# Claude API Proxy

Secure proxy for Anthropic Claude API with:
- IP whitelist
- Allowed model enforcement
- Daily spend limit
- Per-project tracking via pseudo-keys
- Encrypted real API key

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
# Copy CRYPTO_SALT and ANTHROPIC_API_KEY_ENCRYPTED output into .env

# 5. Generate pseudo-keys for each project
python3 -c "import secrets; print('sk-proxy-golf-' + secrets.token_hex(16))"
python3 -c "import secrets; print('sk-proxy-teams-' + secrets.token_hex(16))"
python3 -c "import secrets; print('sk-proxy-boost-' + secrets.token_hex(16))"
# Paste into .env as PSEUDO_KEY_GOLF, PSEUDO_KEY_TEAMS, PSEUDO_KEY_PRICEBOOST

# 6. Fill in .env
nano .env
# Set ALLOWED_IPS, MASTER_PASSWORD, pseudo-keys

# 7. Install and start systemd service
cp claude-proxy.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable claude-proxy
systemctl start claude-proxy

# 8. Verify
systemctl status claude-proxy
curl http://localhost:8080/health
```

## Updating scripts to use proxy

### Python (anthropic SDK)
```python
client = anthropic.Anthropic(
    api_key="sk-proxy-golf-xxxx",   # pseudo-key
    base_url="http://localhost:8080", # or http://ODDSSERVER_IP:8080 from server 1
)
```

### PHP (golf_update_tournament_map.php)
Change the API URL and key:
```php
define('ANTHROPIC_API_KEY', 'sk-proxy-golf-xxxx');  // pseudo-key
define('ANTHROPIC_API_URL', 'http://ODDSSERVER_IP:8080');
```

## Endpoints

- `GET /health` — proxy status and daily spend
- `GET /stats?day=2026-04-21` — detailed per-project stats
- `POST /v1/messages` — proxy to Anthropic (same API as Anthropic)

## Logs

```bash
journalctl -u claude-proxy -f
```