from pydantic import BaseModel
from typing import List, Optional


# -----------------------------
# Query request schema
# -----------------------------
class QueryRequest(BaseModel):
    query: str


# -----------------------------
# Search result schema
# -----------------------------
class SearchResult(BaseModel):
    file_name: str
    chunk_text: str
    similarity_score: float


# -----------------------------
# Query response schema
# -----------------------------
class QueryResponse(BaseModel):
    query: str
    results: List[SearchResult]


# -----------------------------
# Upload response schema
# -----------------------------
class UploadResponse(BaseModel):
    message: str
    file_name: str
    chunks_indexed: int


# -----------------------------
# Timeline item schema
# -----------------------------
class TimelineItem(BaseModel):
    file_name: str
    timestamp: Optional[str]


# -----------------------------
# Timeline response schema
# -----------------------------
class TimelineResponse(BaseModel):
    items: List[TimelineItem]