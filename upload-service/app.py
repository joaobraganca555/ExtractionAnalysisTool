import boto3
import os
import cv2
import uuid
import logging
from fastapi import FastAPI, UploadFile, Form
from botocore.client import Config
from typing import List
import pika  # Import for RabbitMQ interaction
import json
from dotenv import load_dotenv
import requests
from moviepy.editor import VideoFileClip

# Initialize FastAPI app
app = FastAPI()

# Load .env file
load_dotenv()

BUCKET_NAME = os.getenv("BUCKET_NAME", "data-extraction-file-storage-thesis")
RESULT_SERVICE_URL = os.getenv("RESULT_SERVICE_URL", "http://result-service:5007")

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)

# Initialize S3 client
s3 = boto3.client("s3")


# Initialize RabbitMQ connection
def publish_to_rabbitmq(queue_name, message):
    try:
        # Set the RabbitMQ credentials (user/password as defined in docker-compose)
        credentials = pika.PlainCredentials("user", "password")

        # Establish a connection to RabbitMQ with credentials
        connection = pika.BlockingConnection(
            pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
        )
        channel = connection.channel()

        # Declare a queue to ensure it exists
        channel.queue_declare(queue=queue_name, durable=True)

        # Publish the message to the specified queue
        channel.basic_publish(
            exchange="", routing_key=queue_name, body=json.dumps(message)
        )

        logging.info(
            f"Message published to RabbitMQ queue '{queue_name}' with content: {message}"
        )

    except Exception as e:
        logging.error(f"Failed to publish message to RabbitMQ. Error: {str(e)}")
    finally:
        connection.close()


# Function to split and upload video frames
def split_and_upload_frames(video_path, frame_second, video_id):
    frames_dir = f"videos/{video_id}/frames/"
    try:
        video_capture = cv2.VideoCapture(video_path)
        fps = int(video_capture.get(cv2.CAP_PROP_FPS))
        frame_interval = fps * frame_second
        frame_count = 0

        logging.info(
            f"Starting to split video '{video_id}' into frames every {frame_second} seconds."
        )

        while True:
            success, frame = video_capture.read()
            if not success:
                break
            if frame_count % frame_interval == 0:
                frame_filename = f"/tmp/frame{frame_count}.jpg"
                cv2.imwrite(frame_filename, frame)
                s3_frame_key = f"{frames_dir}frame_{frame_count}.jpg"
                s3.upload_file(frame_filename, BUCKET_NAME, s3_frame_key)
                os.remove(frame_filename)
                logging.info(f"Uploaded frame {frame_count} to S3 at '{s3_frame_key}'.")
            frame_count += 1

        logging.info(f"Completed frame splitting for video '{video_id}'.")
        return frames_dir  # Return the frames directory path
    except Exception as e:
        logging.error(
            f"Failed to split and upload frames for video '{video_id}'. Error: {str(e)}"
        )
        raise
    finally:
        video_capture.release()


# Function to notify the coordinator via RabbitMQ
def notify_services_via_rabbitmq(item_id, services, item_type, paths, languages):
    message = {
        "item_id": item_id,
        "services": services,
        "item_type": item_type,
        "paths": paths,
        "languages": languages,
    }

    logging.info(f"Sending message to RabbitMQ to notify services: {message}")

    # Serialize the message to JSON before publishing to RabbitMQ
    publish_to_rabbitmq("coordinator_queue", message)


def save_upload(item_id, services, frame_second, s3_file_key, video_length, languages):
    frame_second = frame_second if frame_second is not None else 0
    video_length = video_length if video_length is not None else 0
    languages = languages if languages is not None else []

    result_data = {
        "item_id": item_id,
        "services": services,
        "frame_second": frame_second,
        "s3_file_key": s3_file_key,
        "video_length": video_length,
        "languages": languages,
    }

    logging.info(f"results data: {result_data}")

    try:
        response = requests.post(f"{RESULT_SERVICE_URL}/upload/save", json=result_data)
        response.raise_for_status()  # Raise an error for bad responses (4xx or 5xx)
        logging.info(f"Upload details for item {item_id} saved to result service.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to save upload details to result service: {str(e)}")


@app.post("/upload")
async def upload_file(
    file: UploadFile,
    frame_second: int = Form(None),
    services: List[str] = Form(...),
    languages: List[str] = Form(...),
):
    item_id = str(uuid.uuid4())  # Generate unique ID for both videos and images
    file_path = f"/tmp/{file.filename}"
    s3_file_key = None
    video_length = None  # To store video length

    try:
        # Save the uploaded file locally
        with open(file_path, "wb") as f:
            f.write(await file.read())
        logging.info(f"File '{file.filename}' saved locally at '{file_path}'.")

        paths = {}

        if file.filename.endswith((".mp4", ".mov")):
            if frame_second is None:
                logging.error(
                    "Frame second is required for video files but was not provided."
                )
                return {"error": "frame_second is required for video files."}

            # Get the video length using VideoFileClip
            video = VideoFileClip(file_path)
            video_length = video.duration  # Get video length in seconds
            video.close()

            # Upload full video for Whisper
            s3_video_key = f"videos/{item_id}/{file.filename}"
            s3.upload_file(
                file_path,
                BUCKET_NAME,
                s3_video_key,
                ExtraArgs={
                    "ContentType": "image/jpeg",  # or the correct content type for your file
                    "ACL": "public-read",  # Set the file to be publicly readable
                },
            )
            logging.info(f"Video '{file.filename}' uploaded to S3 at '{s3_video_key}'.")

            # Split and upload frames for YOLO
            frames_dir = split_and_upload_frames(file_path, frame_second, item_id)

            # Add the paths to the message
            paths["video_path"] = s3_video_key
            paths["frames_path"] = frames_dir
            s3_file_key = s3_video_key

            # Notify the services via RabbitMQ
            notify_services_via_rabbitmq(item_id, services, "video", paths, languages)

            logging.info(
                f"Video '{file.filename}' processed, frames uploaded, and services triggered via coordinator."
            )
            return {
                "message": f"Video '{file.filename}' processed, frames uploaded, and services triggered via coordinator."
            }

        else:
            # Upload the image
            s3_image_key = f"images/{item_id}/{file.filename}"
            s3.upload_file(file_path, BUCKET_NAME, s3_image_key)
            logging.info(f"Image '{file.filename}' uploaded to S3 at '{s3_image_key}'.")

            # Add the image path to the message
            paths["image_path"] = s3_image_key
            s3_file_key = s3_image_key

            # Notify the services via RabbitMQ
            notify_services_via_rabbitmq(item_id, services, "image", paths, languages)

            logging.info(
                f"Image '{file.filename}' uploaded and services triggered via coordinator."
            )
            return {
                "message": f"Image '{file.filename}' uploaded and services triggered via coordinator."
            }

    except Exception as e:
        logging.error(f"Error processing file '{file.filename}'. Error: {str(e)}")
        return {"error": str(e)}

    finally:
        # Pass the video_length to save_upload (if it's a video)
        save_upload(
            item_id, services, frame_second, s3_file_key, video_length, languages
        )
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Temporary file '{file_path}' deleted.")
