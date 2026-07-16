#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import secrets
import string
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg
from dotenv import load_dotenv
from psycopg import sql

ROOT = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "tapis-postgres-backup"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from backup import BackupManager, TapisBackupClient, resolve_tapis_token
from config import get_settings
from pods import PodsService


logger = logging.getLogger(__name__)


def load_env(env_file: str | None) -> None:
    if env_file:
        load_dotenv(env_file)
        return
    default_env = TOOLS_DIR / ".env"
    if default_env.exists():
        load_dotenv(default_env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rotate passwords for Upstream Postgres pods and update paired API pods.")
    parser.add_argument("--env-file", help="Path to .env file. Defaults to tapis-postgres-backup/.env if present.")
    parser.add_argument("--token", help="Explicit Tapis access token.")
    parser.add_argument("--base-url", help="Tapis API base URL override.")
    parser.add_argument("--pods", nargs="*", help="Specific postgres pod ids to rotate. Defaults to all discovered Upstream postgres pods.")
    parser.add_argument("--password-length", type=int, default=32, help="Length for generated passwords.")
    parser.add_argument("--show-passwords", action="store_true", help="Print generated passwords in output.")
    parser.add_argument("--dry-run", action="store_true", help="Show planned rotations without changing databases or pods.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def generate_password(length: int) -> str:
    alphabet = string.ascii_letters + string.digits + "-_~."
    return "".join(secrets.choice(alphabet) for _ in range(length))


def build_database_url(existing_url: str | None, *, user: str, password: str, host: str, port: int, db_name: str) -> str:
    encoded_password = quote(password, safe="")
    if existing_url:
        parts = urlsplit(existing_url)
        hostname = parts.hostname or host
        target_port = parts.port or port
        path = parts.path or f"/{db_name}"
        query = parts.query
        netloc = f"{quote(user, safe='')}:{encoded_password}@{hostname}:{target_port}"
        return urlunsplit((parts.scheme or "postgresql+psycopg", netloc, path, query, parts.fragment))
    return f"postgresql+psycopg://{quote(user, safe='')}:{encoded_password}@{host}:{port}/{db_name}"


def build_update_payload(pod: dict[str, Any], *, env_updates: dict[str, str], status_requested: str) -> dict[str, Any]:
    env = dict(pod.get("environment_variables") or {})
    env.update(env_updates)
    return {
        "description": pod.get("description", ""),
        "command": pod.get("command"),
        "environment_variables": env,
        "status_requested": status_requested,
        "volume_mounts": pod.get("volume_mounts") or {},
        "time_to_stop_default": pod.get("time_to_stop_default", -1),
        "time_to_stop_instance": pod.get("time_to_stop_instance"),
        "networking": pod.get("networking") or {},
        "resources": pod.get("resources") or {},
    }


def alter_password(*, host: str, port: int, db_name: str, user: str, old_password: str, new_password: str) -> None:
    with psycopg.connect(
        host=host,
        port=port,
        dbname=db_name,
        user=user,
        password=old_password,
        sslmode="require",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("ALTER ROLE {} WITH PASSWORD {}").format(
                    sql.Identifier(user),
                    sql.Literal(new_password),
                )
            )
        conn.commit()


def verify_connection(*, host: str, port: int, db_name: str, user: str, password: str) -> None:
    with psycopg.connect(
        host=host,
        port=port,
        dbname=db_name,
        user=user,
        password=password,
        sslmode="require",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level))
    load_env(args.env_file)

    settings = get_settings()
    token = resolve_tapis_token(explicit_token=args.token, settings=settings)
    base_url = args.base_url or settings.TAPIS_PODS_BASE_URL or settings.TAPIS_BASE_URL
    client = TapisBackupClient(
        token=token,
        base_url=base_url,
        timeout_seconds=settings.TAPIS_BACKUP_TIMEOUT_SECONDS,
    )
    manager = BackupManager(client=client, settings=settings)
    pods_service = PodsService(token=token, settings=settings)

    targets = manager.discover_targets()
    if args.pods:
        requested = set(args.pods)
        targets = [target for target in targets if target.pod_id in requested]
    if not targets:
        raise SystemExit("No matching postgres pods found.")

    results: list[dict[str, Any]] = []
    for target in targets:
        api_pod_id = target.pod_id[:-len("postgres")] + "api"
        postgres_pod = client.get_pod(target.pod_id)
        api_pod = client.get_pod(api_pod_id)
        new_password = generate_password(args.password_length)
        existing_database_url = str((api_pod.get("environment_variables") or {}).get("DATABASE_URL") or "")
        new_database_url = build_database_url(
            existing_database_url or None,
            user=target.db_user,
            password=new_password,
            host=target.host,
            port=target.port,
            db_name=target.db_name,
        )

        if not args.dry_run:
            alter_password(
                host=target.host,
                port=target.port,
                db_name=target.db_name,
                user=target.db_user,
                old_password=target.db_password,
                new_password=new_password,
            )
            verify_connection(
                host=target.host,
                port=target.port,
                db_name=target.db_name,
                user=target.db_user,
                password=new_password,
            )

            pods_service.update_pod(
                pod_id=target.pod_id,
                payload=build_update_payload(
                    postgres_pod,
                    env_updates={"POSTGRES_PASSWORD": new_password},
                    status_requested="ON",
                ),
            )
            pods_service.update_pod(
                pod_id=api_pod_id,
                payload=build_update_payload(
                    api_pod,
                    env_updates={
                        "POSTGRES_PASSWORD": new_password,
                        "DATABASE_URL": new_database_url,
                    },
                    status_requested="RESTART",
                ),
            )

        result = {
            "postgres_pod_id": target.pod_id,
            "api_pod_id": api_pod_id,
            "database_host": target.host,
            "database_name": target.db_name,
            "database_user": target.db_user,
            "status": "planned" if args.dry_run else "rotated",
        }
        if args.show_passwords:
            result["new_password"] = new_password
        results.append(result)

    print(json.dumps({"results": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
