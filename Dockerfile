FROM python:3.9

WORKDIR /app

COPY requirements.txt .
COPY import.py .

RUN pip install -r requirements.txt

CMD ["python3", "import.py"]

