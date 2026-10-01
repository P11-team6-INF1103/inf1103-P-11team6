FROM python:3.11-slim

WORKDIR /app

COPY library.txt .
RUN pip install --no-cache-dir -r library.txt

COPY . .

CMD ["python", "main.py"]
