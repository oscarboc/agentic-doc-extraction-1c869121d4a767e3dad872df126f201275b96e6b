from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ParseDocumentResponse(BaseModel):
    document_id: str
    filename: str
    content_type: str | None
    size_bytes: int
    stored_path: str
    created_at: datetime
    provider: str
    model: str
    chunk_count: int
    chunks: list[dict[str, Any]]
    markdown: str
    json_output_path: str
    markdown_output_path: str
