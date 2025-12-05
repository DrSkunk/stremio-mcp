#!/usr/bin/env python3
"""Sync the local Stremio MCP addon directory to a Home Assistant instance."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, Iterable, Tuple

DEFAULTS = {
    "host": "homeassistant.local",
    "user": "root",
    "port": 22,
    "target": "/addons/stremio-mcp",
    "source": "stremio-mcp",
    "identity": "",
}

ENV_KEYS = {
    "host": "HA_HOST",
    "user": "HA_USER",
    "port": "HA_PORT",
    "target": "HA_TARGET_DIR",
    "source": "ADDON_SOURCE_DIR",
    "identity": "HA_SSH_KEY",
}

EXCLUDES = [".git", "__pycache__", "*.pyc", ".DS_Store"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Synchronize the Home Assistant addon via rsync over SSH."
    )
    parser.add_argument(
        "-H",
        "--host",
        help=f"Home Assistant host (default: {DEFAULTS['host']})",
    )
    parser.add_argument(
        "-u",
        "--user",
        help=f"SSH user (default: {DEFAULTS['user']})",
    )
    parser.add_argument(
        "-P",
        "--port",
        type=int,
        help=f"SSH port (default: {DEFAULTS['port']})",
    )
    parser.add_argument(
        "-t",
        "--target",
        help=f"Target directory on Home Assistant (default: {DEFAULTS['target']})",
    )
    parser.add_argument(
        "-s",
        "--source",
        help=f"Local addon directory to sync (default: {DEFAULTS['source']})",
    )
    parser.add_argument(
        "-i",
        "--identity",
        help="SSH private key to use (default: empty)",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would be transferred without copying",
    )
    parser.add_argument(
        "--env-file",
        default=".sync-ha.env",
        help="Path to the env file with defaults (default: .sync-ha.env)",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env

    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        env[key] = value
    return env


def build_config(args: argparse.Namespace) -> Dict[str, str | int | bool]:
    config: Dict[str, str | int | bool] = dict(DEFAULTS)

    env_path = Path(args.env_file).expanduser()
    file_env = load_env_file(env_path)
    if env_path.exists():
        print(f"[sync] Loaded configuration from {env_path}")
    else:
        print(f"[sync] Env file {env_path} not found; proceeding with defaults")

    def apply_value(key: str, raw: str | int | None):
        if raw in (None, ""):
            return
        if key == "port":
            config[key] = int(raw)
        else:
            config[key] = raw

    for key, env_name in ENV_KEYS.items():
        apply_value(key, file_env.get(env_name))
        apply_value(key, os.environ.get(env_name))

    apply_value("host", args.host)
    apply_value("user", args.user)
    apply_value("port", args.port)
    apply_value("target", args.target)
    apply_value("source", args.source)
    apply_value("identity", args.identity)

    config["dry_run"] = bool(args.dry_run)
    return config


def ensure_dependencies(cmds: Iterable[str]) -> None:
    missing = [cmd for cmd in cmds if shutil_which(cmd) is None]
    if missing:
        raise SystemExit(f"Required command(s) missing from PATH: {', '.join(missing)}")


def shutil_which(cmd: str) -> str | None:
    from shutil import which

    return which(cmd)


def expand_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(path))


def build_ssh_parts(config: Dict[str, str | int | bool]) -> Tuple[str, ...]:
    parts = ["ssh"]
    port = config["port"]
    identity = config["identity"]
    if port:
        parts.extend(["-p", str(port)])
    if identity:
        parts.extend(["-i", expand_path(identity)])
    return tuple(parts)


def run_ssh_command(base_cmd: Tuple[str, ...], remote: str, command: str) -> None:
    ssh_cmd = list(base_cmd) + [remote, command]
    subprocess.run(ssh_cmd, check=True)


def sync(config: Dict[str, str | int | bool]) -> None:
    ensure_dependencies(["rsync", "ssh"])

    source_dir = Path(expand_path(str(config["source"]))).resolve()
    if not source_dir.is_dir():
        raise SystemExit(f"Source directory '{source_dir}' does not exist")

    target_dir = str(config["target"]).rstrip("/") or "/"
    dry_run = bool(config["dry_run"])

    remote = f"{config['user']}@{config['host']}"
    ssh_parts = build_ssh_parts(config)

    if dry_run:
        print("[sync] Dry run enabled; remote directories will not be created")
    else:
        print(f"[sync] Ensuring {target_dir} exists on {remote}")
        run_ssh_command(ssh_parts, remote, f"mkdir -p {shlex.quote(target_dir)}")

    rsync_cmd = [
        "rsync",
        "-avh",
        "--delete",
    ]

    if dry_run:
        rsync_cmd.append("--dry-run")

    for pattern in EXCLUDES:
        rsync_cmd.extend(["--exclude", pattern])

    ssh_for_rsync = shlex.join(ssh_parts)
    rsync_cmd.extend(
        [
            "-e",
            ssh_for_rsync,
            f"{str(source_dir)}/",
            f"{remote}:{target_dir}/",
        ]
    )

    print(f"[sync] Syncing {source_dir} -> {remote}:{target_dir}")
    subprocess.run(rsync_cmd, check=True)
    print("[sync] Sync complete")


def main() -> None:
    args = parse_args()
    config = build_config(args)
    try:
        sync(config)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}") from exc


if __name__ == "__main__":
    main()
