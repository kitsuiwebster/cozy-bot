FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /data

EXPOSE 8010

CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8010"]
