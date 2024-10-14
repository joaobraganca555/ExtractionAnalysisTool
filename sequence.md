# Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant UploadService
    participant AWSS3
    participant Coordinator
    participant YOLO
    participant Whisper
    participant EasyOCR
    participant Sentiment
    participant MongoDB
    activate Frontend
    User ->> Frontend: Upload video/image and select services
    alt Image Upload
    activate UploadService
        Frontend ->> UploadService: Send image file and selected services
    else Video Upload
        Frontend ->> User: Request frame-per-second input
        User ->> Frontend: Provide frame-per-second input
        Frontend ->> UploadService: Send video file, frame-per-second, and selected services
    end
    deactivate Frontend
    alt Image Upload
    activate AWSS3
        UploadService ->> AWSS3: Upload image file
    activate Coordinator
        UploadService ->> Coordinator: Notify coordinator with image details
    else Video Upload
        UploadService ->> UploadService: Extract frames from video
        UploadService ->> AWSS3: Upload video and frames
    deactivate AWSS3
        UploadService ->> Coordinator: Notify coordinator with video details
    end
    deactivate UploadService
    activate YOLO
    Coordinator ->> YOLO: Trigger object detection (if selected)
    activate Whisper
    Coordinator ->> Whisper: Trigger speech recognition (if selected)
    activate EasyOCR
    Coordinator ->> EasyOCR: Trigger OCR (if selected)
    deactivate Coordinator
    activate AWSS3
    YOLO ->> AWSS3: Download file from S3
    Whisper ->> AWSS3: Download file from S3
    EasyOCR ->> AWSS3: Download file from S3
    deactivate AWSS3
    activate Coordinator
    Whisper -->> Coordinator: Notify coordinator with results
    Coordinator ->> Sentiment: Trigger Sentiment
    activate Sentiment
    deactivate Coordinator
    activate AWSS3
    Sentiment ->> AWSS3: Download file from S3
    deactivate AWSS3
    YOLO ->> MongoDB: Save object detection results
    deactivate YOLO
    Whisper ->> MongoDB: Save speech recognition results
    deactivate Whisper
    EasyOCR ->> MongoDB: Save OCR results
    deactivate EasyOCR
    Sentiment ->> MongoDB: Save sentiment analysis results
    deactivate Sentiment
    MongoDB -->> Frontend: Display results

