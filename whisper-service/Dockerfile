# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install ffmpeg (required for Whisper to process videos)
RUN apt-get update && apt-get install -y ffmpeg

# Copy the requirements.txt file into the container at /app
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Command to run the whisper-service that consumes RabbitMQ messages
CMD ["python", "whisper_service.py"]
