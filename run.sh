#!/bin/bash
echo "Starting Document Chat API"
export PORT=${PORT:-8000}
export WORKERS=${WORKERS:-1}

echo "Serving on port $PORT with $WORKERS workers"
uvicorn api.main:app --host 0.0.0.0 --port $PORT --workers $WORKERS
