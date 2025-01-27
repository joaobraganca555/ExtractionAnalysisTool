# ExtractionAnalysisTool

Cloud-based tool for multimedia data extraction and analysis, focusing on influencer content. Utilizes YOLOv8 for object/logo detection, Whisper.AI for speech recognition, and EasyOCR for OCR. Includes sentiment analysis with a scalable microservice architecture for content monitoring.

## System Architecture & Services Description

![systemArchitecture](/docs/architecture.png)

| **Service**                | **Functionality**                                  | **Task**                                                   |
|----------------------------|---------------------------------------------------|------------------------------------------------------------|
| yolo-service                | Object Detection                                  | Detect objects in images and video frames                  |
| yolo-cls-service            | Image Classification                              | Classify images into categories                            |
| yolo-logo-service           | Logo Detection                                    | Detect specific logos in media                             |
| whisper-service             | Speech Recognition                                | Convert audio to text                                      |
| ocr-service                 | Optical Character Recognition                     | Extract text from images and video frames                  |
| sentiment-service           | Sentiment Analysis                                | Analyse the sentiment of extracted text                    |
| upload-service              | Upload Files                                      | API for uploading files and trigger coordinator            |
| coordinator-service         | Manage services                                   | Controls and manage services                               |
| result-service              | Stores Data                                       | API for storing service results                            |

## Application Video

Watch the demo of the application in action: [Video Link](https://github.com/user-attachments/assets/c564dffb-e532-435d-ac4a-fcef40f3129f)

## How to Run the Application

To run the **ExtractionAnalysisTool** locally, follow these steps:

### Prerequisites
- Ensure you have **Docker** and **Docker Compose** installed on your machine.
- You will need an **AWS S3 Bucket**. Update the `.env.example` file with your S3 credentials before proceeding.

### Steps to Run:

1. **Clone the repository**:

   ```bash
   git clone https://github.com/joaobraganca555/ExtractionAnalysisTool.git
   cd ExtractionAnalysisTool
   
2. **Prepare the .env file**:
   - Rename .env.example to .env:
     ```bash
     mv .env.example .env  

   - Add your AWS S3 Bucket credentials and any other necessary configurations to the .env file.
3. **Build the Docker containers**:
   ```bash
   docker-compose build
4. **Start the services**:
   ```bash
   docker-compose up
5. Once the containers are up, the tool will be running, and you can start interacting with it. Use the ports provided the docker compose file.
