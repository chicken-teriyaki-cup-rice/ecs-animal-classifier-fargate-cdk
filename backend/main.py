import base64
import json
import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel
from torchvision import models, transforms

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
numeric_level = getattr(logging, log_level, logging.INFO)
logging.basicConfig(
    level=numeric_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("animal-classifier-backend")

app = FastAPI(title="Animal Classifier API")

allowed_origins = os.getenv("CORS_ORIGINS", "https://your-frontend-domain.com").split(",")
cors_config = {
    "origins": allowed_origins,
    "methods": ["*"],
    "headers": os.getenv("CORS_ALLOWED_HEADERS", "*").split(","),
    "credentials": True,
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_config["origins"],
    allow_credentials=cors_config["credentials"],
    allow_methods=cors_config["methods"],
    allow_headers=cors_config["headers"],
)

device = torch.device("cpu")
logger.info(f"Using device: {device}")

try:
    base_path = Path(__file__).parent
    class_file = base_path / "imagenet_class_index.json"
    if not class_file.exists():
        logger.error("imagenet_class_index.json is missing.")
    else:
        with open(class_file, "r") as f:
            class_idx = json.load(f)
        logger.debug(f"class_idx content: {class_idx}")
except Exception as e:
    logger.error(f"Error loading class labels: {e}")
    class_idx = {str(i): [f"class_{i}"] for i in range(1000)}

model: Optional[torch.nn.Module] = None
is_model_ready = False

preprocess = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(223),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.223, 0.225]),
])

@app.on_event("startup")
async def load_model():
    global model, is_model_ready
    logger.info("Starting model initialization...")
    try:
        model = models.mobilenet_v2(weights=models.MobileNet_V2_Weights.DEFAULT)
        model.eval()
        model.to(device)
        logger.info("Model loaded successfully")
        is_model_ready = True
    except Exception as e:
        logger.error(f"Failed to load model: {e}", exc_info=True)
        is_model_ready = False

@app.get("/health")
async def health_check():
    status = "healthy" if is_model_ready else "unhealthy"
    return {"status": status, "timestamp": datetime.utcnow().isoformat()}

class PredictionRequest(BaseModel):
    image: str
    threshold: float = 0.5

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")
    try:
        while True:
            data = await websocket.receive_text()
            request = json.loads(data)
            prediction_request = PredictionRequest(**request)
            response = await make_prediction(prediction_request)
            await websocket.send_text(json.dumps(response))
    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"Error during WebSocket communication: {e}", exc_info=True)
        await websocket.close()

async def make_prediction(prediction_request: PredictionRequest):
    if not is_model_ready:
        return {"error": "Model is not ready. Please try again later."}

    try:
        image_data = base64.b64decode(prediction_request.image.split(",")[1])
        image = Image.open(BytesIO(image_data)).convert("RGB")
        input_tensor = preprocess(image).unsqueeze(0).to(device)

        with torch.no_grad():
            outputs = model(input_tensor)
            probabilities = torch.nn.functional.softmax(outputs[0], dim=0)

        threshold = prediction_request.threshold
        predictions = []
        for idx, prob in enumerate(probabilities):
            prob_value = prob.item()
            if prob_value >= threshold:
                label = class_idx.get(str(idx), [f"class_{idx}"])[1]
                predictions.append({"label": label, "score": prob_value})

        predictions.sort(key=lambda x: x["score"], reverse=True)
        return {
            "predictions": predictions,
            "total_predictions": len(probabilities),
            "filtered_predictions": len(predictions),
        }
    except Exception as e:
        logger.error(f"Prediction error: {e}", exc_info=True)
        return {"error": "Failed to process the image. Please ensure it is a valid image."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), log_level=log_level.lower())
