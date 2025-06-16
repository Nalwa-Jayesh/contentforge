from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import uuid

class ContentStatus(Enum):
    SCRAPED = "scraped"
    AI_WRITTEN = "ai_written"
    AI_REVIEWED = "ai_reviewed"
    HUMAN_REVIEW = "human_review"
    HUMAN_EDITED = "human_edited"
    FINALIZED = "finalized"
    PUBLISHED = "published"

class AgentType(Enum):
    SCRAPER = "scraper"
    AI_WRITER = "ai_writer"
    AI_REVIEWER = "ai_reviewer"
    HUMAN_WRITER = "human_writer"
    HUMAN_REVIEWER = "human_reviewer"
    HUMAN_EDITOR = "human_editor"
    SYSTEM = "system"

@dataclass
class ContentVersion:
    """Represents a version of content at a specific stage"""
    id: str
    chapter_id: str
    content: str
    status: ContentStatus
    agent_type: AgentType
    metadata: Dict[str, Any]
    created_at: datetime
    parent_version_id: Optional[str] = None
    
    def __post_init__(self):
        """Ensure ID is properly set and metadata is serializable"""
        if not self.id:
            self.id = str(uuid.uuid4())
        if not isinstance(self.id, str):
            self.id = str(self.id)
            
        # Ensure metadata is serializable
        self.metadata = self._make_serializable(self.metadata)
    
    def _make_serializable(self, data: Any) -> Any:
        """Convert data to JSON serializable format"""
        if isinstance(data, dict):
            return {k: self._make_serializable(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._make_serializable(item) for item in data]
        elif isinstance(data, datetime):
            return data.isoformat()
        elif isinstance(data, (ContentStatus, AgentType)):
            return data.value
        return data
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        return self._make_serializable(data)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ContentVersion':
        """Create instance from dictionary"""
        # Ensure ID is a string
        if 'id' in data and data['id'] is not None:
            data['id'] = str(data['id'])
            
        # Convert datetime string back to datetime object
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
            
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            chapter_id=data['chapter_id'],
            content=data['content'],
            status=ContentStatus(data['status']),
            agent_type=AgentType(data['agent_type']),
            metadata=data['metadata'],
            created_at=data['created_at'],
            parent_version_id=data.get('parent_version_id')
        )
    
    def get_content_hash(self) -> str:
        """Generate hash of content for comparison"""
        import hashlib
        return hashlib.md5(self.content.encode()).hexdigest()

@dataclass
class ReviewRequest:
    """Represents a human review request"""
    id: str
    chapter_id: str
    version: ContentVersion
    review_type: str
    submitted_at: datetime
    status: str = 'pending'
    reviewer_notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'chapter_id': self.chapter_id,
            'version': self.version.to_dict(),
            'review_type': self.review_type,
            'submitted_at': self.submitted_at.isoformat(),
            'status': self.status,
            'reviewer_notes': self.reviewer_notes
        }