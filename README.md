# Sequence-to-Function

An agent-based system for generating a knowledge base from all publicly available sources regarding the relationships between protein sequences and their functions to support future protein and gene reengineering efforts to combat aging.

## How to Run the Service

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager (fast Python package installer)
- OpenAI API key

**Install uv:**
```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Or via pip
pip install uv
```

### Setup Instructions

#### 1. Environment Configuration
Set up your environment variables:

```bash
# Required: OpenAI API key for agent functionality
export OPENAI_API_KEY="your-openai-api-key"

# Optional: Database URL (defaults to a local SQLite file)
export DATABASE_URL="sqlite+aiosqlite:///databases/sequence_function.db"
```

#### 2. Install Python Dependencies
```bash
# Install dependencies using uv (creates virtual environment automatically)
uv sync

# Alternative: Install without creating a project virtual environment
uv pip install -r requirements.txt
```

#### 3. Start the Application
```bash
# Run the FastAPI application using uv
uv run uvicorn app:app --host 0.0.0.0 --port 8080

# Or activate the virtual environment and run directly
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uvicorn app:app --host 0.0.0.0 --port 8080
```

The service will be available at:
- **Main Application**: http://localhost:8080
- **Chat UI**: http://localhost:8080/ (root path serves the chat interface)
- **API Documentation**: http://localhost:8080/docs

### Database Initialization

On first startup, the application will:
1. Create the SQLite database file at `databases/sequence_function.db`
2. Create normalized `articles` and `sequence_data` tables
3. Import missing articles from `data/articles.csv` and missing sequence records from `data/sequence_data.csv` on every startup
4. Store full article text once in `articles.full_text` and `data/articles.csv`; `data/sequence_data.csv` references articles by `article_id`

### Service Features

- **Article Parsing**: Extract sequence-function data from research papers
- **Vision Parsing**: AI-powered analysis of scientific figures, tables, and supplementary materials to extract sequence data not available in text
- **Data Retrieval**: Query database by article URL, gene, UniProt ID, or read-only SQL
- **Article Writing**: Generate research content from stored data
- **Chat Interface**: Interactive UI for all agent capabilities
