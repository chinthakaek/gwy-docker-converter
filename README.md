# Portkey AI Gateway — Docker Converter

Convert a Portkey AI Gateway Helm `values.yaml` into a ready-to-run
`docker-compose.yml` for local or single-host Docker deployments.

## What this tool does

The official Portkey AI Gateway is distributed as a Helm chart for Kubernetes.
This converter lets you take the same `values.yaml` configuration and spin up an
identical stack on plain Docker — no Kubernetes required.

Running `python3 convert.py` produces three files:

| File | Purpose |
|---|---|
| `docker-compose.yml` | The full gateway + Redis stack definition |
| `deploy.sh` | One-command launcher for Linux / macOS |
| `deploy.bat` | One-command launcher for Windows |

---

## Prerequisites

Install the following before starting:

- **Docker Desktop** (includes Docker Compose v2) — [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- **Python 3.10+** — [python.org](https://www.python.org)
- **PyYAML** — run: `pip3 install pyyaml`

---

## Step 1 — Gather your Portkey credentials

You need four values from your Portkey account before you can configure the gateway.
Log in to [portkey.ai](https://portkey.ai) and note the following:

| Value | Where to find it |
|---|---|
| Registry username | Portkey dashboard → Settings → Registry Access, or provided by your Portkey account team |
| Registry password | Same location as above |
| `PORTKEY_CLIENT_AUTH` | Portkey dashboard → Settings → API Keys |
| `ORGANISATIONS_TO_SYNC` | Portkey dashboard → Settings → Organisation — copy the Organisation ID |
| Gateway image tag | Provided by your Portkey account team (e.g. `2.15.0`) |

If you are unsure where to find any of these, contact [support@portkey.ai](mailto:support@portkey.ai).

---

## Step 2 — Place your values.yaml

You will have received a pre-configured `values.yaml` file. Copy it into the same folder as `convert.py` — no editing required. It should look like this:

```yaml
imageCredentials:
  - registry: "https://registry.portkey.ai"
    username: "your-registry-username"       # from Portkey dashboard → Settings → Registry Access
    password: "your-registry-password"       # from Portkey dashboard → Settings → Registry Access

image:
  repository: registry.portkey.ai/airsgw/gateway_enterprise
  tag: "2.15.0"                              # version provided by your Portkey account team

environment:
  data:
    PORTKEY_CLIENT_AUTH: "your-client-auth"  # from Portkey dashboard → Settings → API Keys
    ORGANISATIONS_TO_SYNC: "your-org-id"     # from Portkey dashboard → Settings → Organisation

service:
  port: 80           # host port the gateway will listen on
  containerPort: 8787
```

> **Security note:** `values.yaml` contains credentials — never commit it to version control.

---

## Step 3 — Generate and deploy

### Option A: Generate and start in one command

```bash
python3 convert.py --deploy
```

This will:
1. Log in to the Portkey container registry using your credentials
2. Write `docker-compose.yml` with all environment variables and resource limits
3. Write `deploy.sh` and `deploy.bat` for future re-deployments
4. Start the gateway and Redis with `docker compose up -d`

### Option B: Generate files only, then deploy manually

```bash
# Generate the files
python3 convert.py

# Start the stack
docker compose up -d
```

---

## Step 4 — Verify the deployment

Once the stack is running, confirm the gateway is healthy. Run these commands from the folder that contains `docker-compose.yml`:

```bash
# Check that both containers are running
cd "/path/to/gwy-docker-converter"
docker compose ps

# View gateway logs
docker compose logs airs-gateway

# Test the gateway endpoint (replace 80 with your configured port if different)
curl http://localhost:80/
```

> **Note:** `docker compose ps` and `docker compose logs` only work when run from the folder containing `docker-compose.yml`, or by passing `-f /path/to/docker-compose.yml`. To check containers from anywhere, use `docker ps`.

The gateway API will be available at `http://localhost:<port>` where `<port>` is the
value you set for `service.port` in `values.yaml` (default: `80`).

---

## Re-deploying or updating

To restart the stack on the same host using the generated scripts:

```bash
# Linux / macOS
bash deploy.sh

# Windows
deploy.bat
```

To upgrade to a new gateway version:

1. Update the `image.tag` in `values.yaml` to the new version
2. Re-run `python3 convert.py --deploy`

---

## CLI reference

```
python3 convert.py [OPTIONS]

Options:
  --values FILE      Path to values.yaml (default: values.yaml)
  --image IMAGE:TAG  Override the gateway image, e.g. registry.portkey.ai/airsgw/gateway_enterprise:2.15.0
  --output FILE      Output file path (default: docker-compose.yml)
  --deploy           Run 'docker compose up -d' after generating the file
  --no-login         Skip docker registry login
```

### Examples

```bash
# Generate files only, deploy manually
python3 convert.py
docker compose up -d

# Generate and deploy immediately
python3 convert.py --deploy

# Pin to a specific gateway version
python3 convert.py --image registry.portkey.ai/airsgw/gateway_enterprise:2.15.0 --deploy

# Use a non-default values file
python3 convert.py --values /path/to/my-values.yaml --deploy
```

---

## values.yaml reference

```yaml
imageCredentials:
  - registry: "https://registry.portkey.ai"
    username: "<REGISTRY_USERNAME>"
    password: "<REGISTRY_PASSWORD>"

# Gateway image version. Use the tag provided by your Portkey account team.
image:
  repository: registry.portkey.ai/airsgw/gateway_enterprise
  tag: "<VERSION>"          # e.g. 2.15.0

environment:
  data:
    PORTKEY_CLIENT_AUTH: "<CLIENT_AUTH_KEY>"
    ORGANISATIONS_TO_SYNC: "<ORGANISATION_ID>"
    # Optional: comma-separated list of extra hosts the gateway can forward to
    TRUSTED_CUSTOM_HOSTS: "localhost,127.0.0.1,host.docker.internal"

service:
  port: 80           # host port
  containerPort: 8787

# Optional: override default resource limits
resources:
  gateway:
    cpus: "2.0"
    memory: "4g"
  redis:
    cpus: "0.5"
    memory: "512m"
```

---

## Resource sizing

Default limits applied to the generated `docker-compose.yml` (based on
[Portkey's official sizing guide](https://portkey.ai/docs/enterprise/hybrid)):

| Component | Default (applied) | Minimum |
|---|---|---|
| Gateway (vCPU) | 2 cores | 1 core |
| Gateway (RAM) | 4 GB | 2 GB |
| Redis (vCPU) | 0.5 core | 0.25 core |
| Redis (RAM) | 512 MB | 256 MB |

Override these by adding a `resources:` block to `values.yaml` (see reference above).

---

## Required outbound network access

If the host is behind a firewall or egress proxy, allow the following:

### Always required (runtime)

| Domain | Purpose |
|---|---|
| `https://aigw.portkey.ai` | Control plane — logs, analytics, config sync |
| `https://mp.us.prod.airs-gw.portkey.ai` | Policy engine and guardrails |
| `https://api.portkey.ai` | Organisation sync and model config |

### Required at deploy / upgrade time only

| Domain | Purpose |
|---|---|
| `https://registry.portkey.ai` | Pull the gateway container image |

### Depends on your AI providers

The gateway forwards requests to whatever AI provider endpoints your virtual keys
are configured for (e.g. `api.openai.com`, `api.anthropic.com`).
Allowlist the providers relevant to your deployment.

---

## Security

- **Never commit `values.yaml`** — it contains registry credentials and API keys.
  It is listed in `.gitignore` by default.
- The generated `docker-compose.yml`, `deploy.sh`, and `deploy.bat` also embed
  credentials and are gitignored.
- For production environments, consider injecting secrets via Docker secrets or a
  dedicated secrets manager instead of plain environment variables.
