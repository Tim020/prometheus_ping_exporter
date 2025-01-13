from dataclasses import dataclass
from typing import List


@dataclass
class PingResult:
    process_index: int
    is_error: bool
    host: str
    duration: float
    output: List[str]


@dataclass
class ProcessDuration:
    process_index: int
    duration: float
