# Claude API Proxy

Secure proxy for Anthropic Claude API with:
- IP whitelist
- Allowed model enforcement
- Daily spend limit
- Per-project tracking via pseudo-keys
- Encrypted real API key (password never stored)

## Installation

```bash
# 1. Copy files to server
cp -r . /opt/claude-proxy
cd /opt/claude-proxy

# 2. Create virtual environment
python3 -m venv venv
venv/bin/pip install -r requirements.txt

# 3. Configure
cp .env.example .env

# 4. Generate crypto salt and encrypt your API key
venv/bin/python crypto.py encrypt
# Enter master password: (choose a strong password — NOT stored anywhere)
# Enter Anthropic API key: sk-ant-...
# Copy CRYPTO_SALT and ANTHROPIC_API_KEY_ENCRYPTED output into .env

# 5. Generate pseudo-keys for each project
python3 -c "import secrets; print('sk-proxy-golf-' + secrets.token_hex(16))"
python3 -c "import secrets; print('sk-proxy-teams-' + secrets.token_hex(16))"
python3 -c "import secrets; print('sk-proxy-boost-' + secrets.token_hex(16))"
# Paste into .env as PSEUDO_KEY_GOLF, PSEUDO_KEY_TEAMS, PSEUDO_KEY_PRICEBOOST

# 6. Fill in .env
nano .env
# Set ALLOWED_IPS, pseudo-keys, ANTHROPIC_API_KEY_ENCRYPTED, CRYPTO_SALT

# 7. Verify encryption works
venv/bin/python crypto.py verify
```

## Starting the proxy

The proxy is run inside a tmux session so it persists after SSH disconnect.
Master password is entered once at startup and never stored anywhere.

```bash
# Install tmux if not already installed
apt install tmux

# Start tmux session and run proxy
tmux new-session -s claude-proxy
cd /opt/claude-proxy && venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
# Enter master password when prompted
# Then detach: Ctrl+B, then D
```

## Reconnect to proxy session

```bash
tmux attach -t claude-proxy
```

## Updating scripts to use proxy

### Python (anthropic SDK)
```python
client = anthropic.Anthropic(
    api_key="sk-proxy-golf-xxxx",    # pseudo-key from proxy .env
    base_url="http://localhost:8080",
```

## Endpoints

- `GET http://127.0.0.1:8080/health` — proxy status and daily spend
- `GET http://127.0.0.1:8080/stats?day=2026-04-21` — detailed per-project stats
- `POST http://127.0.0.1:8080/v1/messages` — proxy to Anthropic (same API as Anthropic)


## Logs

```bash
# View live proxy output
tmux attach -t claude-proxy
# Detach: Ctrl+B, then D
```