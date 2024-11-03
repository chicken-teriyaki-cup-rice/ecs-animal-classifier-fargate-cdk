import asyncio
import base64
import json
import logging
import os
from io import BytesIO

import streamlit as st
import websockets
from PIL import Image, ImageOps

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("animal-classifier-frontend")

# Streamlit configuration
st.set_page_config(
    page_title="Real-time Animal Classifier",
    page_icon="🐱",
    layout="centered"
)

# Custom CSS to match the minimal design
st.markdown("""
    <style>
    /* Custom styling */
    .stApp { max-width: 1200px; margin: 0 auto; }
    h1 { padding-top: 1rem; padding-bottom: 2rem; }
    .stButton>button { background-color: #000000; color: white; border-radius: 8px; padding: 0.5rem 1rem; border: none; }
    .stButton>button:hover { background-color: #333333; }
    .uploadedFile { border: 1px solid #E6E6E6; border-radius: 12px; padding: 1rem; }
    .stProgress > div > div > div { background-color: #000000; }
    .css-1d391kg { background-color: #F8F8F8; }
    .element-container { background-color: white; padding: 1rem; border-radius: 12px; border: 1px solid #E6E6E6; margin-bottom: 1rem; }
    </style>
""", unsafe_allow_html=True)

# Get WebSocket URL from environment variable
BACKEND_URL = os.getenv('BACKEND_URL', 'wss://backend.isthisasquirrel.com/ws')
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

if DEBUG_MODE:
    st.write(f"Using backend WebSocket URL: {BACKEND_URL}")

# Process image for efficient transmission
@st.cache_data
def process_image(image):
    """Resize and encode image for WebSocket transmission."""
    image = ImageOps.fit(image, (224, 224), Image.Resampling.LANCZOS)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    buffered = BytesIO()
    image.save(buffered, format="JPEG", quality=85, optimize=True)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f'data:image/jpeg;base64,{img_str}'

# WebSocket connection to send image and threshold and receive predictions
async def get_prediction(image_data, threshold):
    """Send image and threshold to backend and receive predictions."""
    try:
        async with websockets.connect(BACKEND_URL) as websocket:
            await websocket.send(json.dumps({
                'image': image_data,
                'threshold': threshold
            }))
            response = await websocket.recv()
            return json.loads(response)
    except websockets.exceptions.InvalidURI:
        logger.error("Invalid WebSocket URI. Check BACKEND_URL configuration.")
        return {"error": "Invalid WebSocket URI. Check BACKEND_URL configuration."}
    except websockets.exceptions.InvalidHandshake as e:
        logger.error(f"Server rejected WebSocket connection (403 Forbidden). Details: {str(e)}")
        return {"error": "Server rejected WebSocket connection (403 Forbidden)."}
    except websockets.exceptions.ConnectionClosedError as e:
        logger.error(f"Connection was closed unexpectedly: {str(e)}")
        return {"error": "Connection closed unexpectedly."}
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        return {"error": f"Connection error: {str(e)}"}

# Display predictions with colored confidence indicators
async def display_predictions(image, threshold):
    processed_image = process_image(image)
    results = await get_prediction(processed_image, threshold)
    
    if "error" in results:
        st.error(results["error"])
    else:
        total = results.get("total_predictions", 0)
        filtered = results.get("filtered_predictions", 0)
        st.write(f"Found {filtered} predictions above {threshold*100:.0f}% confidence")
        
        for pred in results["predictions"]:
            confidence = pred["score"] * 100
            container_color = (
                "🟢" if confidence >= 80 else
                "🟡" if confidence >= 50 else
                "🟠"
            )
            st.write(f"{container_color} **{pred['label']}** - Confidence: {confidence:.1f}%")
            st.progress(pred["score"])

# Check file size before processing
def validate_file_size(uploaded_file):
    """Validate that file size is under 5 MB."""
    max_size_mb = 5
    if uploaded_file.size > max_size_mb * 1024 * 1024:
        st.error(f"File is too large. Max file size is {max_size_mb} MB.")
        return False
    return True

# Wrapper to handle async display in Streamlit
async def display_predictions_wrapper(image, threshold):
    if asyncio.get_event_loop().is_running():
        await display_predictions(image, threshold)
    else:
        asyncio.run(display_predictions(image, threshold))

# Streamlit UI
st.title("🐱 Real-time Animal Classifier")

# Sidebar for settings
with st.sidebar:
    st.header("Settings")
    threshold = st.slider(
        "Confidence Threshold",
        min_value=0.0,
        max_value=1.0,
        value=st.session_state.get("threshold", 0.3),
        step=0.05,
        help="Only show predictions above this confidence level"
    )
    st.session_state.threshold = threshold
    st.info(f"Showing predictions with {threshold*100:.0f}%+ confidence")

# Main content
col1, col2 = st.columns([2, 1])

with col1:
    uploaded_file = st.file_uploader("Upload an image", type=["jpg", "jpeg", "png"])

    if uploaded_file and validate_file_size(uploaded_file):
        image = Image.open(uploaded_file)
        st.image(image, use_column_width=True)
        
        with st.spinner("Analyzing image..."):
            try:
                await display_predictions_wrapper(image, threshold)
            except Exception as e:
                logger.error(f"Error during image analysis: {str(e)}")
                st.error(f"Error: {str(e)}")

with col2:
    st.info("""
    ### Tips
    - Adjust the confidence threshold to filter predictions
    - Higher threshold = fewer but more confident predictions
    - Lower threshold = more predictions but might be less accurate
    """)
    
    if uploaded_file:
        st.success(f"""
        ### Current Settings
        - Threshold: {threshold*100:.0f}%
        - Image size: {image.size}
        - Format: {image.format}
        """)

# Optional camera input
if st.checkbox("Enable Camera"):
    picture = st.camera_input("Take a picture")
    
    if picture:
        image = Image.open(picture)
        with st.spinner("Analyzing image from camera..."):
            try:
                await display_predictions_wrapper(image, threshold)
            except Exception as e:
                logger.error(f"Camera error: {str(e)}")
                st.error(f"Camera error: {str(e)}")
