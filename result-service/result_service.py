from fastapi import FastAPI, HTTPException, Query
from pymongo import MongoClient, DESCENDING
from pydantic import BaseModel, model_validator
import os
from dotenv import load_dotenv
from typing import Union, List, Dict
import boto3
from fastapi.responses import StreamingResponse

# Load environment variables from .env file
load_dotenv()

app = FastAPI()

# MongoDB connection using environment variables
mongo_user = os.getenv("MONGO_INITDB_ROOT_USERNAME", "root")
mongo_password = os.getenv("MONGO_INITDB_ROOT_PASSWORD", "password")
mongo_host = os.getenv("MONGO_HOST", "mongodb")
mongo_port = os.getenv("MONGO_PORT", "27017")
mongo_db = os.getenv("MONGO_DB_NAME", "multimedia_db")
bucket_name = os.getenv("BUCKET_NAME")  # The S3 bucket name

mongo_uri = f"mongodb://{mongo_user}:{mongo_password}@{mongo_host}:{mongo_port}/"
client = MongoClient(mongo_uri)
db = client[mongo_db]
collection = db["processing_results"]

# Initialize S3 client
s3_client = boto3.client("s3")


# Pydantic models for request/response validation
class ResultModel(BaseModel):
    item_id: str
    service: str
    result: Union[Dict, List[Dict], List[List[Dict]]]
    status: str

    @model_validator(mode="after")
    def check_status(self):
        if self.status not in {"pending", "completed", "failed"}:
            raise ValueError("Status must be 'pending', 'completed', or 'failed'")
        return self


class UploadModel(BaseModel):
    item_id: str
    services: List[str]
    frame_second: int
    s3_file_key: str
    video_length: float
    languages: List[str]


@app.get("/results/{item_id}")
async def get_results(item_id: str):
    """Fetch the results for a specific item."""
    try:
        result = collection.find_one({"item_id": item_id}, {"_id": 0})
        if result:
            return result
        else:
            raise HTTPException(status_code=404, detail="Item not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/results/save")
async def save_result(result_data: ResultModel):
    """Save the results for a specific service."""
    try:
        # Update the result of the service in MongoDB
        collection.update_one(
            {"item_id": result_data.item_id},
            {
                "$set": {
                    f"{result_data.service}_result": result_data.result,
                    f"{result_data.service}_status": result_data.status,
                },
                "$currentDate": {"updated_at": True},
            },
            upsert=True,
        )
        return {"message": "Result saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/save")
async def save_upload(upload_data: UploadModel):
    """Save the item_id with uploaded_at timestamp, requested services, and frame_second."""
    try:
        # Check if whisper is requested and add sentiment automatically
        if (
            "whisper" in upload_data.services
            and "sentiment" not in upload_data.services
        ):
            upload_data.services.append("sentiment")

        # Prepare status for each requested service (set to "pending")
        service_statuses = {
            f"{service}_status": "pending" for service in upload_data.services
        }

        # Insert or update the item_id with uploaded_at timestamp, services, and frame_second
        collection.update_one(
            {"item_id": upload_data.item_id},
            {
                "$set": {
                    "item_id": upload_data.item_id,
                    "services": upload_data.services,
                    "frame_second": upload_data.frame_second,
                    "s3_file_key": upload_data.s3_file_key,
                    "video_length": upload_data.video_length,
                    "languages": upload_data.languages,
                    **service_statuses,  # Add status for each service
                },
                "$currentDate": {"uploaded_at": True},
            },
            upsert=True,
        )
        return {
            "message": f"Item {upload_data.item_id} saved with uploaded_at timestamp, services, and frame_second. Service statuses set to pending."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/items/")
async def get_paginated_items(
    skip: int = Query(0, description="Number of items to skip"),
    limit: int = Query(10, description="Number of items to retrieve"),
):
    """Fetch paginated items excluding result fields (e.g., yolo_result, ocr_result)."""
    try:
        # Fetch the total count of items
        total_items = collection.count_documents({})
        # Fetch items and exclude the result fields (e.g., yolo_result, ocr_result)
        items = list(
            collection.find(
                {},  # Query to match all documents
                {
                    "_id": 0,  # Exclude the _id field
                    "yolo_result": 0,  # Exclude YOLO results
                    "ocr_result": 0,  # Exclude OCR results
                    "whisper_result": 0,  # Exclude Whisper results
                    "sentiment_result": 0,  # Exclude Sentiment results
                },
            )
            .sort("uploaded_at", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        return {"items": items, "total_items": total_items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/media/{item_id}")
async def get_media(item_id: str):
    """Fetch the media (image or video) for a specific item based on the S3 file key stored in MongoDB."""
    try:
        # Fetch the document from MongoDB
        document = collection.find_one({"item_id": item_id})
        if not document:
            raise HTTPException(status_code=404, detail="Item not found")

        # Assuming the document contains a field 's3_file_key' that stores the S3 object key
        s3_file_key = document.get("s3_file_key")
        if not s3_file_key:
            raise HTTPException(
                status_code=404, detail="S3 file key not found for this item"
            )

        # Determine the correct content type (MIME type) based on file extension
        file_extension = os.path.splitext(s3_file_key)[1].lower()
        if file_extension in [".jpg", ".jpeg", ".png"]:
            content_type = (
                "image/jpeg" if file_extension in [".jpg", ".jpeg"] else "image/png"
            )
        elif file_extension in [".mp4", ".mov"]:
            content_type = (
                "video/mp4" if file_extension == ".mp4" else "video/quicktime"
            )
        else:
            content_type = "application/octet-stream"  # Default content type if unknown

        # Get the object from S3
        s3_object = s3_client.get_object(Bucket=bucket_name, Key=s3_file_key)
        file_stream = s3_object["Body"]

        # Set a proper filename for the download
        filename = os.path.basename(s3_file_key)

        # Stream the file back to the client with the correct content type and disposition
        headers = {"Content-Disposition": f'inline; filename="{filename}"'}
        return StreamingResponse(file_stream, media_type=content_type, headers=headers)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Run the FastAPI app using `uvicorn` or your preferred server
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
