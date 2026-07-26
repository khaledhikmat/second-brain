from typing import Dict, List, Optional, Any
from pydantic import BaseModel

class SummarizerResult(BaseModel):
    """
    Represents the result of a summarization process.
    """
    category: str
    channel: str
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    concepts: Optional[List[str]] = None
    entities: Optional[Dict[str, List[str]]] = None
    summary: Optional[str] = None
    wikilinks: Optional[List[str]] = None
    content: Optional[str] = None
    translations: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None

