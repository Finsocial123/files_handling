import aiohttp
import aiofiles
import tempfile
import os
from urllib.parse import urlparse, parse_qs
import logging
import mimetypes
from functools import lru_cache
from typing import Tuple

logger = logging.getLogger(__name__)

class URLProcessor:
    def __init__(self):
        self.supported_content_types = {
            # Documents
            'application/pdf': '.pdf',
            'application/msword': '.doc',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/vnd.oasis.opendocument.text': '.odt',
            'text/plain': '.txt',
            'text/rtf': '.rtf',
            
            # Markdown & Documentation
            'text/markdown': '.md',
            'text/x-rst': '.rst',
            'application/x-tex': '.tex',
            
            # Presentations
            'application/vnd.ms-powerpoint': '.ppt',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
            'application/vnd.oasis.opendocument.presentation': '.odp',
            
            # Spreadsheets
            'application/vnd.ms-excel': '.xls',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': '.xlsx',
            'text/csv': '.csv',
            'application/vnd.oasis.opendocument.spreadsheet': '.ods',
            
            # Web & Data
            'text/html': '.html',
            'application/json': '.json',
            'application/xml': '.xml',
            'application/yaml': '.yaml',
            'application/toml': '.toml',
            
            # Code
            'text/x-python': '.py',
            'application/javascript': '.js',
            'text/x-java': '.java',
            'text/x-c': '.c',
            'text/x-c++': '.cpp',
            
            # Archives
            'application/zip': '.zip',
            'application/x-tar': '.tar',
            'application/x-gzip': '.gz',
            'application/x-7z-compressed': '.7z',
            'application/x-rar-compressed': '.rar',
            
            # Others
            'application/x-ipynb+json': '.ipynb'
        }
        # Create a session pool
        self.session = None
        
    async def get_session(self):
        if self.session is None or self.session.closed:
            # TCP connection pooling with generous limits
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)
            timeout = aiohttp.ClientTimeout(total=60, connect=10)
            self.session = aiohttp.ClientSession(
                connector=connector, 
                timeout=timeout,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            )
        return self.session

    @lru_cache(maxsize=128)
    def is_valid_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    @lru_cache(maxsize=64)
    def _convert_dropbox_url(self, url: str) -> str:
        """Convert Dropbox shared link to direct download link"""
        if 'dropbox.com' in url:
            # Handle different Dropbox URL formats
            if 'dl=0' in url:
                return url.replace('dl=0', 'dl=1')
            elif '?dl=0' not in url and '?raw=1' not in url:
                return url + '?dl=1'
        return url

    async def download_file(self, url: str) -> Tuple[str, str]:
        """Downloads file from URL and returns (file_path, filename) asynchronously"""
        try:
            # Convert URL if it's a Dropbox link
            download_url = self._convert_dropbox_url(url)
            logger.debug(f"Downloading from URL: {download_url}")

            session = await self.get_session()
            async with session.get(download_url, allow_redirects=True) as response:
                response.raise_for_status()
                content = await response.read()

                # Verify content
                if len(content) < 100:  # Suspicious if file is too small
                    logger.warning(f"Downloaded content suspiciously small: {len(content)} bytes")
                    raise ValueError("Downloaded file appears to be invalid")

                # Check if content starts with PDF signature
                if content.startswith(b'%PDF'):
                    extension = '.pdf'
                else:
                    # Get content type and extension
                    content_type = response.headers.get('content-type', '').split(';')[0]
                    extension = self.supported_content_types.get(content_type, '.txt')
                    logger.debug(f"Content type: {content_type}, selected extension: {extension}")

                # Generate filename
                url_path = urlparse(url).path
                base_filename = os.path.basename(url_path)
                filename = base_filename if base_filename else 'document'
                if not os.path.splitext(filename)[1]:
                    filename += extension

                # Save to temp file asynchronously
                temp_dir = tempfile.mkdtemp()
                file_path = os.path.join(temp_dir, filename)
                
                logger.debug(f"Saving file to: {file_path}")
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(content)

                # Verify file was written
                if not os.path.exists(file_path) or os.path.getsize(file_path) < 100:
                    raise ValueError("File not saved correctly")

                return file_path, filename

        except aiohttp.ClientError as e:
            logger.error(f"Error downloading file: {str(e)}", exc_info=True)
            raise ValueError(f"Failed to download file: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            raise ValueError(f"Error processing URL: {str(e)}")
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
