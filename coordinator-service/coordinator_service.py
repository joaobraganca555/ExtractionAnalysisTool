import pika
import json
import logging
import time

# Setup basic logging configuration
logging.basicConfig(level=logging.INFO)


# Publish message to the appropriate service queue
def publish_to_queue(queue_name, message):
    credentials = pika.PlainCredentials("user", "password")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
        )
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_publish(
            exchange="", routing_key=queue_name, body=json.dumps(message)
        )
        logging.info(f"Published to {queue_name}: {message}")
    except Exception as e:
        logging.error(f"Failed to publish to {queue_name}. Error: {str(e)}")
    finally:
        connection.close()


def process_message(ch, method, properties, body):
    try:
        message = json.loads(body)
        logging.info(f"Parsed message: {message}")
        item_id = message["item_id"]
        item_type = message["item_type"]
        services = message["services"]
        paths = message["paths"]  # Get the paths for video, frames, or image
        languages = message["languages"]

        logging.info(
            f"Received message to process item {item_id} with services: {services} and paths: {paths}"
        )

        # Send messages to specific service queues
        if "whisper" in services and item_type == "video":
            publish_to_queue(
                "whisper_queue",
                {
                    "item_id": item_id,
                    "video_path": paths.get("video_path"),
                    "languages": languages,
                },
            )

        if "yolo_cls" in services:
            if item_type == "video":
                publish_to_queue(
                    "yolo_cls_queue",
                    {"item_id": item_id, "frames_path": paths.get("frames_path")},
                )
            else:
                publish_to_queue(
                    "yolo_cls_queue",
                    {"item_id": item_id, "image_path": paths.get("image_path")},
                )

        if "yolo_logo" in services:
            if item_type == "video":
                publish_to_queue(
                    "yolo_logo_queue",
                    {"item_id": item_id, "frames_path": paths.get("frames_path")},
                )
            else:
                publish_to_queue(
                    "yolo_logo_queue",
                    {"item_id": item_id, "image_path": paths.get("image_path")},
                )

        if "yolo" in services:
            if item_type == "video":
                publish_to_queue(
                    "yolo_queue",
                    {"item_id": item_id, "frames_path": paths.get("frames_path")},
                )
            else:
                publish_to_queue(
                    "yolo_queue",
                    {"item_id": item_id, "image_path": paths.get("image_path")},
                )

        if "ocr" in services:
            if item_type == "video":
                publish_to_queue(
                    "ocr_queue",
                    {
                        "item_id": item_id,
                        "frames_path": paths.get("frames_path"),
                        "languages": languages,
                    },
                )
            else:
                publish_to_queue(
                    "ocr_queue",
                    {
                        "item_id": item_id,
                        "image_path": paths.get("image_path"),
                        "languages": languages,
                    },
                )

        logging.info(f"Processed item {item_id} with services: {services}")

    except Exception as e:
        logging.error(f"Error processing message: {str(e)}")


# New function to process Whisper completion and notify Sentiment service
def process_whisper_completion(ch, method, properties, body):
    try:
        message = json.loads(body)
        logging.info(f"Whisper completion message received: {message}")
        item_id = message["item_id"]
        whisper_result = message["whisper_result"]

        # After Whisper is done, trigger Sentiment service
        logging.info(f"Triggering Sentiment service for item {item_id}")
        publish_to_queue(
            "sentiment_queue", {"item_id": item_id, "whisper_result": whisper_result}
        )
        logging.info(f"Sentiment processing triggered for item {item_id}")

    except Exception as e:
        logging.error(f"Error processing Whisper completion message: {str(e)}")


# Start the coordinator to consume messages from RabbitMQ
def start_coordinator():
    credentials = pika.PlainCredentials("user", "password")

    while True:
        try:
            logging.info("Attempting to connect to RabbitMQ...")
            connection = pika.BlockingConnection(
                pika.ConnectionParameters("rabbitmq", 5672, "/", credentials)
            )
            logging.info("Connected to RabbitMQ")

            channel = connection.channel()

            # Declare the main coordinator queue
            channel.queue_declare(queue="coordinator_queue", durable=True)
            logging.info("Waiting for messages in coordinator_queue...")
            channel.basic_consume(
                queue="coordinator_queue",
                on_message_callback=process_message,
                auto_ack=True,
            )

            # Declare the whisper completion queue
            channel.queue_declare(queue="whisper_complete_queue", durable=True)
            logging.info(
                "Waiting for Whisper completion messages in whisper_complete_queue..."
            )
            channel.basic_consume(
                queue="whisper_complete_queue",
                on_message_callback=process_whisper_completion,
                auto_ack=True,
            )

            # Start consuming messages for both queues
            channel.start_consuming()

        except pika.exceptions.AMQPConnectionError as e:
            logging.error(
                f"Connection to RabbitMQ failed, retrying in 5 seconds: {str(e)}"
            )
            time.sleep(5)


# Run the coordinator
if __name__ == "__main__":
    start_coordinator()
