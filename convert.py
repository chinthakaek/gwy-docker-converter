#!/usr/bin/env python3
"""
Convert a Portkey AI Gateway values.yaml into a docker-compose.yml.

Usage:
  python convert.py [--values values.yaml] [--image IMAGE:TAG] [--output docker-compose.yml] [--deploy]

The image is resolved in this priority order:
  1. --image CLI flag
  2. image.repository + image.tag in values.yaml
  3. Registry hostname from imageCredentials + a prompted tag
"""

import argparse
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip install pyyaml")

# Infrastructure defaults added to every deployment.
# Values from values.yaml environment.data take precedence over these.
INFRA_ENV_DEFAULTS = {
    "NODE_ENV": "production",
    "SERVER_MODE": "all",
    "CACHE_STORE": "redis",
    "REDIS_URL": "redis://redis-cache:6379",
    "REDIS_MODE": "standalone",
    "REDIS_TLS_ENABLED": "false",
    "LOG_STORE": "control_plane",
    "ANALYTICS_STORE": "control_plane",
    "LOG_STORE_FILE_PATH_FORMAT": "v2",
    "CONTROL_PLANE_BASEPATH": "https://aigw.portkey.ai/v1",
    "ALBUS_BASEPATH": "https://mp.us.prod.airs-gw.portkey.ai/api",
    "SOURCE_SYNC_API_BASEPATH": "https://api.portkey.ai/v1/sync",
    "CONFIG_READER_PATH": "https://api.portkey.ai/model-configs",
    "MODEL_CONFIGS_PROXY_FETCH_ENABLED": "true",
}

REDIS_IMAGE = "redis:7.2-alpine"

# Default resource limits based on Portkey official sizing guidance.
# (1–2 cores, 2–4 GB RAM per gateway instance)
DEFAULT_RESOURCES = {
    "gateway": {"cpus": "2.0", "memory": "4g"},
    "redis":   {"cpus": "0.5", "memory": "512m"},
}


def docker_login(creds_list: list) -> None:
    for cred in creds_list:
        registry = cred.get("registry", "").removeprefix("https://").removeprefix("http://")
        username = cred.get("username", "")
        password = cred.get("password", "")
        if not (registry and username and password):
            print(f"  Skipping incomplete credential entry: {cred.get('name', '?')}")
            continue
        print(f"  Logging in to {registry} as {username}...")
        result = subprocess.run(
            ["docker", "login", registry, "-u", username, "--password-stdin"],
            input=password,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            sys.exit(f"Docker login to {registry} failed:\n{result.stderr.strip()}")
        print(f"  Login successful: {registry}")


def resolve_image(values: dict, cli_image: str | None) -> str:
    if cli_image:
        return cli_image

    # values.yaml image section (standard Helm pattern)
    img = values.get("image", {})
    repo = img.get("repository", "")
    tag = img.get("tag", "")
    if repo and tag:
        return f"{repo}:{tag}"
    if repo:
        return repo  # tag-less, Docker will use :latest

    # Fall back: derive registry host from imageCredentials and ask for the rest
    creds = values.get("imageCredentials", [])
    if creds:
        registry = creds[0].get("registry", "").removeprefix("https://").removeprefix("http://")
        print(
            f"\nNo image found in values.yaml or --image flag.\n"
            f"Registry from imageCredentials: {registry}\n"
        )
        image = input("Enter full image (e.g. registry.portkey.ai/airsgw/gateway_enterprise:2.15.0): ").strip()
        if image:
            return image

    sys.exit(
        "Cannot determine image. Add an 'image:' section to values.yaml or pass --image IMAGE:TAG."
    )


def resource_limits(cpus: str, memory: str) -> dict:
    return {"deploy": {"resources": {"limits": {"cpus": cpus, "memory": memory}}}}


def build_compose(image: str, env: dict, host_port: int, container_port: int,
                  gw_res: dict, redis_res: dict) -> dict:
    return {
        "services": {
            "airs-gateway": {
                "image": image,
                "container_name": "airs-gateway",
                "restart": "always",
                "ports": [f"{host_port}:{container_port}"],
                "environment": env,
                "depends_on": ["redis-cache"],
                "extra_hosts": ["model-runner.docker.internal:host-gateway"],
                **resource_limits(gw_res["cpus"], gw_res["memory"]),
            },
            "redis-cache": {
                "image": REDIS_IMAGE,
                "container_name": "airs-redis",
                "restart": "always",
                **resource_limits(redis_res["cpus"], redis_res["memory"]),
            },
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert values.yaml to docker-compose.yml for Portkey AI Gateway"
    )
    parser.add_argument("--values", default="values.yaml", metavar="FILE",
                        help="Path to the Helm values.yaml (default: values.yaml)")
    parser.add_argument("--image", metavar="IMAGE:TAG",
                        help="Gateway image to use (overrides values.yaml image section)")
    parser.add_argument("--output", default="docker-compose.yml", metavar="FILE",
                        help="Output file path (default: docker-compose.yml)")
    parser.add_argument("--deploy", action="store_true",
                        help="Run 'docker compose up -d' after generating the file")
    parser.add_argument("--no-login", action="store_true",
                        help="Skip docker login even if imageCredentials are present")
    args = parser.parse_args()

    values_path = Path(args.values)
    if not values_path.exists():
        sys.exit(f"Error: values file not found: {values_path}")

    with open(values_path) as f:
        values = yaml.safe_load(f) or {}

    # Step 1: Registry login
    creds = values.get("imageCredentials", [])
    if creds and not args.no_login:
        print("\n[1/3] Docker registry login")
        docker_login(creds)
    else:
        print("\n[1/3] Skipping registry login (no credentials or --no-login)")

    # Step 2: Resolve image
    print("\n[2/3] Resolving image")
    image = resolve_image(values, args.image)
    print(f"  Image: {image}")

    # Step 3: Build environment — infra defaults, then values.yaml wins
    env_data = values.get("environment", {}).get("data", {})
    merged_env = {**INFRA_ENV_DEFAULTS, **{k: str(v) for k, v in env_data.items()}}

    # Port mapping from service section
    service = values.get("service", {})
    host_port = int(service.get("port", 80))
    container_port = int(service.get("containerPort", merged_env.get("PORT", 8787)))

    # Resource limits — values.yaml resources section overrides defaults
    res = values.get("resources", {})
    gw_res = {**DEFAULT_RESOURCES["gateway"], **res.get("gateway", {})}
    redis_res = {**DEFAULT_RESOURCES["redis"], **res.get("redis", {})}

    # Step 3: Write docker-compose.yml
    print(f"\n[3/3] Writing {args.output}")
    compose = build_compose(image, merged_env, host_port, container_port, gw_res, redis_res)

    output_path = Path(args.output)
    with open(output_path, "w") as f:
        yaml.dump(compose, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    print(f"  Written: {output_path}")
    print(f"  Gateway: {host_port} → {container_port} ({len(merged_env)} env vars)")
    print(f"  Resources: gateway={gw_res['cpus']} CPUs / {gw_res['memory']}  redis={redis_res['cpus']} CPUs / {redis_res['memory']}")

    if args.deploy:
        print("\n[+] Deploying with docker compose up -d...")
        result = subprocess.run(["docker", "compose", "-f", str(output_path), "up", "-d"])
        if result.returncode != 0:
            sys.exit("Deployment failed.")
        print("Deployed successfully.")
    else:
        print(f"\nTo deploy: docker compose -f {output_path} up -d")
        print(f"     or:   python convert.py --values {args.values} --deploy")


if __name__ == "__main__":
    main()
