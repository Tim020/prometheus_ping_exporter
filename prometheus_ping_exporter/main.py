import re
import signal
import subprocess
import sys
import time
from functools import partial
from multiprocessing import Event, Process, Queue, cpu_count
from typing import List, Tuple, Union

from more_itertools import distribute
from prometheus_client import start_http_server

from prometheus_ping_exporter.metrics import (
    HOST_AVAILABILITY,
    PROCESS_DURATION_SECONDS,
    RECEIVED_PACKETS,
    SCRAPE_COUNT,
    SCRAPE_DURATION_SECONDS,
    TRANSMITTED_PACKETS,
)
from prometheus_ping_exporter.types import PingResult, ProcessDuration

ping_summary = re.compile(
    r"(?P<transmit_packets>[0-9]+) packets transmitted, (?P<received_packets>[0-9+]) packets received, (?P<packet_loss>[0-9]+\.[0-9]+)% packet loss.*"
)


def terminate_processes(signum, frame, processes: List[Process], run_flag: Event):
    print("Signal received, terminating processes.")
    run_flag.set()
    for p in processes:
        p.terminate()
        p.join()
    sys.exit(0)


def _ping_host(host: str, count: int) -> Tuple[str, str]:
    ping = subprocess.Popen(
        ["ping", "-c", str(count), host],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, error = ping.communicate()
    return out, error


def _pinger(
    hosts: List[str],
    ping_count: int,
    scrape_interval: int,
    results_queue: Queue,
    run_flag: Event,
    process_num: int,
) -> None:
    while not run_flag.is_set():
        start_time = time.time()
        for host in hosts:
            split_out = []
            inner_start_time = time.time()
            out, error = _ping_host(host, int(ping_count))
            inner_duration = time.time() - inner_start_time
            if out:
                split_out = out.splitlines()
            if error and not split_out:
                results_queue.put(
                    PingResult(process_num, True, host, inner_duration, [])
                )
            else:
                results_queue.put(
                    PingResult(process_num, False, host, inner_duration, split_out)
                )
        duration = time.time() - start_time
        results_queue.put(ProcessDuration(process_num, duration))
        next_sleep = scrape_interval - duration
        if next_sleep < 0:
            print(
                "Next sleep is less than 1 second. Consider tuning the scrape_interval to a higher value."
            )
        time.sleep(max(next_sleep, 1))


def _process_result(result: Union[PingResult, ProcessDuration]):
    if isinstance(result, PingResult):
        SCRAPE_DURATION_SECONDS.labels(
            process=result.process_index, host=result.host
        ).observe(result.duration)
        SCRAPE_COUNT.labels(
            process=result.process_index, host=result.host, is_error=result.is_error
        ).inc()
        if result.is_error:
            return

        summary_match = None
        for line in result.output:
            summary_match = ping_summary.match(line)
            if summary_match:
                break
        if not summary_match:
            print("Could not find packet transmit summary in ping output, ignoring.")

        packets_transmitted = int(summary_match.group("transmit_packets"))
        TRANSMITTED_PACKETS.labels(host=result.host).inc(packets_transmitted)
        packets_received = int(summary_match.group("received_packets"))
        RECEIVED_PACKETS.labels(host=result.host).inc(packets_received)

        if packets_received == 0:
            HOST_AVAILABILITY.labels(host=result.host).set(0)
        else:
            HOST_AVAILABILITY.labels(host=result.host).set(1)
    elif isinstance(result, ProcessDuration):
        PROCESS_DURATION_SECONDS.labels(process=result.process_index).observe(
            result.duration
        )
    else:
        print("Result is not a PingResult or ProcessDuration instance.")


def main(http_port: int, hosts: List[str], max_processes: int) -> None:
    # Dedupe hosts, in case of duplicate entries
    deduped_hosts = list(set(hosts))
    if len(deduped_hosts) != len(hosts):
        print("Deduped hosts: {}".format(deduped_hosts))
        hosts = deduped_hosts

    # Set up termination handler
    run_flag = Event()
    processes = []
    signal.signal(
        signal.SIGINT,
        partial(terminate_processes, processes=processes, run_flag=run_flag),
    )
    signal.signal(
        signal.SIGTERM,
        partial(terminate_processes, processes=processes, run_flag=run_flag),
    )

    # Start the Prometheus Server
    start_http_server(http_port)

    # Calculate the number of processes we can use, and chunk the input hosts list accordingly
    if max_processes == -1:
        max_processes = min(1, cpu_count() - 1)
    desired_processes = min(len(hosts), max_processes)
    chunked_hosts = [list(chunk) for chunk in distribute(desired_processes, hosts)]

    # Set up the multiple processes to run
    results_queue = Queue()
    for index, hosts_chunk in enumerate(chunked_hosts):
        print(f"Starting process {index} with {len(hosts_chunk)} hosts")
        process = Process(
            target=_pinger,
            args=(hosts_chunk, 4, 15, results_queue, run_flag, index),
            daemon=True,
        )
        processes.append(process)
        process.start()

    while not run_flag.is_set():
        ping_result = results_queue.get()
        _process_result(ping_result)

    # If we fall through to here, then gracefully terminate
    terminate_processes(None, None, processes, run_flag)


if __name__ == "__main__":
    main(8080, [], 1)
