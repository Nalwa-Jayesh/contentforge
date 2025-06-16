import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from models.content_models import ContentVersion, ReviewRequest, AgentType, ContentStatus
from utils.logger import logger

class HumanReviewInterface:
    """Interface for human-in-the-loop interactions"""
    
    def __init__(self):
        self.pending_reviews: Dict[str, ReviewRequest] = {}
        self.completed_reviews: Dict[str, ReviewRequest] = {}
        
    def submit_for_human_review(self, chapter_id: str, version: ContentVersion, 
                               review_type: str = "general", 
                               priority: str = "normal") -> str:
        """
        Submit content for human review
        
        Args:
            chapter_id: ID of the chapter
            version: ContentVersion to review
            review_type: Type of review (general, copy_edit, style, technical)
            priority: Priority level (low, normal, high, urgent)
            
        Returns:
            Review request ID
        """
        review_id = str(uuid.uuid4())
        
        review_request = ReviewRequest(
            id=review_id,
            chapter_id=chapter_id,
            version=version,
            review_type=review_type,
            submitted_at=datetime.now(),
            status='pending'
        )
        
        self.pending_reviews[review_id] = review_request
        
        logger.info(f"Submitted version {version.id} for human review "
                   f"(ID: {review_id}, Type: {review_type}, Priority: {priority})")
        
        return review_id
    
    def get_pending_reviews(self, chapter_id: Optional[str] = None, 
                          review_type: Optional[str] = None) -> Dict[str, ReviewRequest]:
        """
        Get pending human reviews with optional filters
        
        Args:
            chapter_id: Filter by chapter ID
            review_type: Filter by review type
            
        Returns:
            Dictionary of pending reviews
        """
        filtered_reviews = {}
        
        for review_id, review in self.pending_reviews.items():
            if review.status != 'pending':
                continue
                
            if chapter_id and review.chapter_id != chapter_id:
                continue
                
            if review_type and review.review_type != review_type:
                continue
                
            filtered_reviews[review_id] = review
        
        return filtered_reviews
    
    def get_review_details(self, review_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific review"""
        review = self.pending_reviews.get(review_id) or self.completed_reviews.get(review_id)
        
        if not review:
            return None
        
        return {
            'review_id': review_id,
            'chapter_id': review.chapter_id,
            'review_type': review.review_type,
            'status': review.status,
            'submitted_at': review.submitted_at.isoformat(),
            'version_info': {
                'version_id': review.version.id,
                'status': review.version.status.value,
                'agent_type': review.version.agent_type.value,
                'created_at': review.version.created_at.isoformat(),
                'content_length': len(review.version.content),
                'content_preview': review.version.content[:200] + "..." if len(review.version.content) > 200 else review.version.content
            },
            'reviewer_notes': review.reviewer_notes
        }
    
    def complete_review(self, review_id: str, updated_content: str, 
                       feedback: str = "", reviewer_name: str = "Unknown") -> Optional[ContentVersion]:
        """
        Complete a human review
        
        Args:
            review_id: ID of the review to complete
            updated_content: The revised content
            feedback: Reviewer feedback and notes
            reviewer_name: Name of the reviewer
            
        Returns:
            New ContentVersion with human edits, or None if review not found
        """
        if review_id not in self.pending_reviews:
            logger.error(f"Review {review_id} not found in pending reviews")
            return None
        
        review = self.pending_reviews[review_id]
        original_version = review.version
        
        # Create new version with human edits
        new_version = ContentVersion(
            id=str(uuid.uuid4()),
            chapter_id=review.chapter_id,
            content=updated_content,
            status=ContentStatus.HUMAN_EDITED,
            agent_type=AgentType.HUMAN_EDITOR,
            metadata={
                'feedback': feedback,
                'review_id': review_id,
                'reviewer_name': reviewer_name,
                'review_type': review.review_type,
                'review_completed_at': datetime.now().isoformat()
            },
            created_at=datetime.now(),
            parent_version_id=original_version.id
        )
        
        # Update review status
        review.status = 'completed'
        review.reviewer_notes = feedback
        
        # Move to completed reviews
        self.completed_reviews[review_id] = review
        del self.pending_reviews[review_id]
        
        logger.info(f"Review {review_id} completed by {reviewer_name}")
        return new_version
    
    def reject_review(self, review_id: str, reason: str = "") -> bool:
        """
        Reject a review and send back for revision
        
        Args:
            review_id: ID of the review to reject
            reason: Reason for rejection
            
        Returns:
            True if successful, False otherwise
        """
        if review_id not in self.pending_reviews:
            logger.error(f"Review {review_id} not found in pending reviews")
            return False
        
        review = self.pending_reviews[review_id]
        review.status = 'rejected'
        review.reviewer_notes = reason
        
        logger.info(f"Review {review_id} rejected: {reason}")
        return True
    
    def get_review_statistics(self) -> Dict[str, Any]:
        """Get statistics about review activities"""
        total_pending = len(self.pending_reviews)
        total_completed = len(self.completed_reviews)
        
        # Count by review type
        pending_by_type = {}
        completed_by_type = {}
        
        for review in self.pending_reviews.values():
            review_type = review.review_type
            pending_by_type[review_type] = pending_by_type.get(review_type, 0) + 1
        
        for review in self.completed_reviews.values():
            review_type = review.review_type
            completed_by_type[review_type] = completed_by_type.get(review_type, 0) + 1
        
        # Calculate average completion time for completed reviews
        completion_times = []
        for review in self.completed_reviews.values():
            if review.status == 'completed':
                # This would need completion timestamp to calculate properly
                # For now, we'll use a placeholder
                completion_times.append(1.0)  # placeholder: 1 day
        
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
        
        return {
            'total_pending': total_pending,
            'total_completed': total_completed,
            'pending_by_type': pending_by_type,
            'completed_by_type': completed_by_type,
            'average_completion_time_days': avg_completion_time,
            'review_types': list(set(list(pending_by_type.keys()) + list(completed_by_type.keys())))
        }
    
    def get_reviewer_dashboard(self, reviewer_name: Optional[str] = None) -> Dict[str, Any]:
        """Get dashboard information for reviewers"""
        dashboard = {
            'pending_reviews': [],
            'recent_completions': [],
            'review_metrics': {}
        }
        
        # Get pending reviews
        for review_id, review in self.pending_reviews.items():
            if review.status == 'pending':
                dashboard['pending_reviews'].append({
                    'review_id': review_id,
                    'chapter_id': review.chapter_id,
                    'review_type': review.review_type,
                    'submitted_at': review.submitted_at.isoformat(),
                    'content_length': len(review.version.content),
                    'urgency': self._calculate_urgency(review.submitted_at)
                })
        
        # Get recent completions
        recent_completions = sorted(
            [(rid, r) for rid, r in self.completed_reviews.items() if r.status == 'completed'],
            key=lambda x: x[1].submitted_at,
            reverse=True
        )[:10]
        
        for review_id, review in recent_completions:
            dashboard['recent_completions'].append({
                'review_id': review_id,
                'chapter_id': review.chapter_id,
                'review_type': review.review_type,
                'completed_at': review.submitted_at.isoformat(),  # placeholder
                'feedback_length': len(review.reviewer_notes)
            })
        
        # Calculate metrics
        dashboard['review_metrics'] = {
            'pending_count': len(dashboard['pending_reviews']),
            'completed_today': len([r for r in recent_completions if self._is_today(r[1].submitted_at)]),
            'average_review_time': '1.2 days',  # placeholder
            'most_common_review_type': self._get_most_common_review_type()
        }
        
        return dashboard
    
    def _calculate_urgency(self, submitted_at: datetime) -> str:
        """Calculate urgency based on submission time"""
        hours_since_submission = (datetime.now() - submitted_at).total_seconds() / 3600
        
        if hours_since_submission > 72:  # 3 days
            return 'high'
        elif hours_since_submission > 24:  # 1 day
            return 'medium'
        else:
            return 'low'
    
    def _is_today(self, date: datetime) -> bool:
        """Check if date is today"""
        return date.date() == datetime.now().date()
    
    def _get_most_common_review_type(self) -> str:
        """Get the most common review type"""
        type_counts = {}
        for review in list(self.pending_reviews.values()) + list(self.completed_reviews.values()):
            review_type = review.review_type
            type_counts[review_type] = type_counts.get(review_type, 0) + 1
        
        if not type_counts:
            return 'general'
        
        return max(type_counts, key=type_counts.get)
    
    def bulk_assign_reviews(self, reviewer_name: str, review_ids: List[str]) -> Dict[str, bool]:
        """Assign multiple reviews to a reviewer"""
        results = {}
        
        for review_id in review_ids:
            if review_id in self.pending_reviews:
                review = self.pending_reviews[review_id]
                review.metadata = review.version.metadata.copy()
                review.metadata['assigned_reviewer'] = reviewer_name
                review.metadata['assigned_at'] = datetime.now().isoformat()
                results[review_id] = True
                logger.info(f"Assigned review {review_id} to {reviewer_name}")
            else:
                results[review_id] = False
                logger.warning(f"Could not assign review {review_id} - not found")
        
        return results
    
    def export_review_data(self, format: str = "json") -> Any:
        """Export review data for analysis"""
        all_reviews = {**self.pending_reviews, **self.completed_reviews}
        
        export_data = []
        for review_id, review in all_reviews.items():
            export_data.append({
                'review_id': review_id,
                'chapter_id': review.chapter_id,
                'review_type': review.review_type,
                'status': review.status,
                'submitted_at': review.submitted_at.isoformat(),
                'content_length': len(review.version.content),
                'has_feedback': bool(review.reviewer_notes),
                'feedback_length': len(review.reviewer_notes),
            })
        
        if format.lower() == "json":
            import json
            return json.dumps(export_data, indent=2)
        elif format.lower() == "csv":
            import csv
            import io
            output = io.StringIO()
            if export_data:
                fieldnames = export_data[0].keys()
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(export_data)
            return output.getvalue()
        else:
            return export_data

    async def review_content(self, title: str, content: str, description: str = "") -> Dict[str, Any]:
        """
        Review content and provide feedback
        
        Args:
            title: Title of the content
            content: Content to review
            description: Optional description of the content
            
        Returns:
            Dictionary containing review feedback and any changes made
        """
        try:
            # Submit for human review
            review_id = self.submit_for_human_review(
                chapter_id=title,  # Using title as chapter_id for now
                version=ContentVersion(
                    id=str(uuid.uuid4()),
                    chapter_id=title,
                    content=content,
                    status=ContentStatus.AI_REVIEWED,
                    agent_type=AgentType.AI_REVIEWER,
                    metadata={'description': description},
                    created_at=datetime.now()
                ),
                review_type="general"
            )
            
            # Get review details
            review_details = self.get_review_details(review_id)
            if not review_details:
                return {
                    'requires_changes': False,
                    'feedback': "No review details available",
                    'edited_content': content,
                    'review_id': review_id
                }
            
            # Check if review is completed
            if review_details['status'] == 'completed':
                return {
                    'requires_changes': True,
                    'feedback': review_details['reviewer_notes'],
                    'edited_content': review_details['version_info']['content_preview'],
                    'changes_made': ['Content reviewed and edited by human reviewer'],
                    'review_id': review_id
                }
            
            return {
                'requires_changes': False,
                'feedback': "Review pending",
                'edited_content': content,
                'review_id': review_id
            }
            
        except Exception as e:
            logger.error(f"Error in review_content: {str(e)}")
            return {
                'requires_changes': False,
                'feedback': f"Error during review: {str(e)}",
                'edited_content': content,
                'review_id': None
            }