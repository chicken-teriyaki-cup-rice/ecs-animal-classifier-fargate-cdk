import base64
import io
import logging
import os
from typing import Any, Dict, Optional

import tensorflow as tf
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from starlette.websockets import WebSocketState

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("animal-classifier-backend")

app = FastAPI(title="Animal Classifier API")

# Get allowed origins from environment or use defaults
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")
if not ALLOWED_ORIGINS or ALLOWED_ORIGINS[0] == "":
    ALLOWED_ORIGINS = [
        "https://isthisasquirrel.com",
        "https://www.isthisasquirrel.com",
        "https://frontend.isthisasquirrel.com",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]

# Enhanced CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Upgrade", "Connection"],  # Add WebSocket headers
    expose_headers=["*"],
    max_age=3600,
)

# Global variables for model
model: Optional[tf.keras.Model] = None
image_size = (224, 224)

@app.on_event("startup")
async def load_model():
    """Initialize the model on startup."""
    global model
    
    logger.info("Loading MobileNetV2 model...")
    
    try:
        model = tf.keras.applications.MobileNetV2(
            input_shape=(224, 224, 3),
            include_top=True,
            weights='imagenet'
        )
        
        # Warmup
        test_tensor = tf.zeros((1, 224, 224, 3))
        _ = model(test_tensor)
        
        logger.info("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}", exc_info=True)
        raise

def process_image(image_bytes: bytes) -> tf.Tensor:
    """Process the input image bytes for model prediction."""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        image = image.resize(image_size, Image.Resampling.LANCZOS)
        img_array = tf.keras.preprocessing.image.img_to_array(image)
        img_array = tf.expand_dims(img_array, 0)
        return tf.keras.applications.mobilenet_v2.preprocess_input(img_array)
    except Exception as e:
        logger.error(f"Image processing error: {e}", exc_info=True)
        raise

async def handle_prediction(image_tensor: tf.Tensor, threshold: float) -> Dict[str, Any]:
    """Handle the prediction logic."""
    try:
        predictions = model(image_tensor)
        probs = tf.nn.softmax(predictions)
        
        top_k_values, top_k_indices = tf.nn.top_k(probs[0], k=5)
        
        scores = top_k_values.numpy().tolist()
        indices = top_k_indices.numpy().tolist()
        
        labels = [
            tf.keras.applications.mobilenet_v2.decode_predictions(predictions, top=1)[0][i][1]
            for i in range(len(indices))
        ]
        
        filtered_predictions = [
            {"label": label, "score": float(score)}
            for label, score in zip(labels, scores)
            if score >= threshold
        ]
        
        return {
            "predictions": filtered_predictions,
            "total_predictions": len(scores),
            "filtered_predictions": len(filtered_predictions)
        }
    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        raise

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time image classification."""
    try:
        # Log connection attempt with origin
        client_host = websocket.client.host
        logger.info(f"WebSocket connection attempt from {client_host}")
        
        # Check origin
        origin = websocket.headers.get("origin", "")
        if origin and origin not in ALLOWED_ORIGINS:
            logger.warning(f"Rejected WebSocket connection from unauthorized origin: {origin}")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
            
        # Accept the connection
        await websocket.accept()
        logger.info(f"WebSocket connection accepted from {client_host}")

        while True:
            try:
                # Receive data
                data = await websocket.receive_json()
                logger.info(f"Received data from {client_host}")
                
                # Extract and validate image data
                image_data = data.get('image')
                if not image_data:
                    raise ValueError("Invalid or missing 'image' data")

                # Parse threshold
                threshold = float(data.get('threshold', 0.0))
                
                # Process base64 image
                if ',' in image_data:
                    _, encoded = image_data.split(',', 1)
                else:
                    encoded = image_data
                    
                image_bytes = base64.b64decode(encoded)
                
                # Process image and get predictions
                img_tensor = process_image(image_bytes)
                result = await handle_prediction(img_tensor, threshold)
                
                # Send results
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json(result)
                    logger.info(f"Sent {result['filtered_predictions']} predictions to {client_host}")

            except ValueError as e:
                logger.error(f"Value error from {client_host}: {e}")
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"error": str(e)})
                
            except Exception as e:
                logger.error(f"Error processing request from {client_host}: {e}", exc_info=True)
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.send_json({"error": "Internal server error"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket connection closed by client: {client_host}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_host}: {e}", exc_info=True)
    finally:
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.close()
            logger.info(f"WebSocket connection closed for {client_host}")

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model_loaded": model is not None,
        "allowed_origins": ALLOWED_ORIGINS
    }

# Add OPTIONS endpoint for WebSocket path
@app.options("/ws")
async def websocket_options():
    """Handle OPTIONS requests for WebSocket endpoint."""
    return JSONResponse(
        status_code=200,
        content={"message": "WebSocket connection allowed"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS, CONNECT",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Max-Age": "3600",
        },
    )

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware to log all requests."""
    logger.info(f"Request: {request.method} {request.url}")
    logger.info(f"Client Host: {request.client.host}")
    logger.info(f"Headers: {request.headers}")
    
    response = await call_next(request)
    return response