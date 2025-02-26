#!/bin/bash
set -e

echo "Checking environment..."
python -c "import fastapi; print(f'FastAPI version: {fastapi.__version__}')"
python -c "import uvicorn; print(f'Uvicorn version: {uvicorn.__version__}')"

echo "Starting Document Chat API"
export PORT=${PORT:-8000}
export WORKERS=${WORKERS:-1}

echo "Serving on port $PORT with $WORKERS workers"
uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers $WORKERS
