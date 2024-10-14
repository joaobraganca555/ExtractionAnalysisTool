# Use a lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install EasyOCR dependencies
RUN apt-get update && apt-get install -y libgl1

# Copy the rest of your application code to the working directory
COPY . .

# Run your OCR service
CMD ["python", "ocr_service.py"]
