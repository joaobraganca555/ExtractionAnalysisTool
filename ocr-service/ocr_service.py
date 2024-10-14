import os
import json
import pika
import boto3
import logging
import easyocr
import time
import cv2
import requests
from dotenv import load_dotenv
from typing import List, Dict, Union

# Load environment variables from .env file
load_dotenv()

RABBITMQ_DEFAULT_USER = os.getenv("RABBITMQ_DEFAULT_USER", "user")
RABBITMQ_DEFAULT_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "password")
DEFAULT_OCR_LANGUAGES = os.getenv("DEFAULT_OCR_LANGUAGES", "en").split(",")
BUCKET_NAME = os.getenv("BUCKET_NAME", "data-extraction-file-storage-thesis")
RESULT_SERVICE_URL = os.getenv("RESULT_SERVICE_URL", "http://result-service:5007")
# OCR_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_CONFIDENCE_THRESHOLD", 0.50))

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)

# Initialize an S3 client
s3 = boto3.client("s3")

# Initialize EasyOCR Reader
env_languages = DEFAULT_OCR_LANGUAGES


def download_file_from_s3(file_key, download_path):
    """Download a file from S3."""
    logging.info(f"Downloading {file_key} from S3...")
    s3.download_file(BUCKET_NAME, file_key, download_path)
    logging.info(f"Downloaded {file_key} to {download_path}")


def enhance_image_for_ocr(image_path):
    """
    Enhance the image for better OCR performance by converting to grayscale and adjusting contrast.

    :param image_path: Path to the image to be enhanced.
    :return: Path to the enhanced image.
    """
    img = cv2.imread(image_path)

    # Convert the image to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Apply histogram equalization to improve contrast
    enhanced_img = cv2.equalizeHist(gray)

    # Save the enhanced image back to the original path
    cv2.imwrite(image_path, enhanced_img)
    logging.info(f"Enhanced image saved at: {image_path}")

    return image_path


def resize_image(image_path, max_size=(800, 800), min_size=(300, 300)):
    """
    Resize the image to reduce memory usage while keeping the aspect ratio.
    Adjusts the image size based on its original dimensions and only resizes if larger than min_size.

    :param image_path: Path to the image to be resized.
    :param max_size: Maximum dimensions for the resized image (default is 800x800).
    :param min_size: Minimum dimensions below which resizing will not be applied (default is 300x300).
    :return: Path to the resized image.
    """
    img = cv2.imread(image_path)

    # Get the original dimensions of the image
    original_height, original_width = img.shape[:2]

    # If the image is already smaller than the minimum size, don't resize
    if original_width < min_size[0] or original_height < min_size[1]:
        logging.info(f"Image is small enough, skipping resizing.")
        return image_path

    # Calculate the aspect ratio of the image
    aspect_ratio = original_width / original_height

    # Determine the new width and height while maintaining the aspect ratio
    if original_width > original_height:
        new_width = min(max_size[0], original_width)
        new_height = int(new_width / aspect_ratio)
    else:
        new_height = min(max_size[1], original_height)
        new_width = int(new_height * aspect_ratio)

    # Resize the image
    resized_img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    # Overwrite the original image with the resized one
    cv2.imwrite(image_path, resized_img)
    logging.info(
        f"Resized image saved at: {image_path} (Size: {new_width}x{new_height})"
    )

    return image_path


def process_image(
    image_key: str, languages: List[str]
) -> List[Dict[str, Union[str, float]]]:
    """Process a single image using OCR."""

    if languages:
        ocr_reader = easyocr.Reader(languages)
        logging.info(f"Running OCR on languages: {languages}")
    else:
        ocr_reader = easyocr.Reader(env_languages)
        logging.info(f"Running OCR on default languages: {env_languages}")

    image_path = f"/tmp/{image_key.split('/')[-1]}"
    download_file_from_s3(image_key, image_path)

    # Resize image to reduce memory usage
    resize_image(image_path, max_size=(1024, 1024), min_size=(300, 300))
    enhance_image_for_ocr(image_path)

    logging.info(f"Running OCR on image: {image_path}")
    ocr_result = ocr_reader.readtext(image_path)

    # Structure the results into a list of dictionaries
    # Not using bounding box coordinates for simplicity
    results = [
        {"text": text, "confidence": confidence}
        for _, text, confidence in ocr_result
        # if confidence >= OCR_CONFIDENCE_THRESHOLD
    ]

    os.remove(image_path)
    return results


def process_frames(
    frames_dir_key: str, languages: List[str]
) -> List[Dict[str, Union[str, float]]]:
    """Process a directory of frames for a video using OCR."""
    logging.info(f"Processing frames in directory: {frames_dir_key}")

    # Initialize the OCR reader with the specified languages or defaults
    if languages:
        ocr_reader = easyocr.Reader(languages)
        logging.info(f"Running OCR on languages: {languages}")
    else:
        ocr_reader = easyocr.Reader(env_languages)
        logging.info(f"Running OCR on default languages: {env_languages}")

    # Fetch the objects in the frames directory from S3
    objects = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=frames_dir_key)
    frame_files = []

    # Download all frames and store them locally
    for obj in objects.get("Contents", []):
        frame_key = obj["Key"]
        frame_path = f"/tmp/{frame_key.split('/')[-1]}"
        download_file_from_s3(frame_key, frame_path)
        frame_files.append(frame_path)

    # Sort the frame files based on the frame number (assuming numeric frame names)
    frame_files.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))

    results = []

    # Process each frame after sorting
    for frame_path in frame_files:
        # Resize frame to reduce memory usage
        resize_image(frame_path, max_size=(1024, 1024), min_size=(300, 300))
        enhance_image_for_ocr(frame_path)

        logging.info(f"Running OCR on frame: {frame_path}")
        ocr_result = ocr_reader.readtext(frame_path)

        # Structure the frame results
        frame_results = [
            {"text": text, "confidence": confidence}
            for _, text, confidence in ocr_result
            # if confidence >= OCR_CONFIDENCE_THRESHOLD
        ]
        results.append(frame_results)

        # Clean up the local frame file
        os.remove(frame_path)

    logging.info(f"Completed OCR processing for frames in directory: {frames_dir_key}")
    return results


def send_results_to_result_service(
    item_id: str, results: List[Dict[str, Union[str, float]]], status: str
):
    """Send OCR results to the result service."""
    result_data = {
        "item_id": item_id,
        "service": "ocr",
        "result": results,
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
        languages = message.get("languages")
        result = []

        logging.info(f"Received OCR message for item {item_id}. Processing...")

        if frames_path:
            # Process the frames for a video
            result = process_frames(frames_path, languages)
        elif image_path:
            # Process a single image
            result = process_image(image_path, languages)
        else:
            raise ValueError(f"No valid path found in the message: {message}")

        # Send the results to the result service
        send_results_to_result_service(item_id, result, "completed")

    except Exception as e:
        send_results_to_result_service(item_id, result, "failed")
        logging.error(f"Error processing message from RabbitMQ. Error: {str(e)}")


def start_ocr_service():
    """Start the OCR service and listen to the RabbitMQ 'ocr_queue'."""
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
            channel.queue_declare(queue="ocr_queue", durable=True)

            logging.info("Waiting for messages in 'ocr_queue'...")
            channel.basic_consume(
                queue="ocr_queue", on_message_callback=process_message, auto_ack=True
            )
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(
                f"Connection to RabbitMQ failed, retrying in 5 seconds: {str(e)}"
            )
            time.sleep(5)


# Run the OCR service
if __name__ == "__main__":
    start_ocr_service()
