#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
TOOLS_DIR = ROOT / "tapis-postgres-backup"
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from backup import resolve_tapis_token
from config import get_settings
from pods import PodsService


def load_env(env_file: str | None) -> None:
    if env_file:
        load_dotenv(env_file)
        return
    default_env = TOOLS_DIR / ".env"
    if default_env.exists():
        load_dotenv(default_env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recreate fluxapi using upstreamapi as the base and attach it to fluxpostgres."
    )
    parser.add_argument("--env-file", help="Path to .env file. Defaults to tapis-postgres-backup/.env if present.")
    parser.add_argument("--token", help="Explicit Tapis access token.")
    parser.add_argument("--base-url", help="Tapis API base URL override.")
    parser.add_argument("--source-pod-id", default="upstreamapi", help="Template/source API pod id.")
    parser.add_argument("--target-pod-id", default="fluxapi", help="API pod id to recreate.")
    parser.add_argument("--postgres-pod-id", default="fluxpostgres", help="Target Postgres pod id.")
    parser.add_argument("--ui-host", default="https://flux.pods.portals.tapis.io", help="Flux UI base URL.")
    parser.add_argument("--api-host", default="https://fluxapi.pods.portals.tapis.io", help="Flux API base URL.")
    parser.add_argument("--database-user", help="Database username to embed in DATABASE_URL. Defaults to the live Postgres pod POSTGRES_USER.")
    parser.add_argument(
        "--database-password",
        help="Database password to embed in DATABASE_URL. Defaults to the live Postgres pod POSTGRES_PASSWORD.",
    )
    parser.add_argument("--database-name", help="Database name to embed in DATABASE_URL. Defaults to the live Postgres pod POSTGRES_DB.")
    parser.add_argument(
        "--cors-origin",
        action="append",
        dest="cors_origins",
        default=None,
        help="Allowed CORS origin. May be passed multiple times. Defaults to the Flux UI host and https://*.tapis.io.",
    )
    parser.add_argument(
        "--skip-cors-update",
        action="store_true",
        help="Create the pod without applying the CORS update step.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Skip deletion of the target pod before recreating it. Default behavior deletes the existing target pod.",
    )
    parser.add_argument("--grant-admins", action="store_true", help="Grant default admin users ADMIN on the recreated pod.")
    parser.add_argument("--dry-run", action="store_true", help="Print the recreated payload without mutating Tapis.")
    return parser.parse_args()


def _extract_result(payload: dict[str, Any]) -> Any:
    return payload.get("result", payload)


def _pod_exists(pods_service: PodsService, *, pod_id: str) -> bool:
    try:
        pods_service.get_pod(pod_id=pod_id)
    except Exception as exc:
        message = str(exc).lower()
        if "not found" in message or "\"status\":\"error\"" in message and "not found" in message:
            return False
        raise
    return True


def delete_pod_and_wait(pods_service: PodsService, *, pod_id: str, timeout_seconds: int = 180) -> dict[str, Any]:
    delete_response = {"status": "not_found", "pod_id": pod_id}
    if _pod_exists(pods_service, pod_id=pod_id):
        delete_response = pods_service._request(method="DELETE", path=f"/v3/pods/{pod_id}")
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if not _pod_exists(pods_service, pod_id=pod_id):
                return delete_response
            time.sleep(5)
        raise RuntimeError(f"Timed out waiting for pod deletion: {pod_id}")
    return delete_response


def build_database_url(*, user: str, password: str, postgres_pod_id: str, db_name: str) -> str:
    return f"postgresql+psycopg://{user}:{password}@{postgres_pod_id}.pods.portals.tapis.io:443/{db_name}"


def resolve_database_config(
    *,
    postgres_pod: dict[str, Any],
    user_override: str | None,
    password_override: str | None,
    name_override: str | None,
) -> tuple[str, str, str]:
    env = dict(postgres_pod.get("environment_variables") or {})
    db_user = user_override or env.get("POSTGRES_USER")
    db_password = password_override or env.get("POSTGRES_PASSWORD")
    db_name = name_override or env.get("POSTGRES_DB")
    if not db_user or not db_password or not db_name:
        raise RuntimeError("Could not resolve database credentials from the Postgres pod. Pass explicit overrides if needed.")
    return str(db_user), str(db_password), str(db_name)


