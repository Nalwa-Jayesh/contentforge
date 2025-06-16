"""
Main entry point for the AI Publication System.
Provides a command-line interface for managing the publication workflow.
"""

import asyncio
import click
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import json

from models import Chapter, ContentVersion, ContentStatus, AgentType
from utils import logger
from config import Config
from workflow.publication_workflow import PublicationWorkflow

# Initialize configuration
Config.validate()

# Create workflow instance
workflow = PublicationWorkflow()

@click.group()
def cli():
    """AI Publication System CLI"""
    pass

@cli.command()
@click.argument('url')
def process(url: str):
    """Process a single chapter from a URL"""
    try:
        logger.info(f"Processing chapter from URL: {url}")
        
        # Create publication config
        config = {
            'title': f'Chapter from {url}',
            'chapters': [{
                'title': 'Chapter 1',
                'description': f'Content from {url}',
                'research_sources': [url],
                'metadata': {'source_url': url}
            }]
        }
        
        # Run workflow
        success = asyncio.run(workflow.start_publication(config))
        
        if success:
            click.echo(f"Successfully processed chapter from {url}")
        else:
            click.echo(f"Failed to process chapter from {url}")
            
    except Exception as e:
        logger.error(f"Error processing chapter: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
@click.argument('urls', nargs=-1)
def batch(urls: List[str]):
    """Process multiple chapters from URLs"""
    try:
        logger.info(f"Processing {len(urls)} chapters")
        
        # Create publication config
        config = {
            'title': f'Batch of {len(urls)} chapters',
            'chapters': [
                {
                    'title': f'Chapter {i+1}',
                    'description': f'Content from {url}',
                    'research_sources': [url],
                    'metadata': {'source_url': url}
                }
                for i, url in enumerate(urls)
            ]
        }
        
        # Run workflow
        success = asyncio.run(workflow.start_publication(config))
        
        if success:
            click.echo(f"Successfully processed {len(urls)} chapters")
        else:
            click.echo(f"Failed to process some chapters")
            
    except Exception as e:
        logger.error(f"Error in batch processing: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
@click.argument('chapter_id')
def status(chapter_id: str):
    """Check the status of a chapter"""
    try:
        logger.info(f"Checking status for chapter: {chapter_id}")
        
        # Get workflow status
        status = workflow.get_workflow_status()
        
        # Find chapter status
        chapter_status = None
        for chapter in status.get('chapters', []):
            if chapter['id'] == chapter_id:
                chapter_status = chapter
                break
        
        if chapter_status:
            click.echo(f"Status for chapter {chapter_id}:")
            click.echo(f"  Phase: {chapter_status['current_phase']}")
            click.echo(f"  Progress: {chapter_status.get('progress', 0)}%")
            click.echo(f"  Last Updated: {chapter_status.get('last_updated')}")
        else:
            click.echo(f"Chapter {chapter_id} not found")
            
    except Exception as e:
        logger.error(f"Error checking status: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
def reviews():
    """List all pending reviews"""
    try:
        logger.info("Fetching pending reviews")
        
        # Get workflow status
        status = workflow.get_workflow_status()
        
        # Find chapters in human review phase
        pending_reviews = [
            chapter for chapter in status.get('chapters', [])
            if chapter['current_phase'] == 'human_review'
        ]
        
        if pending_reviews:
            click.echo("Pending reviews:")
            for review in pending_reviews:
                click.echo(f"  Chapter: {review['title']}")
                click.echo(f"  ID: {review['id']}")
                click.echo(f"  Status: {review.get('review_status', 'pending')}")
                click.echo("---")
        else:
            click.echo("No pending reviews found")
            
    except Exception as e:
        logger.error(f"Error fetching reviews: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
@click.argument('review_id')
@click.option('--content', required=True, help='Updated content')
@click.option('--feedback', help='Review feedback')
def complete_review(review_id: str, content: str, feedback: Optional[str] = None):
    """Complete a review with updated content and feedback"""
    try:
        logger.info(f"Completing review: {review_id}")
        
        # Get workflow status
        status = workflow.get_workflow_status()
        
        # Find chapter
        chapter = None
        for ch in status.get('chapters', []):
            if ch['id'] == review_id:
                chapter = ch
                break
        
        if not chapter:
            raise click.ClickException(f"Review {review_id} not found")
        
        # Create review version
        review_version = ContentVersion(
            id=str(uuid.uuid4()),
            chapter_id=review_id,
            content=content,
            status=ContentStatus.HUMAN_REVIEWED,
            agent_type=AgentType.HUMAN_REVIEWER,
            metadata={'feedback': feedback} if feedback else {},
            created_at=datetime.now()
        )
        
        # Update chapter
        chapter['current_version'] = review_version
        chapter['current_phase'] = 'finalization'
        
        click.echo(f"Completed review {review_id}")
        
    except Exception as e:
        logger.error(f"Error completing review: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
@click.argument('chapter_id')
def finalize(chapter_id: str):
    """Finalize a chapter for publication"""
    try:
        logger.info(f"Finalizing chapter: {chapter_id}")
        
        # Get workflow status
        status = workflow.get_workflow_status()
        
        # Find chapter
        chapter = None
        for ch in status.get('chapters', []):
            if ch['id'] == chapter_id:
                chapter = ch
                break
        
        if not chapter:
            raise click.ClickException(f"Chapter {chapter_id} not found")
        
        # Create finalized version
        finalized_version = ContentVersion(
            id=str(uuid.uuid4()),
            chapter_id=chapter_id,
            content=chapter['current_version']['content'],
            status=ContentStatus.FINALIZED,
            agent_type=AgentType.HUMAN_EDITOR,
            created_at=datetime.now()
        )
        
        # Update chapter
        chapter['current_version'] = finalized_version
        chapter['current_phase'] = 'publication'
        
        click.echo(f"Finalized chapter {chapter_id}")
        
    except Exception as e:
        logger.error(f"Error finalizing chapter: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
def test():
    """Run the system with a test URL"""
    try:
        logger.info("Running test with default URL")
        
        # Create test config
        config = {
            'title': 'Test Publication',
            'chapters': [{
                'title': 'Test Chapter',
                'description': 'Test chapter from default URL',
                'research_sources': [Config.DEFAULT_TEST_URL],
                'metadata': {'source_url': Config.DEFAULT_TEST_URL}
            }]
        }
        
        # Run workflow
        success = asyncio.run(workflow.start_publication(config))
        
        if success:
            click.echo(f"Test completed successfully with URL: {Config.DEFAULT_TEST_URL}")
        else:
            click.echo("Test failed")
            
    except Exception as e:
        logger.error(f"Error in test run: {str(e)}")
        raise click.ClickException(str(e))

@cli.command()
def view_publication():
    """View the latest saved publication"""
    try:
        # Get the latest publication version
        publication_version = workflow.version_manager.get_latest_version(
            chapter_id="PUBLICATION",
            status=ContentStatus.PUBLISHED
        )
        
        if not publication_version:
            click.echo("No published content found")
            return
        
        # Parse the publication content
        publication_data = json.loads(publication_version.content)

        # Display chapters
        for i, chapter in enumerate(publication_data['chapters'], 1):
            click.echo(f"\nChapter {i}: {chapter['title']}")
            click.echo(chapter['content'])
            
    except Exception as e:
        logger.error(f"Error viewing publication: {str(e)}")
        raise click.ClickException(str(e))

def main():
    """Main entry point"""
    try:
        cli()
    except Exception as e:
        logger.error(f"Application error: {str(e)}")
        raise

if __name__ == '__main__':
    main()
