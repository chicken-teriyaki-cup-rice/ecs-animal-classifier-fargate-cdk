# Use platform specification for AWS compatibility
FROM --platform=linux/amd64 python:3.9-slim

# Set environment variables to prevent .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set the working directory
WORKDIR /app

# Install system dependencies required for image processing
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy only the requirements file first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Run the FastAPI application with Uvicorn, enabling WebSocket support
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--ws", "auto", "--ws-ping-interval", "20", "--ws-ping-timeout", "20"]
