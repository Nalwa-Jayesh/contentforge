# AI Publication System

An AI-powered system for automated book content processing, from web scraping to final publication.

## Features

- Web scraping and screenshot capture using Playwright
- AI-driven content adaptation and rewriting using Google's Gemini
- Human-in-the-loop review system for quality assurance and iterative refinement
- Version control and content management with ChromaDB for historical tracking
- Intelligent content retrieval for research and review

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Nalwa-Jayesh/contentforge.git
cd contentforge
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

5. Set up environment variables:
Create a `.env` file in the project root with your Gemini API key:
```
GEMINI_API_KEY=your_api_key_here
```

## Project Structure

```
contentforge/
├── agents/                  # AI agents (WebScraper, LLMAgent,HumanReviewInterface)
│   ├── __init__.py
│   ├── human_interface.py
│   ├── llm_agent.py
│   └── web_scraper.py
├── chroma_db/               # Persistent storage for ChromaDB embeddings
├── models/                  # Data models (ContentVersion, Chapter, Book, ReviewRequest, Enums)
│   ├── __init__.py
│   ├── chapter_models.py
│   └── content_models.py
├── screenshots/             # Directory for storing webpage screenshots
├── storage/                 # Data storage and version management
│   ├── __init__.py
│   └── version_manager.py
├── utils/                   # Utility functions (logger)
│   ├── __init__.py
│   └── logger.py
├── workflow/                # Main publication workflow orchestration
│   ├── __init__.py
│   ├── publication_workflow.py
│   └── publication_phases.py # (If added later)
├── app.py                   # Streamlit application for UI
├── config.py                # Configuration settings
├── main.py                  # Command-line interface (CLI) for workflow execution
├── README.md                # Project documentation
├── requirements-frontend.txt # Dependencies for Streamlit UI
├── requirements.txt         # Core Python dependencies
└── test.py                  # Unit tests (placeholder)
```

## Usage

The system can be interacted with via a Command-Line Interface (CLI) or a Streamlit web application.

### 1. Command-Line Interface (CLI)

Run the main workflow to process a chapter from a URL:
```bash
python main.py process <URL_TO_SCRAPE>
```
Example:
```bash
python main.py process https://en.wikisource.org/wiki/The_Gates_of_Morning/Book_1/Chapter_1
```

View the latest published content from the CLI:
```bash
python main.py view-publication
```

Run a quick test with a default URL:
```bash
python main.py test
```

### 2. Streamlit Web Application

To access the interactive UI for publication viewing and human review:
```bash
streamlit run app.py
```
This will open a web application in your browser where you can view published content and manage human review tasks.

## Workflow

1.  **Content Scraping**
    *   Fetches raw content from source URLs using Playwright.
    *   Captures screenshots for visual reference.
    *   Extracts basic metadata from the web pages.

2.  **AI Processing (Drafting & Spinning)**
    *   **AI Writer (Drafting)**: Generates initial content drafts based on the scraped research.
    *   **AI Spinner (Transformation)**: Rewrites and creatively adapts the drafted content. This phase aims to enhance engagement and literary style, producing a substantially transformed version while preserving core themes.
    *   **AI Reviewer**: Provides automated feedback and suggests improvements on the adapted content.

3.  **Human-in-the-Loop Review**
    *   AI-processed content is submitted for human review through a dedicated interface.
    *   Human editors can review AI outputs, provide detailed feedback, and directly edit the content within the Streamlit application.
    *   Users have the option to approve the content (potentially with their edits) or reject it. Rejected content can be sent back for further revision by AI agents, allowing for multiple iterative loops to ensure high-quality final output.

4.  **Version Control**
    *   All content versions (raw, drafted, spun, AI-reviewed, human-edited) are meticulously stored and managed using ChromaDB.
    *   Provides a comprehensive version history tracking for each chapter.
    *   Enables intelligent content search and retrieval based on semantic similarity.

5.  **Finalization & Publication**
    *   Content that has successfully passed all review stages is marked as finalized.
    *   Finalized chapters are compiled into a complete publication, ready for output or further distribution.

## Components

### `agents/web_scraper.py` (`WebScraper`)
- Handles web scraping using Playwright.
- Captures full-page screenshots.
- Extracts main content, titles, and metadata from web pages.

### `agents/llm_agent.py` (`LLMAgent`)
- Integrates with Google's Gemini for advanced AI capabilities.
- Provides robust AI writing for drafting and creative content spinning.
- Offers AI review functionalities, including quality assessment and suggestions for improvement.
- Generates concise content summaries.

### `storage/version_manager.py` (`VersionManager`)
- Manages all content versions using ChromaDB for persistent storage and vector indexing.
- Tracks the complete history of content changes and transformations.
- Facilitates efficient retrieval of content versions.

### `agents/human_interface.py` (`HumanReviewInterface`)
- Manages the human-in-the-loop review process.
- Tracks the status of review requests (pending, completed, rejected).
- Facilitates submission of human feedback and updated content.

### `workflow/publication_workflow.py` (`PublicationWorkflow`)
- The central orchestrator of the entire AI publication process.
- Defines and executes the multi-stage workflow, including research, drafting, spinning, AI review, human review, and finalization.
- Manages chapter transitions between different publication phases.

### `models/` (Data Models)
- Defines the data structures for `ContentVersion`, `Chapter`, `Book`, and `ReviewRequest`.
- Includes `ContentStatus` and `AgentType` enums to categorize content states and responsible agents.

## Contributing

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/YourFeatureName`).
3.  Commit your changes (`git commit -m 'Add new feature'`).
4.  Push to the branch (`git push origin feature/YourFeatureName`).
5.  Create a Pull Request.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Acknowledgments

-   Google Gemini for powerful AI capabilities.
-   Playwright for efficient web scraping.
-   ChromaDB for intelligent vector storage and content versioning. 