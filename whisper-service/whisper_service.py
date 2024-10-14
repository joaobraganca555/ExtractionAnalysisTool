import os
import pika
import boto3
import whisper
import logging
import json
import time
from dotenv import load_dotenv
import requests

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

RABBITMQ_DEFAULT_USER = os.getenv("RABBITMQ_DEFAULT_USER", "user")
RABBITMQ_DEFAULT_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "password")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "tiny")
BUCKET_NAME = os.getenv("BUCKET_NAME", "data-extraction-file-storage-thesis")
RESULT_SERVICE_URL = os.getenv("RESULT_SERVICE_URL", "http://result-service:5007")

# Initialize S3 client
s3 = boto3.client("s3")

# Whisper model (base model, adjust as needed)
whisper_model = whisper.load_model(WHISPER_MODEL)
credentials = pika.PlainCredentials(RABBITMQ_DEFAULT_USER, RABBITMQ_DEFAULT_PASS)


# Publish Whisper completion back to the coordinator
def publish_whisper_completion(item_id, result):
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
        )
        channel = connection.channel()
        channel.queue_declare(queue="whisper_complete_queue", durable=True)
        message = {"item_id": item_id, "whisper_result": result}
        channel.basic_publish(
            exchange="", routing_key="whisper_complete_queue", body=json.dumps(message)
        )
        logging.info(f"Published Whisper completion message to coordinator: {message}")
    except Exception as e:
        logging.error(f"Failed to publish Whisper completion. Error: {str(e)}")
    finally:
        connection.close()


# Function to download video from S3
def download_video_from_s3(video_key):
    try:
        local_video_path = f"/tmp/{video_key.split('/')[-1]}"
        logging.info(
            f"Downloading video from S3: bucket='{BUCKET_NAME}', key='{video_key}'"
        )

        # Download the video from S3
        s3.download_file(BUCKET_NAME, video_key, local_video_path)

        logging.info(f"Video downloaded to local path: {local_video_path}")
        return local_video_path
    except Exception as e:
        logging.error(f"Failed to download video from S3. Error: {str(e)}")
        raise


# Function to transcribe video using Whisper
def process_whisper(video_key: str, languages):
    try:
        result = []
        # Step 1: Download the video from S3
        logging.info(f"Starting transcription for video with key: {video_key}")
        video_path = download_video_from_s3(video_key)

        if languages:
            logging.info(f"Transcribing video using language {languages[0]}")
            result = whisper_model.transcribe(
                video_path, language=languages[0], fp16=False, verbose=True
            )
        else:
            # Step 2: Transcribe the video using Whisper
            logging.info(f"Transcribing video using Whisper for video: {video_path}")
            result = whisper_model.transcribe(video_path, fp16=False, verbose=True)

        # Step 3: Log and return the transcription result
        segments = result["segments"]
        logging.info(f"Transcription completed for video: {video_key}.")
        return segments

    except Exception as e:
        logging.error(
            f"Error during transcription for video {video_key}. Error: {str(e)}"
        )
        return {"error": str(e)}


# Function to process the message received from RabbitMQ
def process_message(ch, method, properties, body):
    try:
        # Parse the message from the RabbitMQ queue
        message = json.loads(body)
        video_key = message.get("video_path")
        item_id = message.get("item_id")
        languages = message.get("languages")
        results = []

        if video_key:
            logging.info(f"Received message to process video: {video_key}")
            # Process the video using Whisper
            results = process_whisper(video_key, languages)
            send_results_to_result_service(item_id, results, "completed")

            # Publish completion to coordinator
            publish_whisper_completion(item_id, results)
        else:
            raise ValueError(f"No video_key found in the message: {message}")
    except Exception as e:
        send_results_to_result_service(item_id, results, "failed")
        logging.error(f"Error processing RabbitMQ message. Error: {str(e)}")


def send_results_to_result_service(item_id, results, status):
    result_data = {
        "item_id": item_id,
        "service": "whisper",
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


# Start the Whisper service to consume messages from RabbitMQ
def start_whisper_service():
    while True:
        try:
            logging.info("Attempting to connect to RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
            )
            logging.info("Connected to RabbitMQ")

            channel = connection.channel()

            # Declare the whisper queue to ensure it exists
            channel.queue_declare(queue="whisper_queue", durable=True)

            logging.info("Waiting for messages in whisper_queue...")
            channel.basic_consume(
                queue="whisper_queue",
                on_message_callback=process_message,
                auto_ack=True,
            )
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(
                f"Connection to RabbitMQ failed, retrying in 5 seconds: {str(e)}"
            )
            time.sleep(5)


# Run the Whisper service
if __name__ == "__main__":
    start_whisper_service()
