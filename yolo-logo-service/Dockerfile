# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies for YOLO and PyTorch
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install pip and any required dependencies
RUN pip install --upgrade pip

# Copy the requirements.txt file to the container at /app
COPY requirements.txt .

# Install dependencies specified in the requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Download the YOLO model from AWS S3
RUN wget https://data-extraction-file-storage-thesis.s3.eu-north-1.amazonaws.com/yolo-logo-models/yolov8x_logo_v1.pt -O /app/yolov8x_logo_v1.pt

# Copy the current directory contents into the container at /app
COPY . .

# Expose the port the service will run on
EXPOSE 5009

# Set environment variable to force python to unbuffer output (for real-time logging)
ENV PYTHONUNBUFFERED=1

# Command to run the YOLO service
CMD ["python", "yolo_logo_service.py"]
