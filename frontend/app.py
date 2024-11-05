import asyncio
import base64
import json
import logging
import os
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, Optional, Tuple

import aiohttp
import streamlit as st
import websockets
from PIL import Image, ImageOps

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
if log_level not in logging._nameToLevel:
    log_level = "INFO"
logging.basicConfig(
    level=logging._nameToLevel[log_level],
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("animal-classifier-frontend")

st.set_page_config(
    page_title="Real-time Animal Classifier  for mobile and edge devices",
    page_icon="💻",
    layout="centered"
)

WEBSOCKET_ENDPOINT = os.environ.get('WEBSOCKET_ENDPOINT', 'ws://localhost:8000/ws')
MAX_FILE_SIZE_MB = max(1, min(10, int(os.environ.get('MAX_FILE_SIZE_MB', '5'))))
DEFAULT_THRESHOLD = max(0.1, min(0.9, float(os.environ.get('DEFAULT_THRESHOLD', '0.3'))))
WEBSOCKET_TIMEOUT = max(10, min(60, int(os.environ.get('WEBSOCKET_TIMEOUT', '30'))))
MAX_RETRIES = 3
RETRY_DELAY = 1

def process_image(_image: Image.Image) -> Tuple[str, Tuple[int, int]]:
    try:
        original_size = _image.size
        image_copy = _image.copy()
        processed = ImageOps.fit(image_copy, (256, 256), Image.Resampling.LANCZOS)
        processed = processed.convert('RGB')
        buffered = BytesIO()
        processed.save(buffered, format="JPEG", quality=85, optimize=True)
        image_copy.close()
        return (
            f'data:image/jpeg;base64,{base64.b64encode(buffered.getvalue()).decode()}',
            original_size
        )
    except Exception as e:
        logger.error(f"Image processing failed: {str(e)}", exc_info=True)
        raise RuntimeError(f"Failed to process image: {str(e)}")

async def check_backend_health(retries: int = 3) -> Optional[Dict[str, Any]]:
    health_url = WEBSOCKET_ENDPOINT.replace('ws://', 'http://')
    health_url = health_url.replace('/ws', '/health')
    
    logger.debug(f"Checking backend health at: {health_url}")
    
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(health_url, timeout=5) as response:
                    if response.status == 200:
                        health_data = await response.json()
                        logger.info(f"Backend health check successful: {health_data}")
                        if health_data.get("status") == "healthy":
                            return health_data
                    logger.warning(f"Unhealthy backend response: {response.status}")
        except Exception as e:
            logger.error(f"Health check attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                await asyncio.sleep(RETRY_DELAY)
    return None

async def get_prediction(image_data: str, threshold: float) -> Dict[str, Any]:
    start_time = datetime.now()
    logger.debug("Performing initial health check")
    health = await check_backend_health()
    if not health:
        return {"error": "Backend service is not healthy. Please try again later."}

    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(f"Attempting WebSocket connection (attempt {attempt + 1}/{MAX_RETRIES})")
            async with websockets.connect(
                WEBSOCKET_ENDPOINT,
                ping_interval=30,
                ping_timeout=30,
                close_timeout=10
            ) as websocket:
                request_data = {
                    'image': image_data,
                    'threshold': threshold,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await websocket.send(json.dumps(request_data))
                logger.debug("Sent prediction request")

                try:
                    response = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=WEBSOCKET_TIMEOUT
                    )
                    logger.debug("Received prediction response")
                    return json.loads(response)
                except asyncio.TimeoutError:
                    logger.warning(f"Request timeout on attempt {attempt + 1}")
                    if attempt == MAX_RETRIES - 1:
                        return {
                            "error": f"Request timed out after {WEBSOCKET_TIMEOUT} seconds. Please try again."
                        }
                    continue

        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket error on attempt {attempt + 1}: {str(e)}")
            if attempt == MAX_RETRIES - 1:
                return {
                    "error": "Connection failed. Please check your connection and try again."
                }
            await asyncio.sleep(RETRY_DELAY)
        except Exception as e:
            logger.error(f"Unexpected error on attempt {attempt + 1}: {str(e)}", exc_info=True)
            return {
                "error": "An unexpected error occurred. Please try again."
            }
        finally:
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Prediction request attempt {attempt + 1} completed in {duration:.2f}s")

def render_predictions(results: Dict[str, Any]) -> None:
    if "error" in results:
        st.error(results["error"])
        return

    filtered = results.get("filtered_predictions", 0)
    total = results.get("total_predictions", 0)

    if filtered == 0:
        st.warning("No animals detected in this image above the confidence threshold.")
        return

    st.success(f"Found {filtered} predictions above threshold out of {total}")

    cols = st.columns(2)
    for idx, pred in enumerate(results.get("predictions", [])):
        with cols[idx % 2]:
            confidence = float(pred["score"]) * 100
            emoji = "🟢" if confidence >= 80 else "🟡" if confidence >= 50 else "🟠"
            st.write(f"{emoji} **{pred['label']}**")
            st.progress(pred["score"])
            st.caption(f"Confidence: {confidence:.1f}%")

def main():
    st.title(" 💻 Real-time Animal Classifier For Mobile And Edge Devices")

    if 'last_health_check' not in st.session_state:
        st.session_state.last_health_check = datetime.now()
        health = asyncio.run(check_backend_health())
        st.session_state.backend_status = health is not None

    if (datetime.now() - st.session_state.last_health_check).seconds > 30:
        health = asyncio.run(check_backend_health())
        st.session_state.backend_status = health is not None
        st.session_state.last_health_check = datetime.now()

    status = "🟢 Online" if st.session_state.backend_status else "🔴 Offline"
    st.sidebar.markdown(f"**System Status:** {status}")

    st.header("Upload an Image")
    uploaded_file = st.file_uploader(
        "Choose an image...",
        type=["jpg", "jpeg", "png"],
        help=f"Maximum file size: {MAX_FILE_SIZE_MB}MB"
    )
    threshold = st.slider(
        "Confidence Threshold",
        0.1, 0.9, DEFAULT_THRESHOLD,
        0.01,
        help="Adjust the minimum confidence threshold for predictions"
    )

    if uploaded_file is not None:
        if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            st.error(f"File size exceeds {MAX_FILE_SIZE_MB} MB limit.")
            return

        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="Uploaded Image", use_column_width=True)

            with st.spinner('Processing image...'):
                image_data, original_size = process_image(image)
            
            with st.spinner('Getting prediction...'):
                results = asyncio.run(get_prediction(image_data, threshold))
            
            render_predictions(results)
        
        except Exception as e:
            st.error("An error occurred while processing the image.")
            logger.error(f"Processing error: {e}", exc_info=True)
        finally:
            if 'image' in locals():
                image.close()

if __name__ == "__main__":
    main()
