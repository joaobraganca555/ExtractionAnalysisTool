import streamlit as st
from streamlit_timeline import st_timeline
from dotenv import load_dotenv
import requests
import pandas as pd
import tempfile
from moviepy import VideoFileClip
from io import BytesIO
import os
import html

# Load environment variables from .env
load_dotenv()

# Streamlit page configuration
st.set_page_config(page_title="File Processing Dashboard", layout="wide")

# Load available services from .env and split them into a list
AVAILABLE_VIDEO_SERVICES = os.getenv("STREAMLIT_AVAILABLE_VIDEO_SERVICES", "").split(
    ","
)
AVAILABLE_IMAGE_SERVICES = os.getenv("STREAMLIT_AVAILABLE_IMAGE_SERVICES", "").split(
    ","
)
AVAILABLE_EXTENSIONS = os.getenv("STREAMLIT_AVAILABLE_EXTENSIONS", "").split(",")
AVAILABLE_LANGUAGES = os.getenv("STREAMLIT_AVAILABLE_LANGUAGES", "").split(",")
SERVICES_COLUMNS = os.getenv("STREAMLIT_SERVICES_COLUMNS", "").split(",")


# Helper function to get paginated items from the backend
def get_uploaded_files(skip, limit):
    response = requests.get(
        f"http://result-service:5007/items?skip={skip}&limit={limit}"
    )
    if response.status_code == 200:
        data = response.json()
        return data["items"], data["total_items"]  # Return both items and total count
    return [], 0


# Helper function to display status in the table
def get_status_display(status, service_requested):
    if not service_requested:
        return "-"  # Show dash if the service was not requested
    if status == "completed":
        return "✅ Completed"
    elif status == "failed":
        return "❌ Failed"
    else:
        return "⏳ Processing..."


def update_status_columns(df):
    """Update the status columns dynamically based on available services."""
    for i, row in df.iterrows():
        for service in SERVICES_COLUMNS:
            service_status_column = f"{service}_status"
            df.at[i, service_status_column] = get_status_display(
                row.get(service_status_column), service in row.get("services", [])
            )
    return df


# Sidebar: Pagination control
st.sidebar.title("Navigation")
current_page = st.sidebar.number_input("Page", min_value=1, step=1, value=1)
items_per_page = 10  # Number of items per page

# State management for resetting the inputs after upload
if "uploaded" not in st.session_state:
    st.session_state.uploaded = False

# File uploader and service selection
st.sidebar.title("Upload New File")
uploaded_file = st.sidebar.file_uploader("Choose a file", type=AVAILABLE_EXTENSIONS)

services = []
frame_second = 0
languages = []  # Array to hold selected languages

# Only display service selection if a file is uploaded
if uploaded_file is not None:
    st.sidebar.write("File selected: ", uploaded_file.name)
    tfile = tempfile.NamedTemporaryFile(delete=False)
    tfile.write(uploaded_file.read())

    # Service selection based on the file type
    if uploaded_file.type.startswith("video/"):
        services = st.sidebar.multiselect(
            "Select services to run", AVAILABLE_VIDEO_SERVICES
        )

        # Ensure that sentiment is automatically included if whisper is selected
        if "whisper" in services and "sentiment" not in services:
            services.append("sentiment")

        video = VideoFileClip(tfile.name)
        video_length_seconds = int(video.duration)
        video.close()

        # Slider to choose interval in seconds for frame extraction
        frame_second = st.sidebar.slider(
            "Choose interval (seconds) for extracting frames:",
            1,
            video_length_seconds,
            5,
        )
        st.sidebar.write(f"Frames will be extracted every {frame_second} seconds.")
    else:
        services = st.sidebar.multiselect(
            "Select services to run", AVAILABLE_IMAGE_SERVICES
        )

    languages = st.sidebar.multiselect(
        "Select language(s) for the file:", AVAILABLE_LANGUAGES
    )

    if st.sidebar.button("Upload and Process"):
        files = {
            "file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)
        }
        data = {
            "services": services,
            "frame_second": frame_second if "frame_second" in locals() else 0,
            "languages": languages,
        }
        response = requests.post(
            "http://upload-service:5000/upload", files=files, data=data
        )

        if response.status_code == 200:
            st.sidebar.success(f"File uploaded successfully: {uploaded_file.name}")
            st.session_state.uploaded = True  # Mark as uploaded
        else:
            st.sidebar.error(f"Failed to upload file: {response.content}")

