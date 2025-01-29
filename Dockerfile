FROM python:3.10-bookworm
RUN apt update
RUN apt install iputils-ping -y

# Python requirements
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Python code
COPY . .

EXPOSE 8080
ENTRYPOINT ["python3", "main.py"]
