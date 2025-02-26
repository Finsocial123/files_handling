from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import tempfile
import os
import logging
import time
import asyncio
from typing import Dict, Optional
import aiofiles
from .document_processor import DocumentProcessor
from .models import ChatResponse, ChatRequest
from .session_store import SessionStore
from .url_processor import URLProcessor
from .models import URLRequest

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance tracking middleware
class PerformanceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        logger.info(f"Request to {request.url.path} processed in {process_time:.4f} seconds")
        return response

# Initialize FastAPI with optimized settings
app = FastAPI(
    title="Document Chat API",
    description="API for processing and chatting with documents",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add performance middleware
app.add_middleware(PerformanceMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize session store
session_store = SessionStore()

# Add URL processor with dependency
async def get_url_processor():
    url_processor = URLProcessor()
    try:
        yield url_processor
    finally:
        await url_processor.close()

# Request rate limiter
request_counts: Dict[str, Dict[str, float]] = {}
MAX_REQUESTS_PER_MINUTE = 60

async def rate_limit(request: Request):
    client_ip = request.client.host
    current_time = time.time()
    
    if client_ip not in request_counts:
        request_counts[client_ip] = {}
    
    # Clean up old timestamps
    request_counts[client_ip] = {
        ts: t for ts, t in request_counts[client_ip].items()
        if current_time - t < 60  # Only keep last minute
    }
    
    if len(request_counts[client_ip]) >= MAX_REQUESTS_PER_MINUTE:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(status_code=429, detail="Too many requests")
    
    request_id = str(time.time())
    request_counts[client_ip][request_id] = current_time

# Clean temporary files in background
async def cleanup_temp_file(file_path: str):
    try:
        await asyncio.sleep(300)  # Wait 5 minutes before cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp file: {str(e)}")

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    _: None = Depends(rate_limit)
):
    start_time = time.time()
    try:
        processor = DocumentProcessor()
        
        # Validate file type
        if not processor.is_supported_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Supported types: {', '.join(processor.supported_extensions)}"
            )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = os.path.join(temp_dir, file.filename)
            
            # Save uploaded file asynchronously
            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)
            
            # Process document asynchronously
            session_id = await processor.process_file(file_path)
            
            # Save session asynchronously
            await session_store.save_session(session_id, processor)
            
            # Add background cleanup task
            if background_tasks:
                background_tasks.add_task(cleanup_temp_file, file_path)
            
            process_time = time.time() - start_time
            logger.info(f"Document processed in {process_time:.2f} seconds")
            
            return {
                "session_id": session_id,
                "message": f"Document {file.filename} processed successfully",
                "file_type": os.path.splitext(file.filename)[1].lower(),
                "process_time_seconds": process_time
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error in upload: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-url")
async def process_url(
    request: URLRequest,
    url_processor: URLProcessor = Depends(get_url_processor),
    background_tasks: BackgroundTasks = None,
    _: None = Depends(rate_limit)
):
    start_time = time.time()
    try:
        # Download file from URL asynchronously
        file_path, filename = await url_processor.download_file(str(request.url))
        
        # Process document asynchronously
        processor = DocumentProcessor()
        session_id = await processor.process_file(file_path)
        
        # Save session asynchronously
        await session_store.save_session(session_id, processor)
        
        # Add background cleanup task
        if background_tasks:
            background_tasks.add_task(cleanup_temp_file, file_path)
        
        process_time = time.time() - start_time
        logger.info(f"URL processed in {process_time:.2f} seconds")
        
        return {
            "session_id": session_id, 
            "message": f"Document {filename} processed successfully",
            "source_url": str(request.url),
            "process_time_seconds": process_time
        }
    except Exception as e:
        logger.error(f"Error processing URL: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/{session_id}", response_model=ChatResponse)
async def chat(
    session_id: str, 
    request: ChatRequest,
    _: None = Depends(rate_limit)
):
    start_time = time.time()
    
    # Load session asynchronously
    processor = await session_store.load_session(session_id)
    if not processor:
        logger.error(f"Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    try:
        if not processor.index:
            logger.error("No index found in processor")
            raise ValueError("Document index not initialized")
        
        # Process query asynchronously
        response = await processor.query_document(request.query)
        if not response or not response.response:
            logger.error("Empty response from query engine")
            raise ValueError("Empty response from query engine")
        
        process_time = time.time() - start_time
        logger.info(f"Chat query processed in {process_time:.2f} seconds")
            
        return ChatResponse(response=str(response.response))
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    if session_store.delete_session(session_id):
        return {"message": "Session deleted successfully"}
    raise HTTPException(status_code=404, detail="Session not found")