# Reset the uploader and inputs after successful upload
if st.session_state.uploaded:
    # Clear all widgets by resetting the session state
    st.session_state.uploader = None
    st.session_state.services = []
    st.session_state.frame_slider = 0
    st.session_state.languages = []
    st.session_state.uploaded = False  # Reset uploaded flag

# Main Page: Display table of uploaded files
st.title("Uploaded Files")

# Calculate the skip value based on the current page
skip = (current_page - 1) * items_per_page

# Get the uploaded files data from the API with pagination
uploaded_files, total_items = get_uploaded_files(skip=skip, limit=items_per_page)

if uploaded_files:
    # Create a DataFrame to display the uploaded files
    df = pd.DataFrame(uploaded_files)

    # Safely format 'uploaded_at' and 'updated_at' columns
    if "uploaded_at" in df.columns and not df["uploaded_at"].isnull().all():
        df["uploaded_at"] = pd.to_datetime(
            df["uploaded_at"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        df["uploaded_at"] = (
            None  # Handle case where 'uploaded_at' is missing or all NaT
        )

    if "updated_at" in df.columns and not df["updated_at"].isnull().all():
        df["updated_at"] = pd.to_datetime(
            df["updated_at"], errors="coerce"
        ).dt.strftime("%Y-%m-%d %H:%M:%S")
    else:
        df["updated_at"] = None  # Handle case where 'updated_at' is missing or all NaT

    df = update_status_columns(df)

    # Add frame_second and video_length to the dataframe
    df["frame_second"] = df.get("frame_second", None)
    df["video_length"] = df.get("video_length", None)
    df["services"] = df.get("services", None)
    df["languages"] = df.get("languages", None)

    # Add dynamically the status columns for each service from SERVICES_COLUMNS
    status_columns = [f"{service}_status" for service in SERVICES_COLUMNS]

    # Reorder the columns to have status columns together and date columns together
    # Now include those dynamically generated status columns along with the other required columns
    df = df[
        [
            "item_id",
            "uploaded_at",
            "updated_at",
            "services",
            "languages",
            "frame_second",
            "video_length",
            *status_columns,  # Dynamically include all service status columns
        ]
    ]

    # Display the table with a radio button for selecting rows
    selection = st.dataframe(df, on_select="rerun", selection_mode="single-row")

    # Check if a row is selected or unselected
    if len(selection["selection"]["rows"]) > 0:
        # Row selected, get the selected row's index and retrieve the corresponding item_id
        selected_index = selection["selection"]["rows"][0]
        st.session_state.selected_item_id = df.iloc[selected_index]["item_id"]
        st.info(f"Item {st.session_state.selected_item_id} selected.")
    else:
        # No row selected, clear the session state for selected_item_id
        if "selected_item_id" in st.session_state:
            del st.session_state.selected_item_id

    # Display the current page and total number of pages
    total_pages = (total_items + items_per_page - 1) // items_per_page
    st.write(f"Page {current_page} of {total_pages}")
else:
    st.write("No files uploaded yet.")


if "selected_frame_timestamp" not in st.session_state:
    st.session_state.selected_frame_timestamp = (
        0  # Default to the first frame (0 seconds)
    )

# Show the details page only when a row is selected
if "selected_item_id" in st.session_state:
    response = requests.get(
        f"http://result-service:5007/results/{st.session_state.selected_item_id}"
    )
    if response.status_code == 200:
        result = response.json()
        st.session_state.result = result

        # Check if the item is a video or image using the frame_second property
        if result.get("frame_second", 0) == 0:

            # Create two columns for side-by-side display
            col1, col2 = st.columns(2)

            with col1:
                media_url = f"http://result-service:5007/media/{st.session_state.selected_item_id}"

                # Manually fetch the image
                image_response = requests.get(media_url)

                if image_response.status_code == 200:
                    image_bytes = BytesIO(image_response.content)
                    st.image(image_bytes)
                else:
                    st.error(f"Failed to load image from {media_url}")

            with col2:
                # Display YOLO results if available
                # st.json(st.session_state.result)

                yolo_results = st.session_state.result.get("yolo_result", [])
                if yolo_results:
                    object_names = [res["label"] for res in yolo_results[0]]
                    st.markdown(
                        f"""
                        <div style='background-color:#d4edda;padding:10px;border-radius:10px;margin-bottom:10px;'>
                            <h4 style='color:#155724;'>Detected Objects:</h4>
                            <p style='font-size:16px;'><strong>{', '.join(object_names)}</strong></p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Display YOLO Classification results if available
                yolo_cls_results = st.session_state.result.get("yolo_cls_result", [])
                if yolo_cls_results:
                    top5_class_names = yolo_cls_results[0]["top5_class_names"]
                    st.markdown(
                        f"""
                        <div style='background-color:#d1ecf1;padding:10px;border-radius:10px;margin-bottom:10px;'>
                            <h4 style='color:#0c5460;'>Top 5 Class Predictions:</h4>
                            <p style='font-size:16px;'><strong>{', '.join(top5_class_names)}</strong></p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Display YOLO Logo Detection results if available
                yolo_logo_results = st.session_state.result.get("yolo_logo_result", [])
                if yolo_logo_results:
                    detected_logos = [res["label"] for res in yolo_logo_results[0]]

                    st.markdown(
                        f"""
                        <div style='background-color:#f3e6ff;padding:10px;border-radius:10px;margin-bottom:10px;'>
                            <h4 style='color:#6f42c1;'>Detected Logos:</h4>
                            <p style='font-size:16px;'><strong>{', '.join(detected_logos)}</strong></p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Display OCR results if available
                ocr_results = st.session_state.result.get("ocr_result", [])
                if ocr_results:
                    ocr_texts = [
                        result["text"]
                        for result in ocr_results
                        if result["confidence"] >= 0.5
                    ]
                    st.markdown(
                        f"""
                        <div style='background-color:#fff3cd;padding:10px;border-radius:10px;margin-bottom:10px;'>
                            <h4 style='color:#856404;'>OCR Text:</h4>
                            <p style='font-size:16px;'><strong>{'<br>'.join(ocr_texts)}</strong></p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
        else:
            # Processed result is a video
            st.write("Timeline with frames")

            timestamps = []
            video_length_seconds = int(result.get("video_length", 0))
            frame_second = result.get("frame_second", 5)

            if frame_second >= video_length_seconds:
                timestamps = [0]  # Only include the 0 frame if interval >= video length
            else:
                for i in range(0, video_length_seconds, frame_second):
                    timestamps.append(i)

            items = []

            # Convert timestamps to strings for the 'content' field
            for idx, timestamp in enumerate(timestamps):
                item = {
                    "id": idx,
                    "content": f"Frame {timestamp}s",
                    "start": timestamp,
                }

                services = st.session_state.result.get("services", [])

                # Add results for each service
                for service in services:
                    if service == "yolo":
                        # Get YOLO results by aligning the index with the timestamp (based on array position)
                        yolo_results = st.session_state.result.get(
                            f"{service}_result", []
                        )
                        if len(yolo_results) > idx:
                            item[service] = yolo_results[
                                idx
                            ]  # Align with timestamp by index
                        else:
                            item[service] = []  # No result for this timestamp
                    elif service == "yolo_cls":
                        # Get YOLO results by aligning the index with the timestamp (based on array position)
                        yolo_cls_results = st.session_state.result.get(
                            f"{service}_result", []
                        )
                        if len(yolo_cls_results) > idx:
                            item[service] = yolo_cls_results[
                                idx
                            ]  # Align with timestamp by index
                        else:
                            item[service] = []  # No result for this timestamp
                    elif service == "yolo_logo":
                        # Get YOLO results by aligning the index with the timestamp (based on array position)
                        yolo_logo_results = st.session_state.result.get(
                            f"{service}_result", []
                        )
                        if len(yolo_logo_results) > idx:
                            item[service] = yolo_logo_results[
                                idx
                            ]  # Align with timestamp by index
                        else:
                            item[service] = []  # No result for this timestamp
                    elif service == "whisper":
                        # Get Whisper results for the timestamp
                        whisper_results = st.session_state.result.get(
                            f"{service}_result", []
                        )
                        item[service] = whisper_results
                    elif service == "ocr":
                        # Get OCR results by aligning the index with the timestamp (based on array position)
                        ocr_results = st.session_state.result.get(
                            f"{service}_result", []
                        )
                        if len(ocr_results) > idx:
                            item[service] = ocr_results[
                                idx
                            ]  # Align with timestamp by index
                        else:
                            item[service] = []  # No result for this timestamp
                    elif service == "sentiment":
                        # Get Sentiment results and merge them into the Whisper results
                        sentiment_results = st.session_state.result.get(
                            f"{service}_result", []
                        )
                        whisper_results = st.session_state.result.get(
                            "whisper_result", []
                        )

                        # Merge sentiment into each corresponding Whisper segment
                        if len(whisper_results) > 0 and len(sentiment_results) == len(
                            whisper_results
                        ):
                            for i in range(len(whisper_results)):
                                whisper_results[i]["sentiment"] = {
                                    "label": sentiment_results[i]["sentiment"]["label"],
                                    "score": sentiment_results[i]["sentiment"]["score"],
                                }
                            item["whisper"] = whisper_results
                        else:
                            item["whisper"] = (
                                whisper_results  # If no sentiment, just keep Whisper
                            )

                items.append(item)

            # Render timeline
            timeline = st_timeline(
                items,
                groups=[],
                options={
                    "zoomable": False,
                    "moveable": False,
                    "horizontalScroll": False,
                    "verticalScroll": False,
                    "timeAxis": {
                        "scale": "second",
                        "step": 1,
                        "showMinorLabels": False,
                        "showMajorLabels": False,
                    },  # Hide labels
                },
                height="200px",
            )

            # Create columns for side-by-side layout
            col1, col2 = st.columns([1, 2])

            # Show video at the selected frame timestamp in the first column (col1)
            with col1:
                media_url = f"http://result-service:5007/media/{st.session_state.selected_item_id}"
                # Manually fetch the video and save it temporarily
                video_response = requests.get(media_url, stream=True)
                if video_response.status_code == 200:
                    tfile = tempfile.NamedTemporaryFile(delete=False)
                    tfile.write(video_response.content)
                    tfile.flush()
                    st.video(
                        tfile.name, start_time=st.session_state.selected_frame_timestamp
                    )
                else:
                    st.error(f"Failed to load video from {media_url}")
            with col2:
                st.subheader("Selected Item Details")

                if timeline:
                    selected_item_id = timeline["id"]  # Get the selected item's id

                    # Find the corresponding timestamp using the selected id
                    selected_item = next(
                        item for item in items if item["id"] == selected_item_id
                    )

                    if (
                        st.session_state.selected_frame_timestamp
                        != selected_item["start"]
                    ):
                        st.session_state.selected_frame_timestamp = selected_item[
                            "start"
                        ]
                        st.rerun()

                    # Display selected frame timestamp
                    st.markdown(
                        f"""
                        <div style='background-color:#f8f9fa;padding:10px;border-radius:10px;margin-bottom:10px;'>
                            <h4 style='color:#007bff;'>Selected Frame Timestamp:</h4>
                            <p style='font-size:18px;'><strong>{st.session_state.selected_frame_timestamp}s</strong></p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Display YOLO results for the selected frame (if available)
                    yolo_results = selected_item.get("yolo", [])
                    if yolo_results:
                        object_names = [res["label"] for res in yolo_results]
                        st.markdown(
                            f"""
                            <div style='background-color:#d4edda;padding:10px;border-radius:10px;margin-bottom:10px;'>
                                <h4 style='color:#155724;'>Detected Objects:</h4>
                                <p style='font-size:16px;'><strong>{', '.join(object_names)}</strong></p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Display YOLO Classification results if available
                    yolo_cls_results = selected_item.get("yolo_cls", [])
                    if yolo_cls_results:
                        top5_class_names = yolo_cls_results["top5_class_names"]

                        st.markdown(
                            f"""
                            <div style='background-color:#d1ecf1;padding:10px;border-radius:10px;margin-bottom:10px;'>
                                <h4 style='color:#0c5460;'>Top 5 Class Predictions:</h4>
                                <p style='font-size:16px;'><strong>{', '.join(top5_class_names)}</strong></p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Display YOLO Logo Detection results if available
                    yolo_logo_results = selected_item.get("yolo_logo", [])
                    if yolo_logo_results:
                        detected_logos = [res["label"] for res in yolo_logo_results]

                        st.markdown(
                            f"""
                            <div style='background-color:#f3e6ff;padding:10px;border-radius:10px;margin-bottom:10px;'>
                                <h4 style='color:#6f42c1;'>Detected Logos:</h4>
                                <p style='font-size:16px;'><strong>{', '.join(detected_logos)}</strong></p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                    # Display Whisper results for the selected frame (if available)
                    whisper_results = selected_item.get("whisper", [])
                    if whisper_results:
                        # Initialize a list to store individual blocks of transcripts and sentiment
                        transcript_blocks = []

                        # Iterate over each whisper segment
                        for whisper_segment in whisper_results:
                            # Check for a timestamp match
                            if (
                                whisper_segment["start"]
                                <= st.session_state.selected_frame_timestamp
                                <= whisper_segment["end"]
                            ):
                                # Get transcript text, sentiment, start, and end time
                                transcript_text = f'"{whisper_segment["text"]}"'
                                start_time = whisper_segment["start"]
                                end_time = whisper_segment["end"]

                                sentiment_label = whisper_segment.get(
                                    "sentiment", {}
                                ).get("label", "N/A")
                                sentiment_score = whisper_segment.get(
                                    "sentiment", {}
                                ).get("score", 0.0)

                                # Format the block for this transcript with its start, end, and sentiment
                                transcript_block = f"""
                                <p style='font-style:italic;font-size:16px;'>
                                    <strong>[{start_time:.2f} - {end_time:.2f}]</strong>
                                    - {transcript_text}
                                </p>
                                <p style='font-size:16px;'>
                                    <strong>Sentiment:</strong> {sentiment_label} ({sentiment_score:.4f})
                                </p>
                                """
                                # Append the formatted block to the list of transcript blocks
                                transcript_blocks.append(transcript_block)

                        # Join all blocks and render them in one container
                        if transcript_blocks:
                            st.markdown(
                                f"""
                                <div style='background-color:#f0f0f0;padding:10px;border-radius:10px;margin-bottom:10px;'>
                                    <h4 style='color:#6c757d;'>Whisper Transcript & Sentiment:</h4>
                                    {"".join(transcript_blocks)}
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                    # Display OCR results for the selected frame (if available)
                    ocr_results = selected_item.get("ocr", [])
                    if ocr_results:
                        ocr_texts = [
                            html.escape(result["text"]) for result in ocr_results if result["confidence"] >= 0.5
                        ]
                        st.markdown(
                            f"""
                            <div style='background-color:#fff3cd;padding:10px;border-radius:10px;margin-bottom:10px;'>
                                <h4 style='color:#856404;'>OCR Text:</h4>
                                <p style='font-size:16px;'><strong>{'<br>'.join(ocr_texts)}</strong></p>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

    else:
        st.error(
            f"Failed to retrieve details for item_id: {st.session_state.selected_item_id}"
        )
