# Base image: Use Python slim image for a lightweight setup
FROM python:3.9-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements.txt into the container
COPY requirements.txt .

# Install the necessary dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code into the container
COPY . .

# Define the command to run the sentiment service (replace with your sentiment service script)
CMD ["python", "sentiment_service.py"]