def clone_fluxapi_payload(
    *,
    source_pod: dict[str, Any],
    target_pod_id: str,
    postgres_pod_id: str,
    ui_host: str,
    api_host: str,
    db_user: str,
    db_password: str,
    db_name: str,
    cors_origins: list[str],
    include_cors: bool = True,
) -> dict[str, Any]:
    env = dict(source_pod.get("environment_variables") or {})
    env["DATABASE_URL"] = build_database_url(
        user=db_user,
        password=db_password,
        postgres_pod_id=postgres_pod_id,
        db_name=db_name,
    )
    env["POSTGRES_PASSWORD"] = db_password
    env["VITE_UPSTREAM_API_URL"] = ui_host
    env["UI_BASE_URL"] = ui_host
    env["API_BASE_URL"] = api_host

    networking = dict(source_pod.get("networking") or {})
    default_network = dict(networking.get("default") or {})
    default_network["url"] = api_host.removeprefix("https://")
    default_network["port"] = int(default_network.get("port") or 8000)
    if include_cors:
        default_network["cors_allow_origins"] = cors_origins
        default_network["cors_allow_methods"] = ["GET", "POST", "OPTIONS", "DELETE", "PUT", "HEAD", "PATCH"]
        default_network["cors_allow_headers"] = ["content-type", "x-tapis-token", "authorization"]
    else:
        default_network.pop("cors_allow_origins", None)
        default_network.pop("cors_allow_methods", None)
        default_network.pop("cors_allow_headers", None)
    networking["default"] = default_network

    description = str(source_pod.get("description") or "")
    description = description.replace("upstreampostgres", postgres_pod_id).replace("upstreamapi", target_pod_id)

    return {
        "pod_id": target_pod_id,
        "image": source_pod.get("image"),
        "template": source_pod.get("template", ""),
        "description": description,
        "command": source_pod.get("command"),
        "arguments": source_pod.get("arguments"),
        "environment_variables": env,
        "secret_map": source_pod.get("secret_map") or {},
        "status_requested": "ON",
        "volume_mounts": source_pod.get("volume_mounts") or {},
        "time_to_stop_default": source_pod.get("time_to_stop_default", -1),
        "time_to_stop_instance": source_pod.get("time_to_stop_instance"),
        "networking": networking,
        "resources": source_pod.get("resources") or {},
        "compute_queue": source_pod.get("compute_queue", "default"),
    }


def build_cors_update_payload(*, created_pod: dict[str, Any], cors_origins: list[str]) -> dict[str, Any]:
    networking = dict(created_pod.get("networking") or {})
    default_network = dict(networking.get("default") or {})
    default_network["cors_allow_origins"] = cors_origins
    default_network["cors_allow_methods"] = ["GET", "POST", "OPTIONS", "DELETE", "PUT", "HEAD", "PATCH"]
    default_network["cors_allow_headers"] = ["content-type", "x-tapis-token", "authorization"]
    networking["default"] = default_network

    return {
        "pod_id": created_pod.get("pod_id"),
        "image": created_pod.get("image"),
        "template": created_pod.get("template", ""),
        "description": created_pod.get("description", ""),
        "command": created_pod.get("command"),
        "arguments": created_pod.get("arguments"),
        "environment_variables": created_pod.get("environment_variables") or {},
        "secret_map": created_pod.get("secret_map") or {},
        "status_requested": "RESTART",
        "volume_mounts": created_pod.get("volume_mounts") or {},
        "time_to_stop_default": created_pod.get("time_to_stop_default", -1),
        "time_to_stop_instance": created_pod.get("time_to_stop_instance"),
        "networking": networking,
        "resources": created_pod.get("resources") or {},
        "compute_queue": created_pod.get("compute_queue", "default"),
    }


def main() -> int:
    args = parse_args()
    load_env(args.env_file)

    settings = get_settings()
    token = resolve_tapis_token(explicit_token=args.token, settings=settings)
    base_url = args.base_url or settings.TAPIS_PODS_BASE_URL or settings.TAPIS_BASE_URL
    pods_service = PodsService(token=token, settings=settings)

    source_pod = _extract_result(pods_service.get_pod(pod_id=args.source_pod_id))
    postgres_pod = _extract_result(pods_service.get_pod(pod_id=args.postgres_pod_id))
    db_user, db_password, db_name = resolve_database_config(
        postgres_pod=postgres_pod,
        user_override=args.database_user,
        password_override=args.database_password,
        name_override=args.database_name,
    )
    cors_origins = args.cors_origins or [args.ui_host, "https://*.tapis.io"]
    payload = clone_fluxapi_payload(
        source_pod=source_pod,
        target_pod_id=args.target_pod_id,
        postgres_pod_id=args.postgres_pod_id,
        ui_host=args.ui_host,
        api_host=args.api_host,
        db_user=db_user,
        db_password=db_password,
        db_name=db_name,
        cors_origins=cors_origins,
        include_cors=False,
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    delete_response = None
    if not args.keep_existing:
        delete_response = delete_pod_and_wait(pods_service, pod_id=args.target_pod_id)

    created = _extract_result(pods_service.create_pod(payload))
    cors_update = None
    cors_update_error = None
    if not args.skip_cors_update:
        try:
            cors_payload = build_cors_update_payload(created_pod=created, cors_origins=cors_origins)
            cors_update = _extract_result(pods_service.update_pod(pod_id=args.target_pod_id, payload=cors_payload))
        except Exception as exc:
            cors_update_error = str(exc)

    permissions: dict[str, Any] = {}
    if args.grant_admins:
        for user in settings.DEFAULT_ADMIN_USERS or []:
            if not user:
                continue
            permissions[user] = pods_service._request(
                method="POST",
                path=f"/v3/pods/{args.target_pod_id}/permissions",
                json={"user": user, "level": "ADMIN"},
            )

    print(
        json.dumps(
            {
                "deleted": delete_response,
                "created": created,
                "cors_update": cors_update,
                "cors_update_error": cors_update_error,
                "permissions": permissions,
                "payload": payload,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
