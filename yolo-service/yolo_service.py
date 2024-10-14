import os
import json
import pika
import boto3
import logging
import time
from ultralytics import YOLO
from dotenv import load_dotenv
import requests

# Load environment variables from .env file
load_dotenv()

RABBITMQ_DEFAULT_USER = os.getenv("RABBITMQ_DEFAULT_USER", "user")
RABBITMQ_DEFAULT_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "password")
YOLO_MODEL = os.getenv("YOLO_MODEL", "yolov8n.pt")
BUCKET_NAME = os.getenv("BUCKET_NAME", "data-extraction-file-storage-thesis")
RESULT_SERVICE_URL = os.getenv("RESULT_SERVICE_URL", "http://result-service:5007")

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)

# Initialize an S3 client
s3 = boto3.client("s3")

# YOLO model initialization
model = YOLO(YOLO_MODEL)  # Load YOLOv8 model (change to your model path if necessary)


def download_file_from_s3(file_key, download_path):
    """Download a file from S3."""
    logging.info(f"Downloading {file_key} from S3...")
    s3.download_file(BUCKET_NAME, file_key, download_path)
    logging.info(f"Downloaded {file_key} to {download_path}")


def extract_yolo_results(results):
    """Extract relevant YOLO results for MongoDB storage."""
    extracted_results = []

    for result in results:
        boxes = result.boxes  # The boxes object contains detected bounding boxes
        extracted_boxes = []

        for box in boxes:
            # Extract box details (x1, y1, x2, y2) and confidence score
            extracted_boxes.append(
                {
                    "box": box.xyxy.tolist()[
                        0
                    ],  # Convert bounding box coordinates to list
                    "confidence": float(box.conf[0]),  # Confidence score
                    "class": int(box.cls[0]),  # Class label (index)
                    "label": result.names[
                        int(box.cls[0])
                    ],  # Class name (e.g., 'person', 'car')
                }
            )

        extracted_results.append(extracted_boxes)

    return extracted_results


def process_image(image_key):
    """Process a single image using YOLO."""
    image_path = None

    image_path = f"/tmp/{image_key.split('/')[-1]}"
    download_file_from_s3(image_key, image_path)

    # YOLO image processing logic goes here
    logging.info(f"Processing image with YOLO: {image_path}")
    results = model.predict(source=image_path)

    # Extract relevant YOLO results
    yolo_results = extract_yolo_results(results)

    # Log YOLO results and remove the image
    logging.info(f"Image {image_key} processed. Results: {yolo_results}")
    os.remove(image_path)
    logging.info(f"Image {image_path} processed and removed.")

    return yolo_results


def process_frames(frames_dir_key):
    """Process a directory of frames for a video using YOLO."""
    frame_paths = []  # Initialize frame_paths as an empty list

    # Download each frame from the frames directory in S3
    objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=frames_dir_key)

    # Download and store frames locally
    for obj in objects.get("Contents", []):
        frame_key = obj["Key"]
        frame_filename = frame_key.split("/")[
            -1
        ]  # Extract filename (e.g., frame_0.jpg)
        frame_path = f"/tmp/{frame_filename}"
        download_file_from_s3(frame_key, frame_path)
        frame_paths.append((frame_path, frame_filename))  # Store both path and filename

    # Sort frames by number based on their filename
    # Assuming the filenames follow the format "frame_<number>.jpg"
    frame_paths.sort(key=lambda x: int(x[1].split("_")[1].split(".")[0]))

    # Extract only the frame paths for YOLO processing
    sorted_frame_paths = [frame_path for frame_path, _ in frame_paths]
    logging.info(f"Frames sorted and ready for YOLO processing: {sorted_frame_paths}")

    # YOLO frame processing logic (process all frames)
    logging.info(f"Processing frames with YOLO...")
    results = model.predict(
        source=sorted_frame_paths
    )  # Pass list of frame paths to YOLO

    # Extract relevant YOLO results
    yolo_results = extract_yolo_results(results)

    # Clean up frames locally
    for frame_path in sorted_frame_paths:
        os.remove(frame_path)
        logging.info(f"Frame {frame_path} processed and removed.")

    logging.info(f"YOLO frame processing completed for directory: {frames_dir_key}.")

    return yolo_results


def send_results_to_result_service(item_id, result, status):
    """Send YOLO results to the result service."""
    result_data = {
        "item_id": item_id,
        "service": "yolo",  # Service name (in this case YOLO)
        "result": result,
        "status": status,
    }

    try:
        response = requests.post(f"{RESULT_SERVICE_URL}/results/save", json=result_data)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)
        logging.info(
            f"Results for item {item_id} saved to result service. Response: {response.json()}"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to save results to result service: {str(e)}")


def process_message(ch, method, properties, body):
    """Process messages received from the RabbitMQ queue."""
    try:
        message = json.loads(body)
        item_id = message["item_id"]
        frames_path = message.get("frames_path")
        image_path = message.get("image_path")
        result = []

        logging.info(f"Received YOLO message for item {item_id}. Processing...")

        if frames_path:
            # Process the frames for a video
            result = process_frames(frames_path)
        elif image_path:
            # Process a single image
            result = process_image(image_path)
        else:
            raise ValueError(f"No valid path found in the message: {message}")

        # Send the results to the result service
        send_results_to_result_service(item_id, result, "completed")

    except Exception as e:
        send_results_to_result_service(item_id, result, "failed")
        logging.error(f"Error processing message from RabbitMQ. Error: {str(e)}")


def start_yolo_service():
    """Start the YOLO service and listen to the RabbitMQ 'yolo_queue'."""
    credentials = pika.PlainCredentials(RABBITMQ_DEFAULT_USER, RABBITMQ_DEFAULT_PASS)

    while True:
        try:
            logging.info("Connecting to RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
            )
            logging.info("Connected to RabbitMQ")

            channel = connection.channel()

            # Declare the queue to ensure it exists
            channel.queue_declare(queue="yolo_queue", durable=True)

            logging.info("Waiting for messages in 'yolo_queue'...")
            channel.basic_consume(
                queue="yolo_queue", on_message_callback=process_message, auto_ack=True
            )
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(
                f"Connection to RabbitMQ failed, retrying in 5 seconds: {str(e)}"
            )
            time.sleep(5)


# Run the YOLO service
if __name__ == "__main__":
    start_yolo_service()
