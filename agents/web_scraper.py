import asyncio
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
from playwright.async_api import async_playwright, Page
from utils.logger import logger
from config import Config

class WebScraper:
    """Handles web scraping and screenshot capture using Playwright"""
    
    def __init__(self, screenshot_dir: Optional[str] = None):
        self.screenshot_dir = Path(screenshot_dir) if screenshot_dir else Config.SCREENSHOT_DIR
        self.screenshot_dir.mkdir(exist_ok=True)
        self.timeout = Config.SCRAPING_TIMEOUT
    
    async def scrape_chapter(self, url: str, chapter_id: str) -> Tuple[str, str, Optional[str]]:
        """
        Scrape content and take screenshot from a web page
        
        Args:
            url: URL to scrape
            chapter_id: Unique identifier for the chapter
            
        Returns:
            Tuple of (title, content, screenshot_path)
        """
        logger.info(f"Starting scrape for chapter {chapter_id} from {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # Set timeout
                page.set_default_timeout(self.timeout)
                
                # Navigate to URL
                await page.goto(url, wait_until="networkidle")
                logger.info(f"Page loaded for {url}")
                
                # Extract content and title
                title, content = await self._extract_content(page, url)
                
                # Take screenshot if enabled
                screenshot_path = None
                if Config.ENABLE_SCREENSHOTS:
                    screenshot_path = await self._take_screenshot(page, chapter_id)
                
                logger.info(f"Successfully scraped chapter {chapter_id}: {len(content)} characters")
                return title, content, screenshot_path
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {str(e)}")
                raise
            finally:
                await browser.close()
    
    async def _extract_content(self, page: Page, url: str) -> Tuple[str, str]:
        """Extract title and content from the page"""
        try:
            # Try to get title from h1.firstHeading (Wikisource specific)
            title_element = await page.query_selector('h1.firstHeading')
            if title_element:
                title = await title_element.inner_text()
            else:
                # Fallback to page title
                title = await page.title()
            
            # Try to get main content from .mw-parser-output (Wikisource specific)
            content_element = await page.query_selector('.mw-parser-output')
            if content_element:
                content = await content_element.inner_text()
            else:
                # Fallback to body content
                body_element = await page.query_selector('body')
                content = await body_element.inner_text() if body_element else ""
            
            # Clean up content
            content = self._clean_content(content)
            
            logger.info(f"Extracted content: title='{title}', content_length={len(content)}")
            return title.strip(), content.strip()
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            # Return basic fallbacks
            title = await page.title() or "Unknown Title"
            content = await page.locator('body').inner_text() or ""
            return title, self._clean_content(content)
    
    async def _take_screenshot(self, page: Page, chapter_id: str) -> str:
        """Take a screenshot of the current page"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_filename = f"{chapter_id}_{timestamp}.png"
            screenshot_path = self.screenshot_dir / screenshot_filename
            
            await page.screenshot(
                path=str(screenshot_path),
                full_page=Config.SCREENSHOT_FULL_PAGE
            )
            
            logger.info(f"Screenshot saved: {screenshot_path}")
            return str(screenshot_path)
            
        except Exception as e:
            logger.error(f"Error taking screenshot: {str(e)}")
            return None
    
    def _clean_content(self, content: str) -> str:
        """Clean and normalize extracted content"""
        if not content:
            return ""
        
        # Remove excessive whitespace
        lines = content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # Skip empty lines
                cleaned_lines.append(line)
        
        # Join lines and normalize spacing
        cleaned_content = '\n'.join(cleaned_lines)
        
        # Remove multiple consecutive newlines
        while '\n\n\n' in cleaned_content:
            cleaned_content = cleaned_content.replace('\n\n\n', '\n\n')
        
        return cleaned_content
    
    async def validate_url(self, url: str) -> bool:
        """Validate if URL is accessible"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    response = await page.goto(url, timeout=10000)
                    return response.status < 400
                finally:
                    await browser.close()
                    
        except Exception as e:
            logger.error(f"URL validation failed for {url}: {str(e)}")
            return False
    
    async def get_page_metadata(self, url: str) -> dict:
        """Extract metadata from a web page"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url, timeout=self.timeout)
                
                metadata = {
                    'url': url,
                    'title': await page.title(),
                    'description': '',
                    'keywords': '',
                    'author': '',
                    'scraped_at': datetime.now().isoformat()
                }
                
                # Try to get meta description
                desc_element = await page.query_selector('meta[name="description"]')
                if desc_element:
                    metadata['description'] = await desc_element.get_attribute('content')
                
                # Try to get meta keywords
                keywords_element = await page.query_selector('meta[name="keywords"]')
                if keywords_element:
                    metadata['keywords'] = await keywords_element.get_attribute('content')
                
                # Try to get author info
                author_element = await page.query_selector('meta[name="author"]')
                if author_element:
                    metadata['author'] = await author_element.get_attribute('content')
                
                return metadata
                
            except Exception as e:
                logger.error(f"Error getting metadata for {url}: {str(e)}")
                return {'url': url, 'error': str(e), 'scraped_at': datetime.now().isoformat()}
            finally:
                await browser.close()

    async def research_topic(self, title: str, keywords: List[str], research_sources: List[str]) -> Tuple[str, Dict[str, Any]]:
        """
        Research a topic using provided sources and keywords
        
        Args:
            title: Title of the chapter
            keywords: List of keywords to research
            research_sources: List of URLs to research
            
        Returns:
            Tuple of (content, metadata)
        """
        try:
            # Combine content from all research sources
            combined_content = []
            combined_metadata = {
                'title': title,
                'keywords': keywords,
                'sources': [],
                'research_completed_at': datetime.now().isoformat()
            }
            
            for source_url in research_sources:
                try:
                    # Scrape the content
                    source_title, content, screenshot_path = await self.scrape_chapter(source_url, title)
                    
                    # Get metadata
                    metadata = await self.get_page_metadata(source_url)
                    
                    # Add to combined content
                    combined_content.append(f"Source: {source_title}\n{content}\n")
                    
                    # Add to combined metadata
                    combined_metadata['sources'].append({
                        'url': source_url,
                        'title': source_title,
                        'screenshot_path': screenshot_path,
                        'content_length': len(content),
                        **metadata
                    })
                    
                except Exception as e:
                    logger.error(f"Error researching source {source_url}: {str(e)}")
                    continue
            
            if not combined_content:
                raise ValueError("No valid research content found")
            
            # Combine all content
            final_content = "\n\n".join(combined_content)
            
            # Add summary metadata
            combined_metadata.update({
                'total_sources': len(combined_metadata['sources']),
                'total_content_length': len(final_content),
                'successful_sources': len([s for s in combined_metadata['sources'] if s.get('content_length', 0) > 0])
            })
            
            return final_content, combined_metadata
            
        except Exception as e:
            logger.error(f"Error researching topic {title}: {str(e)}")
            raise