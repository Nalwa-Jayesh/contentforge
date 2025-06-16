import asyncio
import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from models.content_models import ContentVersion, ContentStatus, AgentType
from models.chapter_models import Chapter, ChapterTask, TaskStatus, PublicationPhase
from storage.version_manager import VersionManager
from agents.web_scraper import WebScraper
from agents.llm_agent import LLMAgent
from agents.human_interface import HumanReviewInterface
from utils.logger import logger
from config import Config


class WorkflowPhase(Enum):
    """Workflow execution phases"""
    INITIALIZATION = "initialization"
    RESEARCH = "research"
    DRAFTING = "drafting"
    SPINNING = "spinning"
    REVIEW = "review"
    HUMAN_REVIEW = "human_review"
    FINALIZATION = "finalization"
    PUBLICATION = "publication"
    COMPLETED = "completed"
    FAILED = "failed"


class PublicationWorkflow:
    """Main workflow orchestrator for AI publication system"""
    
    def __init__(self):
        self.version_manager = VersionManager()
        self.web_scraper = WebScraper()
        self.llm_agent = LLMAgent()
        self.human_interface = HumanReviewInterface()
        
        # Workflow state
        self.current_phase = WorkflowPhase.INITIALIZATION
        self.active_chapters: Dict[str, Chapter] = {}
        self.workflow_stats = {
            'start_time': None,
            'total_chapters': 0,
            'completed_chapters': 0,
            'failed_chapters': 0,
            'phase_times': {}
        }
        
        logger.info("Publication workflow initialized")
    
    async def start_publication(self, publication_config: Dict[str, Any]) -> bool:
        """
        Start the publication workflow
        
        Args:
            publication_config: Configuration for the publication
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.workflow_stats['start_time'] = datetime.now()
            logger.info(f"Starting publication workflow: {publication_config.get('title', 'Untitled')}")
            
            # Initialize chapters from config
            chapters = await self._initialize_chapters(publication_config)
            if not chapters:
                logger.error("No chapters initialized")
                return False
            
            # Execute workflow phases
            success = await self._execute_workflow(chapters)
            
            # Log final statistics
            self._log_workflow_stats()
            
            return success
            
        except Exception as e:
            logger.error(f"Error in publication workflow: {str(e)}")
            self.current_phase = WorkflowPhase.FAILED
            return False
    
    async def _initialize_chapters(self, config: Dict[str, Any]) -> List[Chapter]:
        """Initialize chapters from configuration"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.INITIALIZATION
        
        try:
            chapters = []
            chapter_configs = config.get('chapters', [])
            
            for i, chapter_config in enumerate(chapter_configs):
                chapter_id = str(uuid.uuid4())
                
                # Try to get title from URL if not provided
                chapter_title = chapter_config.get('title')
                if not chapter_title:
                    try:
                        metadata = await self.web_scraper.get_page_metadata(chapter_config.get('url', ''))
                        if metadata and metadata.get('title'):
                            chapter_title = metadata['title']
                        else:
                            chapter_title = f'Chapter {i+1}'
                    except Exception as e:
                        logger.warning(f"Could not fetch title from URL {chapter_config.get('url', '')}: {e}. Falling back to generic title.")
                        chapter_title = f'Chapter {i+1}'
                
                # Create initial content version
                initial_version = ContentVersion(
                    id=str(uuid.uuid4()),
                    chapter_id=chapter_id,
                    content="",  # Empty content initially
                    status=ContentStatus.SCRAPED,
                    agent_type=AgentType.SCRAPER,
                    metadata={
                        'initialized_at': datetime.now().isoformat(),
                        'source_url': chapter_config.get('url', '')
                    },
                    created_at=datetime.now()
                )
                
                chapter = Chapter(
                    id=chapter_id,
                    title=chapter_title,
                    url=chapter_config.get('url', ''),
                    original_content="",  # Will be populated during scraping
                    current_version=initial_version,
                    versions=[initial_version],
                    description=chapter_config.get('description', Config.DEFAULT_CHAPTER_DESCRIPTION),
                    target_length=chapter_config.get('target_length', Config.DEFAULT_CHAPTER_LENGTH),
                    keywords=chapter_config.get('keywords', []),
                    research_sources=chapter_config.get('research_sources', []),
                    current_phase=PublicationPhase.RESEARCH,
                    metadata=chapter_config.get('metadata', {})
                )
                
                chapters.append(chapter)
                self.active_chapters[chapter_id] = chapter
                
                logger.info(f"Initialized chapter: {chapter.title}")
            
            self.workflow_stats['total_chapters'] = len(chapters)
            self.workflow_stats['phase_times']['initialization'] = time.time() - phase_start
            
            return chapters
            
        except Exception as e:
            logger.error(f"Error initializing chapters: {str(e)}")
            return []
    
    async def _execute_workflow(self, chapters: List[Chapter]) -> bool:
        """Execute the main workflow"""
        try:
            # Phase 1: Research
            await self._research_phase(chapters)
            
            # Phase 2: Drafting
            await self._drafting_phase(chapters)
            
            # Phase 2.5: Spinning (Content Transformation)
            await self._spinning_phase(chapters)
            
            # Phase 3: Review
            await self._review_phase(chapters)
            
            # Phase 4: Human Review
            await self._human_review_phase(chapters)
            
            # Phase 5: Finalization
            await self._finalization_phase(chapters)
            
            # Phase 6: Publication
            await self._publication_phase(chapters)
            
            self.current_phase = WorkflowPhase.COMPLETED
            return True
            
        except Exception as e:
            logger.error(f"Error in workflow execution: {str(e)}")
            self.current_phase = WorkflowPhase.FAILED
            return False
    
    async def _research_phase(self, chapters: List[Chapter]) -> None:
        """Execute research phase for all chapters"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.RESEARCH
        logger.info("Starting research phase")
        
        try:
            # Process chapters concurrently
            research_tasks = []
            for chapter in chapters:
                task = self._research_chapter(chapter)
                research_tasks.append(task)
            
            # Wait for all research to complete
            results = await asyncio.gather(*research_tasks, return_exceptions=True)
            
            # Check results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Research failed for chapter {chapters[i].title}: {str(result)}")
                    chapters[i].current_phase = PublicationPhase.FAILED
                else:
                    chapters[i].current_phase = PublicationPhase.DRAFTING
            
            self.workflow_stats['phase_times']['research'] = time.time() - phase_start
            logger.info("Research phase completed")
            
        except Exception as e:
            logger.error(f"Error in research phase: {str(e)}")
            raise
    
    async def _research_chapter(self, chapter: Chapter) -> bool:
        """Research a single chapter"""
        try:
            logger.info(f"Researching chapter: {chapter.title}")
            
            # Collect research data
            content, metadata = await self.web_scraper.research_topic(
                chapter.title,
                chapter.keywords,
                chapter.research_sources
            )
            
            if not content:
                logger.warning(f"No research data found for chapter: {chapter.title}")
                return False
            
            # Create research version
            research_version = ContentVersion(
                id=str(uuid.uuid4()),
                chapter_id=chapter.id,
                content=content,
                status=ContentStatus.SCRAPED,
                agent_type=AgentType.SCRAPER,
                metadata=metadata,
                created_at=datetime.now()
            )
            
            # Save research version
            if not self.version_manager.save_version(research_version):
                logger.error(f"Failed to save research version for chapter: {chapter.title}")
                return False
            
            # Update chapter with research version
            chapter.research_version_id = research_version.id
            chapter.add_version(research_version)
            
            logger.info(f"Research completed for chapter {chapter.title}")
            return True
            
        except Exception as e:
            logger.error(f"Error researching chapter {chapter.title}: {str(e)}")
            return False
    
    async def _drafting_phase(self, chapters: List[Chapter]) -> None:
        """Execute drafting phase for all chapters"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.DRAFTING
        logger.info("Starting drafting phase")
        
        try:
            # Process chapters sequentially to avoid overwhelming the LLM
            for chapter in chapters:
                if chapter.current_phase != PublicationPhase.DRAFTING:
                    continue
                
                success = await self._draft_chapter(chapter)
                if success:
                    chapter.current_phase = PublicationPhase.SPINNING
                else:
                    chapter.current_phase = PublicationPhase.FAILED
                    self.workflow_stats['failed_chapters'] += 1
            
            self.workflow_stats['phase_times']['drafting'] = time.time() - phase_start
            logger.info("Drafting phase completed")
            
        except Exception as e:
            logger.error(f"Error in drafting phase: {str(e)}")
            raise
    
    async def _draft_chapter(self, chapter: Chapter) -> bool:
        """Draft a single chapter"""
        try:
            logger.info(f"Drafting chapter: {chapter.title}")
            
            # Get research data
            research_version = self.version_manager.get_version(chapter.research_version_id)
            if not research_version:
                logger.error(f"No research data found for chapter: {chapter.title}")
                return False
            
            # Generate draft
            draft_content = await self.llm_agent.generate_content(
                chapter.title,
                research_version.content,
                chapter.target_length,
                chapter.description
            )
            
            if not draft_content:
                logger.error(f"Failed to generate draft for chapter: {chapter.title}")
                return False
            
            # Create draft version
            draft_version = ContentVersion(
                id=str(uuid.uuid4()),
                chapter_id=chapter.id,
                content=draft_content,
                status=ContentStatus.AI_WRITTEN,
                agent_type=AgentType.AI_WRITER,
                parent_version_id=research_version.id,
                metadata={
                    'word_count': len(draft_content.split()),
                    'target_length': chapter.target_length
                },
                created_at=datetime.now()
            )
            
            # Save draft version
            self.version_manager.save_version(draft_version)
            chapter.draft_version_id = draft_version.id
            
            return True
            
        except Exception as e:
            logger.error(f"Error drafting chapter {chapter.title}: {str(e)}")
            return False
    
    async def _review_phase(self, chapters: List[Chapter]) -> None:
        """Execute review phase for all chapters"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.REVIEW
        logger.info("Starting review phase")
        
        try:
            for chapter in chapters:
                if chapter.current_phase != PublicationPhase.REVIEW:
                    continue
                
                success = await self._review_chapter(chapter)
                if success:
                    chapter.current_phase = PublicationPhase.HUMAN_REVIEW
                else:
                    chapter.current_phase = PublicationPhase.FAILED
                    self.workflow_stats['failed_chapters'] += 1
            
            self.workflow_stats['phase_times']['review'] = time.time() - phase_start
            logger.info("Review phase completed")
            
        except Exception as e:
            logger.error(f"Error in review phase: {str(e)}")
            raise
    
    async def _review_chapter(self, chapter: Chapter) -> bool:
        """Review a single chapter"""
        try:
            logger.info(f"Reviewing chapter: {chapter.title}")
            
            # Get spun version, or draft if no spinning occurred
            version_to_review = None
            if chapter.spun_version_id:
                version_to_review = self.version_manager.get_version(chapter.spun_version_id)
            elif chapter.draft_version_id:
                version_to_review = self.version_manager.get_version(chapter.draft_version_id)

            if not version_to_review:
                logger.error(f"No content found for chapter: {chapter.title} to review.")
                return False
            
            # Review content
            review_result = await self.llm_agent.review_content(
                version_to_review.content,
                chapter.title,
                chapter.description
            )
            
            if not review_result:
                logger.error(f"Failed to review chapter: {chapter.title}")
                return False
            
            # Create reviewed version if improvements were made
            if review_result.get('improved_content'):
                reviewed_version = ContentVersion(
                    id=str(uuid.uuid4()),
                    chapter_id=chapter.id,
                    content=review_result['improved_content'],
                    status=ContentStatus.AI_REVIEWED,
                    agent_type=AgentType.AI_REVIEWER,
                    parent_version_id=version_to_review.id,
                    metadata={
                        'review_score': review_result.get('score', 0),
                        'suggestions': review_result.get('suggestions', []),
                        'improvements_made': review_result.get('improvements_made', [])
                    },
                    created_at=datetime.now()
                )
                
                self.version_manager.save_version(reviewed_version)
                chapter.reviewed_version_id = reviewed_version.id
            else:
                # No improvements needed, use current version as reviewed
                chapter.reviewed_version_id = version_to_review.id
            
            return True
            
        except Exception as e:
            logger.error(f"Error reviewing chapter {chapter.title}: {str(e)}")
            return False
    
    async def _human_review_phase(self, chapters: List[Chapter]) -> None:
        """Execute human review phase"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.HUMAN_REVIEW
        logger.info("Starting human review phase")
        
        try:
            for chapter in chapters:
                if chapter.current_phase != PublicationPhase.HUMAN_REVIEW:
                    continue
                
                success = await self._human_review_chapter(chapter)
                if success:
                    chapter.current_phase = PublicationPhase.FINALIZATION
                else:
                    chapter.current_phase = PublicationPhase.FAILED
                    self.workflow_stats['failed_chapters'] += 1
            
            self.workflow_stats['phase_times']['human_review'] = time.time() - phase_start
            logger.info("Human review phase completed")
            
        except Exception as e:
            logger.error(f"Error in human review phase: {str(e)}")
            raise
    
    async def _human_review_chapter(self, chapter: Chapter) -> bool:
        """Human review of a single chapter"""
        try:
            logger.info(f"Human review for chapter: {chapter.title}")
            
            # Get reviewed version
            reviewed_version = self.version_manager.get_version(chapter.reviewed_version_id)
            if not reviewed_version:
                logger.error(f"No reviewed version found for chapter: {chapter.title}")
                return False
            
            # Present to human reviewer
            human_feedback = await self.human_interface.review_content(
                chapter.title,
                reviewed_version.content,
                chapter.description
            )
            
            if human_feedback and human_feedback.get('review_id'):
                chapter.metadata['human_review_id'] = human_feedback['review_id']
                logger.info(f"Stored human review ID {human_feedback['review_id']} for chapter {chapter.title}")
            
            if not human_feedback:
                logger.warning(f"No human feedback received for chapter: {chapter.title}")
                # Continue with current version
                chapter.final_version_id = reviewed_version.id
                return True
            
            # Apply human feedback if any
            if human_feedback.get('requires_changes'):
                # Create final version with human edits
                final_version = ContentVersion(
                    id=str(uuid.uuid4()),
                    chapter_id=chapter.id,
                    content=human_feedback['edited_content'],
                    status=ContentStatus.HUMAN_REVIEWED,
                    agent_type=AgentType.HUMAN,
                    parent_version_id=reviewed_version.id,
                    metadata={
                        'human_feedback': human_feedback.get('feedback', ''),
                        'changes_made': human_feedback.get('changes_made', [])
                    }
                )
                
                self.version_manager.save_version(final_version)
                chapter.final_version_id = final_version.id
            else:
                # No changes needed
                chapter.final_version_id = reviewed_version.id
            
            return True
            
        except Exception as e:
            logger.error(f"Error in human review for chapter {chapter.title}: {str(e)}")
            return False
    
    async def _finalization_phase(self, chapters: List[Chapter]) -> None:
        """Execute finalization phase"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.FINALIZATION
        logger.info("Starting finalization phase")
        
        try:
            for chapter in chapters:
                if chapter.current_phase != PublicationPhase.FINALIZATION:
                    continue
                
                success = await self._finalize_chapter(chapter)
                if success:
                    chapter.current_phase = PublicationPhase.PUBLICATION
                    self.workflow_stats['completed_chapters'] += 1
                else:
                    chapter.current_phase = PublicationPhase.FAILED
                    self.workflow_stats['failed_chapters'] += 1
            
            self.workflow_stats['phase_times']['finalization'] = time.time() - phase_start
            logger.info("Finalization phase completed")
            
        except Exception as e:
            logger.error(f"Error in finalization phase: {str(e)}")
            raise
    
    async def _finalize_chapter(self, chapter: Chapter) -> bool:
        """Finalize a single chapter"""
        try:
            logger.info(f"Finalizing chapter: {chapter.title}")
            
            # Get final version
            final_version = self.version_manager.get_version(chapter.final_version_id)
            if not final_version:
                logger.error(f"No final version found for chapter: {chapter.title}")
                return False
            
            # Update status to published
            self.version_manager.update_version_status(
                final_version.id,
                ContentStatus.PUBLISHED
            )
            
            # Mark chapter as completed
            chapter.completed_at = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"Error finalizing chapter {chapter.title}: {str(e)}")
            return False
    
    async def _publication_phase(self, chapters: List[Chapter]) -> None:
        """Execute publication phase"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.PUBLICATION
        logger.info("Starting publication phase")
        
        try:
            # Compile all chapters into final publication
            published_chapters = []
            for chapter in chapters:
                if chapter.current_phase == PublicationPhase.PUBLICATION:
                    final_version = self.version_manager.get_version(chapter.final_version_id)
                    if final_version:
                        published_chapters.append({
                            'title': chapter.title,
                            'content': final_version.content,
                            'metadata': chapter.metadata
                        })
            
            # Generate publication metadata
            publication_metadata = {
                'total_chapters': len(published_chapters),
                'generation_date': datetime.now().isoformat(),
                'workflow_stats': self.workflow_stats
            }
            
            # Save compiled publication
            await self._save_publication(published_chapters, publication_metadata)
            
            self.workflow_stats['phase_times']['publication'] = time.time() - phase_start
            logger.info("Publication phase completed")
            
        except Exception as e:
            logger.error(f"Error in publication phase: {str(e)}")
            raise
    
    async def _save_publication(self, chapters: List[Dict], metadata: Dict) -> bool:
        """Save the final publication"""
        try:
            # Create publication document
            publication_content = {
                'metadata': {
                    **metadata,
                    'generation_date': datetime.now().isoformat(),
                    'total_chapters': len(chapters),
                    'workflow_stats': {
                        k: v if not isinstance(v, datetime) else v.isoformat()
                        for k, v in self.workflow_stats.items()
                    }
                },
                'chapters': [
                    {
                        **chapter,
                        'metadata': {
                            k: v if not isinstance(v, datetime) else v.isoformat()
                            for k, v in chapter.get('metadata', {}).items()
                        }
                    }
                    for chapter in chapters
                ]
            }
            
            # Convert to JSON string for storage
            content_str = json.dumps(publication_content, indent=2)
            
            # Save as final publication version
            publication_version = ContentVersion(
                id=str(uuid.uuid4()),
                chapter_id="PUBLICATION",
                content=content_str,
                status=ContentStatus.PUBLISHED,
                agent_type=AgentType.SYSTEM,
                metadata={
                    'total_chapters': len(chapters),
                    'generation_date': datetime.now().isoformat(),
                    'publication_type': 'book',
                    **{k: v if not isinstance(v, datetime) else v.isoformat() 
                       for k, v in metadata.items()}
                },
                created_at=datetime.now()
            )
            
            # Save the version
            success = self.version_manager.save_version(publication_version)
            if not success:
                logger.error("Failed to save publication version")
                return False
                
            logger.info(f"Successfully saved publication with {len(chapters)} chapters")
            return True
            
        except Exception as e:
            logger.error(f"Error saving publication: {str(e)}")
            return False
    
    def _log_workflow_stats(self) -> None:
        """Log workflow statistics"""
        if self.workflow_stats['start_time']:
            total_time = (datetime.now() - self.workflow_stats['start_time']).total_seconds()
            self.workflow_stats['total_time'] = total_time
        
        logger.info("=== Workflow Statistics ===")
        logger.info(f"Total chapters: {self.workflow_stats['total_chapters']}")
        logger.info(f"Completed chapters: {self.workflow_stats['completed_chapters']}")
        logger.info(f"Failed chapters: {self.workflow_stats['failed_chapters']}")
        logger.info(f"Success rate: {(self.workflow_stats['completed_chapters'] / max(1, self.workflow_stats['total_chapters'])) * 100:.1f}%")
        
        if 'total_time' in self.workflow_stats:
            logger.info(f"Total time: {self.workflow_stats['total_time']:.2f} seconds")
        
        for phase, duration in self.workflow_stats['phase_times'].items():
            logger.info(f"{phase.title()} phase: {duration:.2f} seconds")
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status"""
        return {
            'current_phase': self.current_phase.value,
            'active_chapters': len(self.active_chapters),
            'statistics': self.workflow_stats,
            'chapter_status': {
                chapter_id: {
                    'title': chapter.title,
                    'phase': chapter.current_phase.value,
                    'completed_at': chapter.completed_at.isoformat() if chapter.completed_at else None
                }
                for chapter_id, chapter in self.active_chapters.items()
            }
        }
    
    async def pause_workflow(self) -> bool:
        """Pause the current workflow"""
        try:
            logger.info("Pausing workflow")
            # Implementation depends on specific requirements
            # Could save current state, stop agents, etc.
            return True
        except Exception as e:
            logger.error(f"Error pausing workflow: {str(e)}")
            return False
    
    async def resume_workflow(self) -> bool:
        """Resume a paused workflow"""
        try:
            logger.info("Resuming workflow")
            # Implementation depends on specific requirements
            # Could restore state, restart agents, etc.
            return True
        except Exception as e:
            logger.error(f"Error resuming workflow: {str(e)}")
            return False
    
    async def cancel_workflow(self) -> bool:
        """Cancel the current workflow"""
        try:
            logger.info("Cancelling workflow")
            self.current_phase = WorkflowPhase.FAILED
            
            # Mark all active chapters as failed
            for chapter in self.active_chapters.values():
                if chapter.current_phase not in [PublicationPhase.COMPLETED, PublicationPhase.FAILED]:
                    chapter.current_phase = PublicationPhase.FAILED
            
            return True
        except Exception as e:
            logger.error(f"Error cancelling workflow: {str(e)}")
            return False

    async def _spinning_phase(self, chapters: List[Chapter]) -> None:
        """Execute content spinning phase for all chapters"""
        phase_start = time.time()
        self.current_phase = WorkflowPhase.SPINNING
        logger.info("Starting content spinning phase")

        try:
            for chapter in chapters:
                if chapter.current_phase != PublicationPhase.SPINNING:
                    continue

                success = await self._spin_chapter(chapter)
                if success:
                    chapter.current_phase = PublicationPhase.REVIEW
                else:
                    chapter.current_phase = PublicationPhase.FAILED
                    self.workflow_stats['failed_chapters'] += 1

            self.workflow_stats['phase_times']['spinning'] = time.time() - phase_start
            logger.info("Content spinning phase completed")

        except Exception as e:
            logger.error(f"Error in spinning phase: {str(e)}")
            raise

    async def _spin_chapter(self, chapter: Chapter) -> bool:
        """Spin (rewrite) a single chapter's content"""
        try:
            logger.info(f"Spinning chapter: {chapter.title}")

            # Get draft version
            draft_version = self.version_manager.get_version(chapter.draft_version_id)
            if not draft_version:
                logger.error(f"No draft found for chapter {chapter.title} to spin.")
                return False

            # Spin content using LLM agent
            spun_content = await self.llm_agent.spin_content(
                original_content=draft_version.content,
                instructions="Rewrite the content to be more engaging and literary, while preserving the core narrative and themes. Maintain a similar length.",
                style_preferences={
                    "tone": "engaging and literary",
                    "perspective": "maintain original",
                    "length": "similar to original",
                    "audience": "general readers"
                }
            )

            if not spun_content or spun_content == draft_version.content:
                logger.warning(f"Content spinning yielded no changes or failed for chapter: {chapter.title}. Using original draft.")
                # If no significant change or error, use the draft version as the spun version
                chapter.spun_version_id = draft_version.id
            else:
                # Create new spun version
                spun_version = ContentVersion(
                    id=str(uuid.uuid4()),
                    chapter_id=chapter.id,
                    content=spun_content,
                    status=ContentStatus.AI_WRITTEN,  # Or a new status like ContentStatus.AI_SPUN if we add it
                    agent_type=AgentType.AI_WRITER,
                    parent_version_id=draft_version.id,
                    metadata={'original_draft_id': draft_version.id},
                    created_at=datetime.now()
                )

                self.version_manager.save_version(spun_version)
                chapter.spun_version_id = spun_version.id
                chapter.add_version(spun_version)

            logger.info(f"Content spinning completed for chapter {chapter.title}")
            return True

        except Exception as e:
            logger.error(f"Error spinning chapter {chapter.title}: {str(e)}")
            return False