# Xentauri Cloud Core - Deployment Guide

## Production Environment

| Component | Value |
|-----------|-------|
| **Platform** | Fly.io |
| **App Name** | `xentauri-cloud-core` |
| **Region** | `iad` (Ashburn, Virginia) |
| **URL** | https://xentauri-cloud-core.fly.dev |
| **API Docs** | https://xentauri-cloud-core.fly.dev/docs |
| **Database** | PostgreSQL (`xentauri-db`) |

---

## Prerequisites

1. **Fly CLI installed:**
   ```bash
   # macOS
   brew install flyctl

   # Or via script
   curl -L https://fly.io/install.sh | sh
   ```

2. **Authenticate with Fly.io:**
   ```bash
   fly auth login
   ```

3. **Verify authentication:**
   ```bash
   fly auth whoami
   ```

---

## Initial Deployment (First Time)

### Step 1: Create PostgreSQL Database

```bash
fly postgres create --name xentauri-db --region iad --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1
```

**Save the credentials returned:**
```
Username:    postgres
Password:    <generated-password>
Hostname:    xentauri-db.internal
Connection:  postgres://postgres:<password>@xentauri-db.flycast:5432
```

### Step 2: Create the App

```bash
fly apps create xentauri-cloud-core --org personal
```

### Step 3: Deploy the App

```bash
fly deploy
```

### Step 4: Attach Database to App

```bash
fly postgres attach xentauri-db --app xentauri-cloud-core
```

**Important:** Fly.io sets `DATABASE_URL` as `postgres://...` but SQLAlchemy requires `postgresql+psycopg://...`

Fix the DATABASE_URL format:
```bash
fly secrets set DATABASE_URL="postgresql+psycopg://<user>:<password>@xentauri-db.flycast:5432/<database>" --app xentauri-cloud-core
```

### Step 5: Generate Secure SECRET_KEY

```bash
openssl rand -hex 32
```

### Step 6: Configure All Secrets

```bash
fly secrets set \
  SECRET_KEY="<generated-secret-key>" \
  GEMINI_API_KEY="<your-gemini-api-key>" \
  OPENAI_API_KEY="<your-openai-api-key>" \
  ANTHROPIC_API_KEY="<your-anthropic-api-key>" \
  GOOGLE_CLIENT_ID="<your-google-client-id>" \
  GOOGLE_CLIENT_SECRET="<your-google-client-secret>" \
  GOOGLE_REDIRECT_URI="https://xentauri-cloud-core.fly.dev/auth/google/callback" \
  --app xentauri-cloud-core
```

### Step 7: Update Google Cloud Console

1. Go to: https://console.cloud.google.com/apis/credentials
2. Edit your OAuth 2.0 Client ID
3. Add to **Authorized redirect URIs**:
   ```
   https://xentauri-cloud-core.fly.dev/auth/google/callback
   ```
4. Save

### Step 8: Verify Deployment

```bash
# Check app status
fly status --app xentauri-cloud-core

# Test health endpoint
curl https://xentauri-cloud-core.fly.dev/health
# Expected: {"status":"ok"}
```

---

## Subsequent Deployments

After the initial setup, deploying updates is simple:

```bash
# Deploy latest code
fly deploy

# Or deploy with a specific image tag
fly deploy --image <image>
```

---

## Useful Commands

### Monitoring

```bash
# View app status
fly status --app xentauri-cloud-core

# View logs (live)
fly logs --app xentauri-cloud-core

# View logs for specific machine
fly logs -i <machine-id> --app xentauri-cloud-core
```

### Secrets Management

```bash
# List all secrets (names only)
fly secrets list --app xentauri-cloud-core

# Set a secret
fly secrets set KEY="value" --app xentauri-cloud-core

# Remove a secret
fly secrets unset KEY --app xentauri-cloud-core
```

### Database Operations

```bash
# Connect to database via proxy
fly postgres connect --app xentauri-db

# Run psql commands
fly postgres connect --app xentauri-db -c "SELECT * FROM users LIMIT 5;"
```

### Scaling

