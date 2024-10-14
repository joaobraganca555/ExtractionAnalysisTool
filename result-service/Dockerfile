FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app code into the container
COPY . .

# Expose the port for the FastAPI service
EXPOSE 5007

# Command to run FastAPI app
CMD ["uvicorn", "result_service:app", "--host", "0.0.0.0", "--port", "5007"]
