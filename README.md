# Sequence-to-Function

An agent-based system for generating a knowledge base from all publicly available sources regarding the relationships between protein sequences and their functions to support future protein and gene reengineering efforts to combat aging.

Live app: https://stf.pandamia.org/

## Service Features

- **Single STF Agent**: one consolidated `STFAgent` with function tools for search, article parsing, database access, UniProt lookup, and vision analysis.
- **Literature Discovery**: search public sources for articles about a gene, protein, UniProt ID, mutation effect, longevity association, or related topic.
- **Article Parsing**: extract source article text, relevant images, PDFs, citations, and sequence-function evidence.
- **Vision Analysis**: analyze scientific images and PDFs for sequence-function data that is not available in article text.
- **Structured Persistence**: store normalized article and sequence-function records in SQLite.
- **Gene Retrieval**: query stored records by `gene` or `protein_uniprot_id`.
- **Read-only SQL Access**: execute safe `SELECT` queries against the STF database for inspection and reporting.

## How to Run the Service Locally

### Prerequisites
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager (fast Python package installer)
- OpenAI API key

**Install uv:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### Setup Instructions

#### 1. Environment Configuration
Set up your environment variables:

```bash
# Required: OpenAI API key for agent functionality
export OPENAI_KEY="your-openai-api-key"

# Optional: Database URL (defaults to a local SQLite file)
export DATABASE_URL="sqlite+aiosqlite:///databases/sequence_function.db"
```

Optional public-demo limits:

```bash
export STF_LIMITS_ENABLED="true"
export STF_MAX_MESSAGE_CHARS="8000"
export STF_MAX_REQUESTS_PER_MINUTE="5"
export STF_MAX_REQUESTS_PER_DAY="100"
export STF_MAX_SESSION_REQUESTS_PER_DAY="30"
export STF_MAX_CONCURRENT_RUNS="2"
export STF_MAX_WEB_SEARCH_CALLS_PER_SESSION="3"
export STF_SESSION_DB_PATH="/tmp/stf_sessions.db"
```

For server deployments, avoid storing `OPENAI_KEY` directly in `.env`. Use encrypted local secrets as described in `DEPLOY_SERVER.md`.

#### 2. Install Python Dependencies
```bash
# Install dependencies using uv (creates virtual environment automatically)
uv sync

# Alternative: Install without creating a project virtual environment
uv pip install -r requirements.txt
```

#### 3. Prepare Local Runtime Directories

```bash
mkdir -p data databases secrets
```

If you already have CSV snapshots, place them in:

```text
data/articles.csv
data/sequence_data.csv
```

If these files are missing, the service creates empty CSV snapshots on startup.

#### 4. Start the Application
```bash
# Run the FastAPI application using uv
uv run uvicorn app:app --host 0.0.0.0 --port 8080

# Or run the app entrypoint
uv run python app.py

# Or activate the virtual environment and run directly
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8080
```

The service will be available at:
- **Main Application**: http://localhost:8080
- **Chat UI**: http://localhost:8080/ (root path serves the chat interface)
- **API Documentation**: http://localhost:8080/docs
- **Health Check**: http://localhost:8080/health

### Database Initialization

On first startup, the application will:
1. Create the SQLite database file at `databases/sequence_function.db`
2. Create normalized `articles` and `sequence_data` tables
3. Import missing articles from `data/articles.csv` and missing sequence records from `data/sequence_data.csv` on every startup
4. Store full article text once in `articles.full_text` and `data/articles.csv`; `data/sequence_data.csv` references articles by `article_id`
