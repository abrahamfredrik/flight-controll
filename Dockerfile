# Use Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose Flask port
EXPOSE 3001

# Set environment variables
ENV FLASK_APP=main.py
ENV FLASK_RUN_HOST=0.0.0.0

RUN chmod 755 main.py

RUN ls -l 
RUN ls -l /app

# Run Flask + MQTT listener (if your main.py starts both)
CMD ["python", "main.py"]
