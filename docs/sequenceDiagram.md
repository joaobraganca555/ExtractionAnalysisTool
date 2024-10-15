# Sequence Diagram

```mermaid
sequenceDiagram
    actor User
    participant Frontend
    participant Upload
    participant AWSS3
    participant Coordinator
    participant YOLO Object
    participant YOLO Classification
    participant YOLO Logo
    participant Whisper
    participant EasyOCR
    participant Sentiment
    participant Result
    activate Frontend
    User ->> Frontend: Upload video/image and select services
    alt Image Upload
    activate Upload
        Frontend ->> Upload: Send image file, selected services and language
    else Video Upload
        Frontend ->> User: Request frame-per-second input
        User ->> Frontend: Provide frame-per-second input
        Frontend ->> Upload: Send video file, frame-per-second, selected services and language
    end
    deactivate Frontend
    alt Image Upload
    activate AWSS3
        Upload ->> AWSS3: Upload image file
    activate Coordinator
        Upload ->> Coordinator: Notify coordinator with image details
    else Video Upload
        Upload ->> Upload: Extract frames from video
        Upload ->> AWSS3: Upload video and frames
    deactivate AWSS3
        Upload ->> Coordinator: Notify coordinator with video details
    end
    deactivate Upload
    activate YOLO Object
    Coordinator ->> YOLO Object: Trigger object detection (if selected)
    activate YOLO Classification
    Coordinator ->> YOLO Classification: Trigger image classification (if selected)
    activate YOLO Logo
    Coordinator ->> YOLO Logo: Trigger logo detection (if selected)
    activate Whisper
    Coordinator ->> Whisper: Trigger speech recognition (if selected)
    activate EasyOCR
    Coordinator ->> EasyOCR: Trigger OCR (if selected)
    deactivate Coordinator
    activate AWSS3
    YOLO Object ->> AWSS3: Download file from S3x
    YOLO Classification ->> AWSS3: Download file from S3
    YOLO Logo ->> AWSS3: Download file from S3
    Whisper ->> AWSS3: Download file from S3
    EasyOCR ->> AWSS3: Download file from S3
    deactivate AWSS3
    activate Coordinator
    Whisper -->> Coordinator: Notify coordinator with results
    activate Sentiment
    Coordinator ->> Sentiment: Trigger Sentiment
    deactivate Coordinator
    activate AWSS3
    Sentiment ->> AWSS3: Download file from S3
    deactivate AWSS3
    YOLO Object ->> Result: Save object detection results
    deactivate YOLO Object
    YOLO Classification ->> Result: Save image classification results
    deactivate YOLO Classification
    YOLO Logo ->> Result: Save image logo results
    deactivate YOLO Logo
    Whisper ->> Result: Save speech recognition results
    deactivate Whisper
    EasyOCR ->> Result: Save OCR results
    deactivate EasyOCR
    Sentiment ->> Result: Save sentiment analysis results
    deactivate Sentiment
    Result -->> Frontend: Display results
