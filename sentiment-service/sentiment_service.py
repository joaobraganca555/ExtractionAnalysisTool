import os
import json
import pika
import logging
from transformers import pipeline
from dotenv import load_dotenv
import time
import requests

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)

# Load environment variables from .env file
load_dotenv()

RABBITMQ_DEFAULT_USER = os.getenv("RABBITMQ_DEFAULT_USER", "user")
RABBITMQ_DEFAULT_PASS = os.getenv("RABBITMQ_DEFAULT_PASS", "password")
RESULT_SERVICE_URL = os.getenv("RESULT_SERVICE_URL", "http://result-service:5007")
SENTIMENT_MODEL = os.getenv(
    "SENTIMENT_MODEL", "distilbert/distilbert-base-uncased-finetuned-sst-2-english"
)

# Initialize Sentiment Analysis model
# sentiment_analyzer = pipeline("sentiment-analysis", model=SENTIMENT_MODEL)
sentiment_analyzer = pipeline("sentiment-analysis")


def analyze_sentiment(text):
    """Analyze sentiment using a pre-trained model."""
    result = sentiment_analyzer(text)
    return result


def send_results_to_result_service(item_id, results, status):
    result_data = {
        "item_id": item_id,
        "service": "sentiment",
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
    """Process messages received from RabbitMQ sentiment_queue."""
    try:
        message = json.loads(body)
        item_id = message["item_id"]
        segments = message["whisper_result"]

        logging.info(f"Received message for sentiment analysis on item {item_id}")

        sentiment_results = []

        # Check if transcription is inside a dictionary
        if segments:
            # Process each segment
            for segment in segments:
                text = segment["text"]  # Get the text of the segment
                sentiment_result = analyze_sentiment(text)[
                    0
                ]  # Perform sentiment analysis on the segment

                # Add the sentiment information back into the segment
                segment["sentiment"] = {
                    "label": sentiment_result["label"],
                    "score": sentiment_result["score"],
                }

                # Collect the result for MongoDB
                sentiment_results.append(
                    {"segment_text": text, "sentiment": segment["sentiment"]}
                )

        else:
            raise ValueError(f"Invalid transcription format: {segments}")

        # Update MongoDB with the sentiment result
        send_results_to_result_service(item_id, sentiment_results, "completed")

    except Exception as e:
        send_results_to_result_service(item_id, sentiment_results, "failed")
        logging.error(f"Error processing message from RabbitMQ. Error: {str(e)}")


def start_sentiment_service():
    """Start the Sentiment service and listen to RabbitMQ sentiment_queue."""
    credentials = pika.PlainCredentials(RABBITMQ_DEFAULT_USER, RABBITMQ_DEFAULT_PASS)

    while True:
        try:
            logging.info("Connecting to RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
            )
            logging.info("Connected to RabbitMQ")

            channel = connection.channel()
            channel.queue_declare(queue="sentiment_queue", durable=True)

            logging.info("Waiting for messages in sentiment_queue...")
            channel.basic_consume(
                queue="sentiment_queue",
                on_message_callback=process_message,
                auto_ack=True,
            )
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(
                f"Connection to RabbitMQ failed, retrying in 5 seconds: {str(e)}"
            )
            time.sleep(5)


# Run the sentiment service
if __name__ == "__main__":
    start_sentiment_service()
