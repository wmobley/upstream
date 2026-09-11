#!/usr/bin/env python3
"""Delete and rebuild both Tapis actors:
1. zyoq4PDywXqbN - Nightly Bethel 1 telemetry fetch, transform, and Upstream upload job
2. zXJ3G4DMRD1mK - upstream-postgres-backup actor
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from tapipy.tapis import Tapis


# Bethel 1 telemetry actor configuration
BETHEL_ACTOR_ID = "0ZajqbE1Vyxxk"
BETHEL_ACTOR_NAME = "bethel1base-nightly"
BETHEL_ACTOR_DESCRIPTION = "Nightly Bethel 1 telemetry fetch, transform, and Upstream upload job."
BETHEL_ACTOR_IMAGE = "ghcr.io/wmobley/bethel1base:sha-02cbd6f"
BETHEL_CRON_HOUR_UTC = 5  # Midnight America/Chicago during CDT
BETHEL_PERMISSION_USER = "wmobley"
BETHEL_PERMISSION_LEVEL = "UPDATE"

# Upstream postgres backup actor configuration
PG_BACKUP_ACTOR_ID = "P5ZDzZ7GBWJzl"
PG_BACKUP_ACTOR_NAME = "upstream-postgres-backup"
PG_BACKUP_ACTOR_DESCRIPTION = "Nightly Upstream Postgres backup actor"
PG_BACKUP_ACTOR_IMAGE = "ghcr.io/wmobley/tapis-postgres-backup:sha-e4b8b41"
# Use a dynamic cron schedule starting from tomorrow at midnight UTC
PG_BACKUP_PERMISSION_USER = "wmobley"
PG_BACKUP_PERMISSION_LEVEL = "UPDATE"


def default_cron_schedule(now: datetime | None = None) -> str:
    """Next occurrence of CRON_HOUR_UTC, recurring daily, formatted for Tapis."""
    now = now or datetime.now(timezone.utc)
    next_run = now.replace(hour=BETHEL_CRON_HOUR_UTC, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return f"{next_run.strftime('%Y-%m-%d')} {BETHEL_CRON_HOUR_UTC:02d} + 1 day"


def default_pg_backup_cron_schedule(now: datetime | None = None) -> str:
    """Next occurrence of midnight UTC, recurring daily, formatted for Tapis."""
    now = now or datetime.now(timezone.utc)
    next_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return f"{next_run.strftime('%Y-%m-%d')} 00 + 1 day"


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def tapis_request(base_url: str, headers: dict, method: str, path: str, payload: dict | None = None) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    response = requests.request(method, url, headers=headers, json=payload, timeout=60)
    try:
        data = response.json()
    except Exception:
        response.raise_for_status()
        return {"raw_text": response.text}

    if not response.ok:
        raise RuntimeError(json.dumps(data, indent=2))
    return data


def delete_actor(base_url: str, headers: dict, actor_id: str) -> bool:
    """Delete a Tapis actor. Returns True if successful, False if not found or not authorized."""
    try:
        result = tapis_request(base_url, headers, "DELETE", f"/v3/actors/{actor_id}")
        print(f"Deleted actor {actor_id}: {json.dumps(result, indent=2)}")
        return True
    except RuntimeError as e:
        error_msg = str(e).lower()
        if "404" in error_msg or "not found" in error_msg:
            print(f"Actor {actor_id} not found (already deleted or never existed)")
            return False
        if "not authorized" in error_msg or "403" in error_msg:
            print(f"Actor {actor_id} - not authorized to delete (likely owned by another user). Continuing...")
            return False
        raise


def create_bethel_actor(base_url: str, headers: dict, tapis_username: str, tapis_password: str) -> str:
    """Create the bethel1base-nightly actor."""
    load_dotenv(Path("bethel1Base/.env"))
    load_dotenv(Path("bethel1Base/.env.example"))

    tapis_base_url = os.getenv("TAPIS_BASE_URL", "https://portals.tapis.io")
    tapis_tenant_id = os.getenv("TAPIS_TENANT_ID", "portals")

    ts_authkey = require_env("TS_AUTHKEY")
    remote_password = os.getenv("REMOTE_PASSWORD", "bethel1base")
    work_root = os.getenv("BETHEL1BASE_WORK_ROOT", "/work/bethel1Base/data")
    upstream_base_url = os.getenv("UPSTREAM_BASE_URL", "https://upstreamapi.pods.portals.tapis.io/")

    upstream_username = tapis_username
    upstream_password = tapis_password

    default_environment = {
        "TS_AUTHKEY": ts_authkey,
        "REMOTE_PASSWORD": remote_password,
        "FETCH_MODE": "watermark",
        "FETCH_OVERLAP_DAYS": os.getenv("FETCH_OVERLAP_DAYS", "3"),
        "TRANSFORM_AFTER_FETCH": "true",
        "UPLOAD_AFTER_TRANSFORM": "true",
        "UPSTREAM_USERNAME": upstream_username,
        "UPSTREAM_PASSWORD": upstream_password,
        "UPSTREAM_BASE_URL": upstream_base_url,
        "LOCAL_OUTPUT_DIR": f"{work_root}/out",
        "TRANSFORM_OUTPUT_DIR": f"{work_root}/transformed",
        "UPLOAD_INPUT_DIR": f"{work_root}/transformed",
    }

    cron_schedule = default_cron_schedule()

    actor_payload = {
        "image": BETHEL_ACTOR_IMAGE,
        "name": BETHEL_ACTOR_NAME,
        "description": BETHEL_ACTOR_DESCRIPTION,
        "default_environment": default_environment,
        "cron_schedule": cron_schedule,
        "cron_on": True,
        "token": False,
        "stateless": True,
    }

    print(f"Creating Bethel actor with payload:")
    print(json.dumps(actor_payload, indent=2))

    result = tapis_request(base_url, headers, "POST", "/v3/actors", actor_payload)
    print(json.dumps(result, indent=2))

    actor_result = result.get("result", result)
    actor_id = actor_result.get("id") or actor_result.get("actor_id")
    print(f"Created Bethel actor ID: {actor_id}")

    # Grant permission
    permission_headers = {"X-Tapis-Token": headers["X-Tapis-Token"], "Content-Type": "application/x-www-form-urlencoded"}
    permission_response = requests.post(
        f"{base_url.rstrip('/')}/v3/actors/{actor_id}/permissions",
        headers=permission_headers,
        data={"user": BETHEL_PERMISSION_USER, "level": BETHEL_PERMISSION_LEVEL},
        timeout=60,
    )
    permission_result = permission_response.json()
    if not permission_response.ok:
        raise RuntimeError(json.dumps(permission_result, indent=2))
    print(json.dumps(permission_result, indent=2))

    return actor_id


def create_pg_backup_actor(base_url: str, headers: dict) -> str:
    """Create the upstream-postgres-backup actor."""
    load_dotenv(Path("tapis-postgres-backup/.env"))
    load_dotenv(Path("tapis-postgres-backup/.env.example"))

    # Always use dynamic cron schedule starting tomorrow at midnight UTC
    cron_schedule = default_pg_backup_cron_schedule()

    actor_payload = {
        "image": PG_BACKUP_ACTOR_IMAGE,
        "name": PG_BACKUP_ACTOR_NAME,
        "description": PG_BACKUP_ACTOR_DESCRIPTION,
        "stateless": True,
        "cron_on": True,
        "cron_schedule": cron_schedule,
        "default_environment": {
            "TAPIS_BASE_URL": require_env("TAPIS_BASE_URL"),
            "TAPIS_TENANT_ID": require_env("TAPIS_TENANT_ID"),
            "TAPIS_SERVICE_USERNAME": require_env("TAPIS_SERVICE_USERNAME"),
            "TAPIS_SERVICE_PASSWORD": require_env("TAPIS_SERVICE_PASSWORD"),
            "TAPIS_BACKUP_SYSTEM_ID": require_env("TAPIS_BACKUP_SYSTEM_ID"),
            "TAPIS_BACKUP_ROOT_PATH": require_env("TAPIS_BACKUP_ROOT_PATH"),
            "TAPIS_BACKUP_RETENTION_DAYS": os.getenv("TAPIS_BACKUP_RETENTION_DAYS", "7"),
            "TAPIS_BACKUP_STAGING_DIR": os.getenv("TAPIS_BACKUP_STAGING_DIR", "/tmp/upstream-postgres-backups"),
            "TAPIS_BACKUP_TIMEOUT_SECONDS": os.getenv("TAPIS_BACKUP_TIMEOUT_SECONDS", "300"),
            "TAPIS_POSTGRES_BACKUP_MODE": "backup-once",
            "TAPIS_POSTGRES_BACKUP_LOG_LEVEL": os.getenv("TAPIS_POSTGRES_BACKUP_LOG_LEVEL", "INFO"),
        },
    }

    print(f"Creating Postgres Backup actor with payload:")
    print(json.dumps(actor_payload, indent=2))

    result = tapis_request(base_url, headers, "POST", "/v3/actors", actor_payload)
    print(json.dumps(result, indent=2))

    actor_result = result.get("result", result)
    actor_id = actor_result.get("id") or actor_result.get("actor_id")
    print(f"Created Postgres Backup actor ID: {actor_id}")

    # Grant permission
    permission_headers = {"X-Tapis-Token": headers["X-Tapis-Token"], "Content-Type": "application/x-www-form-urlencoded"}
    permission_response = requests.post(
        f"{base_url.rstrip('/')}/v3/actors/{actor_id}/permissions",
        headers=permission_headers,
        data={"user": PG_BACKUP_PERMISSION_USER, "level": PG_BACKUP_PERMISSION_LEVEL},
        timeout=60,
    )
    permission_result = permission_response.json()
    if not permission_response.ok:
        raise RuntimeError(json.dumps(permission_result, indent=2))
    print(json.dumps(permission_result, indent=2))

    return actor_id


def main() -> int:
    parser = argparse.ArgumentParser(description="Delete and rebuild Tapis actors")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without making changes")
    parser.add_argument("--skip-delete", action="store_true", help="Skip deletion, only create new actors")
    args = parser.parse_args()

    # Load environment
    load_dotenv(Path("tapis-postgres-backup/.env"))
    load_dotenv(Path("tapis-postgres-backup/.env.example"))
    load_dotenv(Path("bethel1Base/.env"))
    load_dotenv(Path("bethel1Base/.env.example"))

    tapis_base_url = os.getenv("TAPIS_BASE_URL", "https://portals.tapis.io")
    tapis_tenant_id = os.getenv("TAPIS_TENANT_ID", "portals")
    tapis_username = require_env("TAPIS_SERVICE_USERNAME")  # from tapis-postgres-backup
    tapis_password = require_env("TAPIS_SERVICE_PASSWORD")  # from tapis-postgres-backup

    # For Bethel, we also need TAPIS_USERNAME/TAPIS_PASSWORD from bethel1Base/.env
    # But the tapis-postgres-backup uses SERVICE_USERNAME/SERVICE_PASSWORD
    # Let's use the service account for both
    bethel_tapis_username = os.getenv("TAPIS_USERNAME", tapis_username)
    bethel_tapis_password = os.getenv("TAPIS_PASSWORD", tapis_password)

    # Authenticate
    t = Tapis(
        base_url=tapis_base_url,
        tenant_id=tapis_tenant_id,
        username=tapis_username,
        password=tapis_password,
    )
    t.get_tokens()
    access_token = t.access_token.access_token
    headers = {"X-Tapis-Token": access_token, "Content-Type": "application/json"}
    print(f"Authenticated as: {tapis_username}")

    if args.dry_run:
        print("DRY RUN - would perform the following actions:")
        print(f"1. Delete actor {BETHEL_ACTOR_ID} (Bethel 1 telemetry)")
        print(f"2. Delete actor {PG_BACKUP_ACTOR_ID} (Postgres backup)")
        print(f"3. Create new Bethel 1 telemetry actor")
        print(f"4. Create new Postgres backup actor")
        return 0

    # Delete existing actors
    if not args.skip_delete:
        print("\n=== Deleting existing actors ===")
        delete_actor(tapis_base_url, headers, BETHEL_ACTOR_ID)
        delete_actor(tapis_base_url, headers, PG_BACKUP_ACTOR_ID)
    else:
        print("\n=== Skipping deletion (--skip-delete) ===")

    # Create new actors
    print("\n=== Creating new Bethel 1 telemetry actor ===")
    new_bethel_id = create_bethel_actor(tapis_base_url, headers, bethel_tapis_username, bethel_tapis_password)

    print("\n=== Creating new Postgres backup actor ===")
    new_pg_backup_id = create_pg_backup_actor(tapis_base_url, headers)

    print("\n=== Summary ===")
    print(f"New Bethel 1 telemetry actor ID: {new_bethel_id}")
    print(f"New Postgres backup actor ID: {new_pg_backup_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
