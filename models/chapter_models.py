from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from .content_models import ContentVersion

class TaskStatus(Enum):
    """Status of a chapter task"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class PublicationPhase(Enum):
    """Publication phases for a chapter"""
    RESEARCH = "research"
    DRAFTING = "drafting"
    SPINNING = "spinning"
    REVIEW = "review"
    HUMAN_REVIEW = "human_review"
    FINALIZATION = "finalization"
    PUBLICATION = "publication"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ChapterTask:
    """Represents a task for a chapter"""
    id: str
    chapter_id: str
    task_type: str
    status: TaskStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def complete(self) -> None:
        """Mark task as completed"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
    
    def fail(self) -> None:
        """Mark task as failed"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
    
    def cancel(self) -> None:
        """Cancel the task"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()

@dataclass
class Chapter:
    """Represents a book chapter with all its versions"""
    id: str
    title: str
    url: str
    original_content: str
    current_version: ContentVersion
    versions: List[ContentVersion]
    description: str = ""
    target_length: int = 0
    keywords: List[str] = None
    research_sources: List[str] = None
    current_phase: PublicationPhase = PublicationPhase.RESEARCH
    research_version_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.keywords is None:
            self.keywords = []
        if self.research_sources is None:
            self.research_sources = []
    
    def add_version(self, version: ContentVersion) -> None:
        """Add a new version to the chapter"""
        self.versions.append(version)
        self.current_version = version
    
    def get_version_by_id(self, version_id: str) -> Optional[ContentVersion]:
        """Get a specific version by ID"""
        for version in self.versions:
            if version.id == version_id:
                return version
        return None
    
    def get_versions_by_status(self, status: str) -> List[ContentVersion]:
        """Get all versions with a specific status"""
        from .content_models import ContentStatus
        target_status = ContentStatus(status)
        return [v for v in self.versions if v.status == target_status]
    
    def get_latest_human_version(self) -> Optional[ContentVersion]:
        """Get the most recent human-edited version"""
        from .content_models import AgentType
        human_versions = [v for v in self.versions 
                         if v.agent_type in [AgentType.HUMAN_WRITER, 
                                           AgentType.HUMAN_REVIEWER, 
                                           AgentType.HUMAN_EDITOR]]
        return max(human_versions, key=lambda x: x.created_at) if human_versions else None
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get a summary of the chapter's current status"""
        return {
            'chapter_id': self.id,
            'title': self.title,
            'current_status': self.current_version.status.value,
            'current_agent': self.current_version.agent_type.value,
            'total_versions': len(self.versions),
            'has_screenshot': self.screenshot_path is not None,
            'last_updated': self.current_version.created_at.isoformat(),
            'version_history': [
                {
                    'version_id': v.id,
                    'status': v.status.value,
                    'agent': v.agent_type.value,
                    'created_at': v.created_at.isoformat()
                }
                for v in self.versions
            ]
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chapter to dictionary for serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'url': self.url,
            'original_content': self.original_content,
            'current_version': self.current_version.to_dict(),
            'versions': [v.to_dict() for v in self.versions],
            'screenshot_path': self.screenshot_path,
            'metadata': self.metadata or {}
        }

@dataclass
class Book:
    """Represents a complete book with multiple chapters"""
    id: str
    title: str
    author: str
    chapters: Dict[str, Chapter]
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
    
    def add_chapter(self, chapter: Chapter) -> None:
        """Add a chapter to the book"""
        self.chapters[chapter.id] = chapter
    
    def get_chapter(self, chapter_id: str) -> Optional[Chapter]:
        """Get a chapter by ID"""
        return self.chapters.get(chapter_id)
    
    def get_all_chapters(self) -> List[Chapter]:
        """Get all chapters sorted by ID"""
        return [self.chapters[key] for key in sorted(self.chapters.keys())]
    
    def get_completion_status(self) -> Dict[str, Any]:
        """Get overall completion status of the book"""
        from .content_models import ContentStatus
        
        total_chapters = len(self.chapters)
        if total_chapters == 0:
            return {'total': 0, 'completed': 0, 'percentage': 0}
        
        finalized_chapters = sum(1 for chapter in self.chapters.values() 
                               if chapter.current_version.status == ContentStatus.FINALIZED)
        
        published_chapters = sum(1 for chapter in self.chapters.values() 
                               if chapter.current_version.status == ContentStatus.PUBLISHED)
        
        return {
            'total_chapters': total_chapters,
            'finalized_chapters': finalized_chapters,
            'published_chapters': published_chapters,
            'finalized_percentage': (finalized_chapters / total_chapters) * 100,
            'published_percentage': (published_chapters / total_chapters) * 100
        }