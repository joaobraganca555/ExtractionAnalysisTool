# ExtractionAnalysisTool
Cloud-based tool for multimedia data extraction and analysis, focusing on influencer content. Utilizes YOLOv8 for object/logo detection, Whisper.AI for speech recognition, and EasyOCR for OCR. Includes sentiment analysis with a scalable microservice architecture for content monitoring.

## System Architecture & Services Description

![systemArchitecture](/docs/architecture.pdf)


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

## Sequence Diagram

The sequence diagram can be found [here](sequenceDiagram.md).