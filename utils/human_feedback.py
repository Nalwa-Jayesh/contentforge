from typing import Dict, List, Optional, Any
from datetime import datetime
from models.content_models import ContentVersion, ReviewRequest, AgentType, ContentStatus
from agents.human_interface import HumanReviewInterface
from utils.logger import logger

class HumanFeedback:
    """Utility class for providing human feedback on content"""
    
    def __init__(self):
        self.review_interface = HumanReviewInterface()
        self.current_session: Optional[Dict[str, Any]] = None
    
    def start_review_session(self, review_id: str) -> Dict[str, Any]:
        """
        Start a new review session for a specific review request
        
        Args:
            review_id: ID of the review request
            
        Returns:
            Dictionary containing session information
        """
        review_details = self.review_interface.get_review_details(review_id)
        if not review_details:
            raise ValueError(f"Review {review_id} not found")
            
        self.current_session = {
            'review_id': review_id,
            'started_at': datetime.now(),
            'content': review_details['version_info']['content_preview'],
            'review_type': review_details['review_type'],
            'chapter_id': review_details['chapter_id']
        }
        
        logger.info(f"Started review session for {review_id}")
        return self.current_session
    
    def provide_feedback(self, feedback: str, updated_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Provide feedback for the current review session
        
        Args:
            feedback: Feedback text
            updated_content: Optional updated content
            
        Returns:
            Dictionary containing feedback submission results
        """
        if not self.current_session:
            raise ValueError("No active review session")
            
        review_id = self.current_session['review_id']
        
        try:
            # If no updated content provided, use original content
            if not updated_content:
                review_details = self.review_interface.get_review_details(review_id)
                updated_content = review_details['version_info']['content_preview']
            
            # Complete the review
            new_version = self.review_interface.complete_review(
                review_id=review_id,
                updated_content=updated_content,
                feedback=feedback,
                reviewer_name="Human Reviewer"  # This could be made configurable
            )
            
            if not new_version:
                raise ValueError("Failed to complete review")
            
            result = {
                'success': True,
                'review_id': review_id,
                'feedback_length': len(feedback),
                'content_updated': updated_content != self.current_session['content'],
                'new_version_id': new_version.id
            }
            
            # Clear current session
            self.current_session = None
            
            logger.info(f"Feedback provided for review {review_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error providing feedback: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'review_id': review_id
            }
    
    def get_pending_reviews(self, review_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get list of pending reviews
        
        Args:
            review_type: Optional filter by review type
            
        Returns:
            List of pending review summaries
        """
        pending = self.review_interface.get_pending_reviews(review_type=review_type)
        
        reviews = []
        for review_id, review in pending.items():
            reviews.append({
                'review_id': review_id,
                'chapter_id': review.chapter_id,
                'review_type': review.review_type,
                'submitted_at': review.submitted_at.isoformat(),
                'content_preview': review.version.content[:200] + "..." if len(review.version.content) > 200 else review.version.content
            })
        
        return reviews
    
    def get_review_history(self, chapter_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get history of completed reviews
        
        Args:
            chapter_id: Optional filter by chapter ID
            
        Returns:
            List of completed review summaries
        """
        # Get statistics which includes completed reviews
        stats = self.review_interface.get_review_statistics()
        
        # Filter by chapter if specified
        if chapter_id:
            return [r for r in stats.get('completed_reviews', []) 
                   if r.get('chapter_id') == chapter_id]
        
        return stats.get('completed_reviews', [])
    
    def format_feedback_template(self, review_type: str) -> str:
        """
        Get a template for providing feedback based on review type
        
        Args:
            review_type: Type of review (general, copy_edit, style, technical)
            
        Returns:
            Feedback template string
        """
        templates = {
            'general': """
Please provide feedback on the following aspects:
1. Overall quality and engagement
2. Clarity and readability
3. Structure and flow
4. Areas for improvement

Your feedback:
""",
            'copy_edit': """
Please review for:
1. Grammar and spelling
2. Punctuation
3. Sentence structure
4. Word choice and clarity

Your feedback:
""",
            'style': """
Please evaluate:
1. Writing style and tone
2. Voice consistency
3. Language appropriateness
4. Style improvements

Your feedback:
""",
            'technical': """
Please check:
1. Technical accuracy
2. Factual correctness
3. Source reliability
4. Technical clarity

Your feedback:
"""
        }
        
        return templates.get(review_type, templates['general'])
    
    def cancel_review(self, review_id: str, reason: str = "") -> bool:
        """
        Cancel a review
        
        Args:
            review_id: ID of the review to cancel
            reason: Optional reason for cancellation
            
        Returns:
            True if successful, False otherwise
        """
        return self.review_interface.reject_review(review_id, reason) 