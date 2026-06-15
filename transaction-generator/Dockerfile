FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
# Not actually used, but keeping for consistency

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]