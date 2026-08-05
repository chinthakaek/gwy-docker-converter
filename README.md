# Portkey AI Gateway — Docker Converter

Convert a Portkey AI Gateway Helm `values.yaml` into a ready-to-run
`docker-compose.yml` for local or single-host Docker deployments.

## Why

The official gateway is distributed as a Helm chart for Kubernetes.
This tool lets you take the same `values.yaml` you received from Portkey
and spin up an identical stack on plain Docker — no Kubernetes required.

## Prerequisites

- Docker + Docker Compose (v2)
- Python 3.10+
- PyYAML: `pip3 install pyyaml`

## Quick start

```bash
# 1. Copy the template and fill in your credentials
cp values.yaml.example values.yaml
$EDITOR values.yaml

# 2. Generate docker-compose.yml and deploy in one step
python3 convert.py --deploy
```

The script will:
1. Log in to the Portkey registry using credentials in `values.yaml`
2. Pull the gateway image
3. Write a `docker-compose.yml` with all required env vars
4. Start the gateway and Redis with `docker compose up -d`

The gateway will be reachable at `http://localhost:<service.port>` (default: port 80).

## Usage

```
python3 convert.py [OPTIONS]

Options:
  --values FILE      Path to values.yaml (default: values.yaml)
  --image IMAGE:TAG  Override the gateway image (e.g. registry.portkey.ai/airsgw/gateway_enterprise:2.15.0)
  --output FILE      Output file path (default: docker-compose.yml)
  --deploy           Run 'docker compose up -d' after generating the file
  --no-login         Skip docker registry login
```

### Examples

```bash
# Generate only, deploy manually
python3 convert.py
docker compose up -d

# Override image version
python3 convert.py --image registry.portkey.ai/airsgw/gateway_enterprise:2.15.0 --deploy

# Use a different values file
python3 convert.py --values /path/to/customer-values.yaml --deploy
```

## values.yaml structure

```yaml
imageCredentials:
  - registry: "https://registry.portkey.ai"
    username: "<YOUR_REGISTRY_USERNAME>"
    password: "<YOUR_REGISTRY_PASSWORD>"

image:
  repository: registry.portkey.ai/airsgw/gateway_enterprise
  tag: "<GATEWAY_VERSION>"

environment:
  data:
    PORTKEY_CLIENT_AUTH: "<YOUR_PORTKEY_CLIENT_AUTH>"
    ORGANISATIONS_TO_SYNC: "<YOUR_ORGANISATION_ID>"
    # ... additional env vars

service:
  port: 80           # host port
  containerPort: 8787
```

See `values.yaml.example` for the full template.

## Environment variable precedence

Infrastructure defaults (Redis connection, control plane URLs, etc.) are
baked into the converter. Any key in `environment.data` overrides the
corresponding default, so you only need to specify what differs.

## Security

- **Never commit `values.yaml`** — it contains credentials. It is listed
  in `.gitignore` by default.
- The generated `docker-compose.yml` embeds env vars from `values.yaml`
  and is also gitignored.
- For production use, prefer injecting secrets via Docker secrets or a
  secrets manager rather than plain env vars.

## Required outbound URLs and domains

If your host is behind a firewall or egress proxy, allowlist the following.

### Persistent (required at runtime)

| Domain / URL | Purpose |
|---|---|
| `https://aigw.portkey.ai` | Control plane — logs, analytics, and config sync |
| `https://mp.us.prod.airs-gw.portkey.ai` | Policy engine and guardrails evaluation |
| `https://api.portkey.ai` | Organisation sync and model config fetch |

### Image pull only

| Domain | Purpose |
|---|---|
| `https://registry.portkey.ai` | Pull the gateway container image (needed at deploy/upgrade time) |

### User-defined (request-time)

The gateway forwards requests to whatever AI provider endpoints your virtual
keys are configured for (e.g. `api.openai.com`, `api.anthropic.com`,
`generativelanguage.googleapis.com`). These are resolved at request time and
are not hardcoded — allowlist them based on the providers you use.
