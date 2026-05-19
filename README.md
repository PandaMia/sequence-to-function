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
export OPENAI_KEY="your-openai-api-key"

# Optional: Database URL (defaults to a local SQLite file)
export DATABASE_URL="sqlite+aiosqlite:///databases/sequence_function.db"
```

For production deployments, avoid storing `OPENAI_KEY` directly in `.env`. Use the encrypted local secret manager described in the Deployment section.

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

## Deployment

The recommended public demo setup is to run the FastAPI app on a localhost-only port and terminate TLS through Caddy.

For the server procedure based on `Docker Compose` and host-level `Caddy`, see `DEPLOY_SERVER.md`.

### Backend process

Use port `18081` for this service to avoid the existing services on `18080` and `18501`.

```bash
# create .env and set HOST, PORT, DATABASE_URL, model settings, limits,
# and the encrypted secret paths described below

uv sync
set -a
source .env
set +a
uv run uvicorn app:app --host "${HOST:-127.0.0.1}" --port "${PORT:-18081}"
```

### Encrypted local secrets

For a self-hosted server, the app can load `OPENAI_KEY` from an encrypted JSON file. This prevents accidentally committing the API key and avoids storing it in the service `.env` file.

Create a Fernet key once on the server:

```bash
uv run python scripts/secrets.py generate-key
```

Store that key outside the repository, for example:

```bash
sudo mkdir -p /etc/sequence-to-function
sudo sh -c 'printf "%s" "PASTE_GENERATED_KEY_HERE" > /etc/sequence-to-function/secrets.key'
sudo chmod 600 /etc/sequence-to-function/secrets.key
```

Create the encrypted secrets file:

```bash
uv run python scripts/secrets.py encrypt \
  --output secrets/stf-secrets.enc \
  --secret OPENAI_KEY
```

The script prompts for the Fernet key and then for `OPENAI_KEY` without echoing values to the terminal.

Configure the service:

```bash
STF_ENCRYPTED_SECRETS_FILE=/opt/sequence-to-function/secrets/stf-secrets.enc
STF_SECRETS_KEY_FILE=/etc/sequence-to-function/secrets.key
```

Supported secret sources, in priority order:

1. `OPENAI_KEY` environment variable for local development.
2. `OPENAI_KEY_FILE` pointing to a plain secret file.
3. `STF_ENCRYPTED_SECRETS_FILE` decrypted with `STF_SECRETS_KEY` or `STF_SECRETS_KEY_FILE`.

Important: local encryption protects secrets at rest and from accidental leaks. It does not protect against an attacker with root access or access to both the encrypted file and the decryption key. For stronger production isolation, use a cloud secret manager or a server-side secret store and inject the secret at runtime.

### Runtime data sensitivity

`databases/sessions.db` stores conversation history when persistent sessions are enabled. For public demos, prefer an ephemeral session DB:

```bash
STF_SESSION_DB_PATH=/tmp/stf_sessions.db
```

The main `databases/sequence_function.db` and `data/*.csv` files contain the service knowledge base and source article text. Keep them out of git, but they normally need to exist on the server if you want persisted knowledge-base state.

### Caddy

Add this block to the server Caddyfile:

```caddyfile
stf.pandamia.org {
    encode zstd gzip
    reverse_proxy 127.0.0.1:18081
}
```

Then reload Caddy on the server.
