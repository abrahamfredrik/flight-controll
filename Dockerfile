FROM python:3.11-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PYTHONPATH=/app/src

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --no-compile -r requirements.txt

COPY main.py .
COPY src/ ./src/

EXPOSE 3001

CMD ["python", "main.py"]
