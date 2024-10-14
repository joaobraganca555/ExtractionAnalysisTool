# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements.txt file into the container at /app
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Set environment variable to force python to unbuffer output (for real-time logging)
ENV PYTHONUNBUFFERED=1

# Command to run the coordinator-service
CMD ["python", "coordinator_service.py"]
