import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration settings for the AI Publication System"""
    
    # API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    
    # Directory paths
    BASE_DIR = Path(__file__).parent
    SCREENSHOT_DIR = BASE_DIR / "screenshots"
    CHROMA_DB_PATH = BASE_DIR / "chroma_db"
    
    # Scraping settings
    SCRAPING_TIMEOUT = 30000  # milliseconds
    SCREENSHOT_FULL_PAGE = True
    
    # AI settings
    AI_MODEL = "gemini-pro"
    MAX_TOKENS = 8192
    TEMPERATURE = 0.7
    
    # Version management
    CHROMA_COLLECTION_NAME = "book_versions"
    SIMILARITY_THRESHOLD = 0.8
    MAX_SEARCH_RESULTS = 5
    
    # Workflow settings
    ENABLE_SCREENSHOTS = True
    ENABLE_AI_REVIEW = True
    REQUIRE_HUMAN_REVIEW = True
    AUTO_FINALIZE = False
    
    # Chapter settings
    DEFAULT_CHAPTER_LENGTH = 2000  # words
    MIN_CHAPTER_LENGTH = 1000  # words
    MAX_CHAPTER_LENGTH = 5000  # words
    DEFAULT_CHAPTER_TITLE = "Untitled Chapter"
    DEFAULT_CHAPTER_DESCRIPTION = "No description provided"
    
    # Logging
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @classmethod
    def validate(cls):
        """Validate configuration settings"""
        errors = []
        
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")
        
        # Create directories if they don't exist
        cls.SCREENSHOT_DIR.mkdir(exist_ok=True)
        cls.CHROMA_DB_PATH.mkdir(exist_ok=True)
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True

# Default URL for testing
DEFAULT_TEST_URL = "https://en.wikisource.org/wiki/The_Gates_of_Morning/Book_1/Chapter_1"