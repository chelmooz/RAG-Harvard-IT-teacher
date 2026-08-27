# Config – Nginx Reverse Proxy

**Purpose**: Centralized Nginx configuration for routing external traffic to the RAG stack services.

## Structure
```
config/nginx.conf          # Main config file
```

## Where to Look
| Task | Location | Notes |
|------|------------|-------|
| Add new reverse proxy rule | `config/nginx.conf` | Follow existing `location /chat` block syntax |
| Adjust rate limits | `config/nginx.conf` | Use `limit_req_zone` / `limit_req` directives |
| Enable HTTPS | `config/nginx.conf` + cert files (outside repo) | Certs managed by reverse‑proxy provisioning pipeline |

## Code Map
- **HTTP → FastAPI**: `/chat` → `backend/api/main.py`
- **HTTP → React UI**: `/` → `frontend` static files
- **Metrics endpoint**: `/metrics` → `backend/api/evaluation.py`

## Conventions
- All paths are case‑sensitive; use kebab‑case for custom locations.
- Upstream services are referenced by Docker container name (`backend`, `frontend`).
- Logging format follows `json` struct; include `request_id` from header.

## Anti‑Patterns
- Hard‑coded IPs – rely on Docker service names.
- Multiple `location` blocks with overlapping regexes – consolidate into a single block.
- Unescaped variables in `proxy_pass` – use `$uri` safely.

## Commands
```bash
# Test config syntax
nginx -t

# Reload service (Docker container name: nginx)
docker exec nginx nginx -s reload
```

## Notes
- Increment `server_version` comment at top of file for audit trail.
- All changes must be reviewed by the infra lead before push.
- TLS certificates are stored in the secrets manager; never commit private keys.