import uuid
import asyncio
from functools import lru_cache
from llama_index.core import VectorStoreIndex, Settings, SimpleDirectoryReader
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from pygments.lexers import get_lexer_for_filename
from dataclasses import dataclass
import os
from typing import Set, Dict, List, Any
import logging
from time import time

logger = logging.getLogger(__name__)

@dataclass
class QueryResponse:
    response: str
    source_nodes: list
    is_code: bool
    language: str = "python"
    response_time: float = 0.0

class DocumentProcessor:
    def __init__(self):
        # Configure Ollama with optimized settings
        Settings.llm = Ollama(
            model="pawan941394/HindAI:latest",
            request_timeout=60.0,  # Reduced timeout
            temperature=0.1,
            context_window=3900,
            base_url="https://sunny-gerri-finsocialdigitalsystem-d9b385fa.koyeb.app",
            additional_kwargs={
                "seed": 42,
                "num_predict": 128,
                "top_k": 20,
                "top_p": 0.9,
                "mirostat_mode": 2,
                "mirostat_tau": 5.0,
                "mirostat_eta": 0.1,
            }
        )

        # Configure embeddings with optimized batch size
        Settings.embed_model = HuggingFaceEmbedding(
            model_name="sentence-transformers/all-mpnet-base-v2",
            embed_batch_size=32  # Optimized batch size
        )

        # Optimized chunking settings
        Settings.chunk_size = 512
        Settings.chunk_overlap = 50
        
        self.index = None
        self.__setstate__(self.__getstate__())
        
        # Add supported file types
        self.supported_extensions: Set[str] = {
            # Documents
            '.pdf', '.docx', '.doc', '.txt', '.rtf', '.odt',
            # Markdown & Documentation
            '.md', '.rst', '.tex',
            # Emails
            '.eml', '.msg', '.mbox',
            # Presentations
            '.pptx', '.ppt', '.odp',
            # Spreadsheets
            '.xlsx', '.xls', '.csv', '.ods',
            # Code & Data files
            '.py', '.js', '.java', '.cpp', '.c', '.cs', '.html',
            '.css', '.php', '.rb', '.go', '.rs', '.swift', '.kt', '.ts',
            '.json', '.xml', '.yaml', '.yml', '.toml', '.ini',
            # E-books
            '.epub', '.mobi',
            # Archives
            '.zip', '.tar', '.gz', '.7z', '.rar',
            # Web
            '.html', '.htm', '.mht', '.mhtml',
            # Database
            '.sqlite', '.db',
            # Others
            '.ipynb'
        }
        
        # Add response cache
        self._response_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_size = 100
    
    def __getstate__(self):
        """Support for pickle serialization"""
        state = self.__dict__.copy()
        return state
    
    def __setstate__(self, state):
        """Support for pickle deserialization"""
        self.__dict__.update(state)

    @lru_cache(maxsize=64)
    def is_code_file(self, filename):
        code_extensions = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.html', '.css'}
        return os.path.splitext(filename)[1].lower() in code_extensions

    @lru_cache(maxsize=128)
    def is_supported_file(self, filename: str) -> bool:
        """Check if file type is supported with caching"""
        ext = os.path.splitext(filename)[1].lower()
        return ext in self.supported_extensions

    async def process_file(self, file_path: str) -> str:
        """Process file asynchronously and return session ID"""
        if not self.is_supported_file(file_path):
            raise ValueError(f"Unsupported file type. Supported types: {', '.join(self.supported_extensions)}")
        
        try:
            # Verify file exists and is readable
            if not os.path.exists(file_path):
                raise ValueError(f"File not found: {file_path}")
            
            if os.path.getsize(file_path) < 100:
                raise ValueError("File appears to be empty or invalid")

            logger.debug(f"Processing file: {file_path}")
            reader = SimpleDirectoryReader(
                input_dir=os.path.dirname(file_path),
                filename_as_id=True,
                recursive=False
            )
            
            # Run in a thread pool to not block
            documents = await asyncio.to_thread(reader.load_data)
            if not documents:
                raise ValueError("No content could be extracted from the file")
            
            logger.debug(f"Loaded {len(documents)} documents")
            
            # Add metadata
            for doc in documents:
                if self.is_code_file(file_path):
                    try:
                        lexer = get_lexer_for_filename(file_path)
                        doc.metadata["is_code"] = True
                        doc.metadata["language"] = lexer.aliases[0]
                    except:
                        doc.metadata["is_code"] = False

            # Create index in a non-blocking way
            self.index = await asyncio.to_thread(
                VectorStoreIndex.from_documents,
                documents,
                show_progress=True
            )
            
            if not self.index:
                raise ValueError("Failed to create document index")
                
            return str(uuid.uuid4())
            
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to process document: {str(e)}")

    async def query_document(self, query: str) -> QueryResponse:
        logger.debug(f"Processing query: {query}")
        
        if not self.index:
            logger.error("No document index available")
            raise ValueError("No document has been processed")

        # Check cache first
        cache_key = query.strip().lower()
        if cache_key in self._response_cache:
            logger.debug(f"Cache hit for query: {cache_key[:30]}...")
            cached = self._response_cache[cache_key]
            return QueryResponse(**cached)

        start_time = time()
        try:
            query_engine = self.index.as_query_engine(
                similarity_top_k=3,
                response_mode="compact"
            )
            
            # Execute query in a non-blocking way
            response = await asyncio.to_thread(query_engine.query, query)
            
            if not response or not str(response).strip():
                logger.error("Empty response from query engine")
                raise ValueError("Query engine returned empty response")
            
            is_code = any(doc.metadata.get("is_code", False) for doc in response.source_nodes)
            language = response.source_nodes[0].metadata.get("language", "python") if is_code else "python"
            
            end_time = time()
            response_time = end_time - start_time
            
            logger.debug(f"Query response generated in {response_time:.2f}s: {str(response)[:100]}...")
            
            result = QueryResponse(
                response=str(response),
                source_nodes=response.source_nodes,
                is_code=is_code,
                language=language,
                response_time=response_time
            )
            
            # Cache the result
            if len(self._response_cache) >= self._cache_size:
                # Remove a random item if cache is full
                self._response_cache.pop(next(iter(self._response_cache)))
                
            self._response_cache[cache_key] = {
                "response": str(response),
                "source_nodes": response.source_nodes,
                "is_code": is_code,
                "language": language,
                "response_time": response_time
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error querying document: {str(e)}", exc_info=True)
            raise
