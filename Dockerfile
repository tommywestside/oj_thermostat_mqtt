FROM python:3.9

WORKDIR /app

COPY requirements.txt .
COPY import.py .

RUN python3 -m pip install --upgrade pip
RUN pip install -r requirements.txt

CMD ["python3", "import.py"]

