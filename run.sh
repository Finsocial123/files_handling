#!/bin/bash
echo "Starting Document Chat API"
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers ${WORKERS:-1}
