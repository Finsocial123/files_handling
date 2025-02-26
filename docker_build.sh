#!/bin/bash
set -e

echo "Building Docker image with verbose output..."
docker build --no-cache --progress=plain -t document-chat-api .

echo "Running the container to verify installation..."
docker run --rm document-chat-api python -c "import fastapi; import uvicorn; print('Imports successful')"

echo "Build and verification complete!"
