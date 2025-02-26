import os
import json
import pickle
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import logging
from typing import Dict, Optional, List
import aiofiles
import aiofiles.os
from functools import lru_cache
import time

logger = logging.getLogger(__name__)

class SessionStore:
    def __init__(self, base_dir=None, max_sessions_per_ip=5, session_timeout_hours=24):
        if base_dir is None:
            # Use relative path from current file
            current_dir = Path(__file__).parent.parent
            self.base_dir = current_dir / "data" / "sessions"
        else:
            self.base_dir = Path(base_dir)
        
        # Create directory if it doesn't exist
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            # Fallback to temp directory if creation fails
            import tempfile
            self.base_dir = Path(tempfile.gettempdir()) / "chatwithfiles_data" / "sessions"
            self.base_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_sessions_per_ip = max_sessions_per_ip
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self.ip_sessions: Dict[str, list] = {}
        self._session_cache: Dict[str, tuple] = {}  # Cache for session data (processor, timestamp)
        self._max_cache_size = 50  # Maximum number of sessions to keep in memory
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_old_sessions())
        
    def _get_session_path(self, session_id):
        return self.base_dir / f"{session_id}.pkl"
        
    def _get_metadata_path(self, session_id):
        return self.base_dir / f"{session_id}_meta.json"
    
    async def _cleanup_old_sessions(self):
        """Periodically clean up old sessions"""
        while True:
            try:
                now = datetime.now()
                # Clean memory cache first
                expired_keys = []
                for session_id, (_, timestamp) in self._session_cache.items():
                    if (now - timestamp) > self.session_timeout:
                        expired_keys.append(session_id)
                
                for key in expired_keys:
                    if key in self._session_cache:
                        del self._session_cache[key]
                
                # Then clean disk storage
                meta_files = list(self.base_dir.glob("*_meta.json"))
                for meta_file in meta_files:
                    try:
                        async with aiofiles.open(meta_file, 'r') as f:
                            metadata = json.loads(await f.read())
                        last_accessed = datetime.fromisoformat(metadata["last_accessed"])
                        
                        if now - last_accessed > self.session_timeout:
                            session_id = metadata["session_id"]
                            await self.delete_session(session_id)
                            logger.info(f"Cleaned up expired session: {session_id}")
                    except Exception as e:
                        logger.error(f"Error cleaning up session: {str(e)}")
                            
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
                
            # Run cleanup every hour
            await asyncio.sleep(3600)
    
    async def save_session(self, session_id: str, processor, ip_address: str = None):
        """Save session with IP tracking asynchronously"""
        # Check IP session limit
        if ip_address:
            ip_sessions = self.ip_sessions.get(ip_address, [])
            if len(ip_sessions) >= self.max_sessions_per_ip:
                # Remove oldest session for this IP
                oldest_session = ip_sessions[0]
                await self.delete_session(oldest_session)
                ip_sessions.pop(0)
            
            ip_sessions.append(session_id)
            self.ip_sessions[ip_address] = ip_sessions

        # Save to memory cache
        self._session_cache[session_id] = (processor, datetime.now())
        
        # If cache is too large, remove least recently used items
        if len(self._session_cache) > self._max_cache_size:
            oldest_key = min(self._session_cache, key=lambda k: self._session_cache[k][1])
            del self._session_cache[oldest_key]

        # Save processor and metadata to disk
        async with aiofiles.open(self._get_session_path(session_id), 'wb') as f:
            await f.write(pickle.dumps(processor))
        
        metadata = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat(),
            "ip_address": ip_address
        }
        async with aiofiles.open(self._get_metadata_path(session_id), 'w') as f:
            await f.write(json.dumps(metadata))
    
    async def load_session(self, session_id):
        """Load session data if exists"""
        # Check memory cache first
        if session_id in self._session_cache:
            processor, _ = self._session_cache[session_id]
            self._session_cache[session_id] = (processor, datetime.now())  # Update access time
            return processor
            
        session_path = self._get_session_path(session_id)
        logger.debug(f"Attempting to load session from disk: {session_path}")
        
        if not session_path.exists():
            logger.error(f"Session file not found: {session_path}")
            return None
            
        try:
            # Load processor from disk
            async with aiofiles.open(session_path, 'rb') as f:
                processor = pickle.loads(await f.read())
                
            # Verify processor state
            if not hasattr(processor, 'index') or processor.index is None:
                logger.error("Loaded processor has no index")
                return None
            
            # Update memory cache
            self._session_cache[session_id] = (processor, datetime.now())
                
            # Update last accessed time
            metadata_path = self._get_metadata_path(session_id)
            if metadata_path.exists():
                async with aiofiles.open(metadata_path, 'r') as f:
                    metadata = json.loads(await f.read())
                metadata["last_accessed"] = datetime.now().isoformat()
                async with aiofiles.open(metadata_path, 'w') as f:
                    await f.write(json.dumps(metadata))
                    
            logger.debug(f"Successfully loaded session: {session_id}")
            return processor
        except Exception as e:
            logger.error(f"Error loading session: {str(e)}", exc_info=True)
            return None
    
    async def delete_session(self, session_id):
        """Delete session data and metadata"""
        try:
            # Remove from memory cache
            if session_id in self._session_cache:
                del self._session_cache[session_id]
                
            # Remove from disk
            session_path = self._get_session_path(session_id)
            meta_path = self._get_metadata_path(session_id)
            
            if session_path.exists():
                await aiofiles.os.remove(session_path)
            if meta_path.exists():
                await aiofiles.os.remove(meta_path)
                
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}")
            return False
    
    @lru_cache(maxsize=1)  # Cache results for a short time
    def _list_sessions_cached(self, cache_key):
        """List all active sessions with metadata (cached version)"""
        sessions = []
        for meta_file in self.base_dir.glob("*_meta.json"):
            try:
                with open(meta_file, 'r') as f:
                    sessions.append(json.load(f))
            except Exception:
                pass
        return sessions
    
    async def list_sessions(self):
        """List all active sessions with metadata asynchronously"""
        # Use cache key based on time (refresh every minute)
        cache_key = int(time.time() / 60)
        return await asyncio.to_thread(self._list_sessions_cached, cache_key)

    def get_sessions_for_ip(self, ip_address: str) -> list:
        """Get all sessions for an IP address"""
        return self.ip_sessions.get(ip_address, [])
