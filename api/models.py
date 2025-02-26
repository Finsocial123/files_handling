from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Union

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    response: str

class URLRequest(BaseModel):
    url: HttpUrl
