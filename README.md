# Sequence-to-Function

An agent-based system for generating a knowledge base from all publicly available sources regarding the relationships between protein sequences and their functions to support future protein and gene reengineering efforts to combat aging.

## How to Run the Service

### Prerequisites
- Docker and Docker Compose installed
- Python 3.12+ with required dependencies
- OpenAI API key (for embeddings and AI agents)

### Setup Instructions

#### 1. Start PostgreSQL Database
The service uses PostgreSQL with pgvector extension for semantic search capabilities.

**Option A: Using Docker (Recommended)**
```bash
# Start PostgreSQL container with pgvector extension
docker compose up -d postgres

# Verify container is running
docker compose ps
```

**Option B: Local PostgreSQL Installation**
If you prefer running PostgreSQL locally, you need PostgreSQL 16+ with pgvector:

```bash
# Install PostgreSQL 16
brew install postgresql@16

# Start PostgreSQL service
brew services start postgresql@16

# Add to PATH (add this to ~/.zshrc for permanent setup)
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"

# Install pgvector extension
git clone --branch v0.8.1 https://github.com/pgvector/pgvector.git /tmp/pgvector
cd /tmp/pgvector
make
make install

# Create database and user
createdb sequence_function_db
createuser -s postgres

# Enable vector extension
psql -U postgres -d sequence_function_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### 2. Environment Configuration
Set up your environment variables:

```bash
# Required: OpenAI API key for embeddings and AI functionality
export OPENAI_API_KEY="your-openai-api-key"

# Optional: Database URL (defaults to local PostgreSQL)
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/sequence_function_db"
```

#### 3. Install Python Dependencies
```bash
# Install required packages
pip install -r requirements.txt
```

#### 4. Start the Application
```bash
# Run the FastAPI application
uvicorn app:app --host 0.0.0.0 --port 8080
```

The service will be available at:
- **Main Application**: http://localhost:8080
- **Chat UI**: http://localhost:8080/ (root path serves the chat interface)
- **API Documentation**: http://localhost:8080/docs

### Database Initialization

On first startup, the application will:
1. Create necessary database tables with pgvector extension
2. Import existing data from `data/sequence_data.csv` if present  
3. Generate embeddings for semantic search functionality
4. Set up vector similarity search indices

### Service Features

- **Article Parsing**: Extract sequence-function data from research papers
- **Vision Parcing**: AI-powered analysis of scientific figures, tables, and supplementary materials to extract sequence data not available in text
- **Data Retrieval**: Query database with SQL and semantic search
- **Article Writing**: Generate research content from stored data
- **Chat Interface**: Interactive UI for all agent capabilities
- **Semantic Search**: Vector-based similarity search using embeddings
