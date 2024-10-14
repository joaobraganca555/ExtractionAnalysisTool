# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements.txt file to the working directory
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application code to the working directory
COPY . .

# Set environment variable to force python to unbuffer output (for real-time logging)
ENV PYTHONUNBUFFERED=1

# Run your application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000"]