```bash
# Scale to more machines
fly scale count 3 --app xentauri-cloud-core

# Change machine size
fly scale vm shared-cpu-2x --app xentauri-cloud-core

# View current scale
fly scale show --app xentauri-cloud-core
```

### SSH Access

```bash
# SSH into a running machine
fly ssh console --app xentauri-cloud-core
```

---

## Configuration Files

### fly.toml

```toml
app = "xentauri-cloud-core"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 8080
  force_https = true
  auto_stop_machines = "stop"
  auto_start_machines = true
  min_machines_running = 0
  processes = ["app"]

[[vm]]
  memory = "512mb"
  cpu_kind = "shared"
  cpus = 1
```

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Make startup script executable
RUN chmod +x start.sh

# Expose port
EXPOSE 8080

# Run startup script (runs migrations, then starts app)
CMD ["./start.sh"]
```

### start.sh

The startup script runs database migrations automatically before starting the app:

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
exec gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers 2
```

---

## Environment Variables (Secrets)

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string (use `postgresql+psycopg://`) | Yes |
| `SECRET_KEY` | JWT signing key (generate with `openssl rand -hex 32`) | Yes |
| `GEMINI_API_KEY` | Google Gemini API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key | Yes |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | Yes |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | Yes |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | Yes |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL | Yes |

---

## Troubleshooting

### App Crashing on Startup

**Error:** `sqlalchemy.exc.NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`

**Solution:** The DATABASE_URL uses `postgres://` but SQLAlchemy needs `postgresql+psycopg://`. Update the secret:
```bash
fly secrets set DATABASE_URL="postgresql+psycopg://..." --app xentauri-cloud-core
```

### Database Connection Issues

1. Verify the database is running:
   ```bash
   fly status --app xentauri-db
   ```

2. Check if app can reach database (they must be in same organization):
   ```bash
   fly ssh console --app xentauri-cloud-core -c "nc -zv xentauri-db.flycast 5432"
   ```

### Tables Not Created (relation "users" does not exist)

If you see `UndefinedTable: relation "users" does not exist`, the migrations haven't run.

**Manual fix:**
```bash
fly ssh console --app xentauri-cloud-core -C "bash -c 'cd /app && alembic upgrade head'"
```

**Note:** This is now handled automatically by `start.sh` on each deploy.

### Google OAuth Not Working

1. Verify `GOOGLE_REDIRECT_URI` matches exactly what's in Google Cloud Console
2. Check that the redirect URI uses `https://` (not `http://`)
3. Ensure the OAuth consent screen is configured for the correct user type

### Viewing Full Logs

```bash
# Last 100 lines
fly logs --app xentauri-cloud-core -n 100

# Follow logs in real-time
fly logs --app xentauri-cloud-core -f
```

---

## Cost Estimation (Fly.io)

| Resource | Configuration | Estimated Cost |
|----------|---------------|----------------|
| App Machines | 2x shared-cpu-1x, 512MB | ~$5-10/month |
| PostgreSQL | 1x shared-cpu-1x, 1GB disk | ~$5/month |
| **Total** | | **~$10-15/month** |

*Note: Machines auto-stop when idle, reducing costs for low-traffic apps.*

---

## Production Checklist

- [x] PostgreSQL database created and attached
- [x] SECRET_KEY generated securely (not using default)
- [x] All API keys configured as secrets
- [x] Google OAuth redirect URI updated in Cloud Console
- [x] HTTPS enforced (`force_https = true`)
- [x] Health endpoint responding
- [ ] Custom domain configured (optional)
- [ ] Monitoring/alerting set up (optional)
- [ ] Backup strategy for database (optional)

---

## Quick Reference

```bash
# Deploy
fly deploy

# Status
fly status --app xentauri-cloud-core

# Logs
fly logs --app xentauri-cloud-core

# SSH
fly ssh console --app xentauri-cloud-core

# Database console
fly postgres connect --app xentauri-db

# Set secret
fly secrets set KEY="value" --app xentauri-cloud-core

fly apps restart xentauri-cloud-core => reset
```

---

*Last updated: December 29, 2025*
