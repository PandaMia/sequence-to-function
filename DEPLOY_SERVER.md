# Deploy Sequence-to-Function

This is a practical deployment procedure for the STF service on a server that uses `Docker Compose` for application processes and host-level `Caddy` for HTTPS reverse proxying.

The service listens on the host at `127.0.0.1:18081`; public HTTPS traffic is handled by Caddy at `stf.pandamia.org`.

## 1. Copy The Repository To The Server

Connect to the server:

```bash
ssh deploy@<server-ip>
```

Go to `/srv` and clone the project:

```bash
cd /srv
git clone https://github.com/PandaMia/sequence-to-function.git sequence-to-function
cd /srv/sequence-to-function
```

If you do not have permission to write to `/srv`:

```bash
sudo mkdir -p /srv/sequence-to-function
sudo chown -R $USER:$USER /srv/sequence-to-function
git clone https://github.com/PandaMia/sequence-to-function.git /srv/sequence-to-function
cd /srv/sequence-to-function
```

## 2. Prepare Runtime Directories

```bash
mkdir -p data databases secrets
chmod 700 secrets
```

If you want to start from local CSV snapshots, upload them from your local machine:

```bash
scp -r ./data/* deploy@<server-ip>:/srv/sequence-to-function/data
```

Verify the files on the server:

```bash
ls -lh /srv/sequence-to-function/data
```

If CSV files are not present, the service will create empty `data/articles.csv` and `data/sequence_data.csv` files on startup.

## 3. Configure The Encrypted OpenAI Secret

Generate a Fernet key on the server:

```bash
python3 - <<'PY'
import base64
import os

print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
```

Store the key outside the repository:

```bash
sudo mkdir -p /etc/sequence-to-function
sudo sh -c 'printf "%s" "PASTE_GENERATED_KEY_HERE" > /etc/sequence-to-function/secrets.key'
sudo chmod 600 /etc/sequence-to-function/secrets.key
```

Create a minimal `.env` file without the OpenAI key:

```bash
cat > .env <<'EOF'
STF_DEFAULT_MODEL=gpt-5.4-nano
STF_WEB_SEARCH_MODEL=gpt-5.4-nano
STF_VISION_MODEL=gpt-5.4-nano
STF_REASONING_EFFORT=low
STF_MAX_OUTPUT_TOKENS=4096
STF_MAX_AGENT_TURNS=25

STF_LIMITS_ENABLED=true
STF_MAX_MESSAGE_CHARS=8000
STF_MAX_REQUESTS_PER_MINUTE=5
STF_MAX_REQUESTS_PER_DAY=100
STF_MAX_SESSION_REQUESTS_PER_DAY=30
STF_MAX_CONCURRENT_RUNS=2
STF_MAX_WEB_SEARCH_CALLS_PER_SESSION=3
STF_SESSION_DB_PATH=/tmp/stf_sessions.db
EOF
```

Build the image so you can use the bundled encryption script:

```bash
docker compose build
```

Create the encrypted secrets file. The command prompts for the Fernet key and `OPENAI_KEY` without echoing values to the terminal:

```bash
docker compose run --rm --entrypoint python stf \
  scripts/secrets.py encrypt \
  --output /app/secrets/stf-secrets.enc \
  --secret OPENAI_KEY
```

Verify that the encrypted file was created:

```bash
ls -lh secrets/stf-secrets.enc
```

## 4. Build And Start The Service

On the server:

```bash
cd /srv/sequence-to-function
docker compose up -d --build
```

Check the status:

```bash
docker compose ps
docker compose logs -f
```

Check the local health endpoint:

```bash
curl http://127.0.0.1:18081/health
```

Expected response:

```json
{"status":"healthy"}
```

## 5. Configure Caddy

Open the main Caddy config:

```bash
sudo nano /etc/caddy/Caddyfile
```

Add this block:

```caddyfile
stf.pandamia.org {
    encode zstd gzip
    reverse_proxy 127.0.0.1:18081
}
```

Save the file:

```text
Ctrl + O
Enter
Ctrl + X
```

Validate the config:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Apply the config:

```bash
sudo systemctl reload caddy
```

## 6. Configure DNS

The `stf.pandamia.org` subdomain must have an `A` record pointing to the server IP address.

Check it:

```bash
dig +short A stf.pandamia.org
```

The output should be the server IP address.

## 7. Verify HTTPS

From the server or your local machine:

```bash
curl -I https://stf.pandamia.org
```

Expected response:

```text
HTTP/2 200
```

Check the health endpoint over HTTPS:

```bash
curl https://stf.pandamia.org/health
```

Expected response:

```json
{"status":"healthy"}
```

## 8. Update The Service

When new changes are available:

```bash
ssh deploy@<server-ip>
cd /srv/sequence-to-function
git pull
docker compose up -d --build
sudo systemctl reload caddy
```

If the CSV or database structure changed, check the startup sync logs:

```bash
docker compose logs -f
```
