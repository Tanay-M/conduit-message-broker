"""Native, project-owned PostgreSQL lifecycle and checksum-checked migrations."""

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse
from urllib.request import urlopen

import psycopg
from psycopg import sql

from .settings import ROOT, settings

STATE = ROOT / ".local"
DATA = STATE / "pgdata"


def pg_bin():
    config = STATE / "native.json"
    saved = json.loads(config.read_text()) if config.exists() else {}
    path = Path(
        os.environ.get(
            "CONDUIT_PG_BIN", saved.get("pg_bin", str(ROOT / ".runtime/pgsql/bin"))
        )
    )
    if not (path / "pg_ctl.exe").is_file():
        raise RuntimeError("PostgreSQL binaries missing. Run scripts/setup.ps1.")
    return path


def command(name, *args):
    subprocess.run(
        [str(pg_bin() / (name + ".exe")), *map(str, args)], check=True, cwd=ROOT
    )


def port_open(port):
    with socket.socket() as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def start_database():
    STATE.mkdir(exist_ok=True)
    url = urlparse(settings.admin_dsn)
    if url.hostname not in ("localhost", "127.0.0.1"):
        raise RuntimeError("Native cluster requires a loopback CONDUIT_ADMIN_DSN.")
    if not (DATA / "PG_VERSION").exists():
        password_file = STATE / "init-password.tmp"
        password_file.write_text(url.password or "", encoding="utf-8")
        try:
            command(
                "initdb",
                "-D",
                DATA,
                "-U",
                url.username,
                "--encoding=UTF8",
                "--locale=C",
                "--auth=scram-sha-256",
                f"--pwfile={password_file}",
            )
        finally:
            password_file.unlink(missing_ok=True)
    expected = (
        subprocess.check_output(
            [str(pg_bin() / "postgres.exe"), "--version"], text=True
        )
        .split()[2]
        .split(".")[0]
    )
    if (DATA / "PG_VERSION").read_text().strip() != expected:
        raise RuntimeError(
            "PostgreSQL major version differs from this data directory. Do not reuse it with other binaries."
        )
    status = subprocess.run(
        [str(pg_bin() / "pg_ctl.exe"), "-D", str(DATA), "status"], capture_output=True
    )
    if status.returncode == 0:
        return
    if port_open(url.port or 55432):
        raise RuntimeError(
            f"Port {url.port} is occupied by another process. Change both DSNs in .env.local."
        )
    command(
        "pg_ctl",
        "-D",
        DATA,
        "-l",
        STATE / "postgres.log",
        "-o",
        f"-p {url.port or 55432} -h 127.0.0.1",
        "-w",
        "start",
    )


def migrate(dsn=None):
    dsn = dsn or settings.admin_dsn
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migration (name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())"
        )
        # Existing base scripts own their BEGIN/COMMIT. Seed is an explicit CLI action.
        paths = [
            p
            for p in sorted((ROOT / "db/sql").glob("*.sql"))
            if p.name != "50_seed.sql"
        ]
        paths += sorted((ROOT / "db/migrations").glob("*.sql"))
        for path in paths:
            name = path.relative_to(ROOT).as_posix()
            content = path.read_text(encoding="utf-8")
            digest = hashlib.sha256(content.encode()).hexdigest()
            applied = conn.execute(
                "SELECT sha256 FROM schema_migration WHERE name=%s", (name,)
            ).fetchone()
            if applied:
                if applied[0] != digest:
                    raise RuntimeError(
                        f"Applied migration changed: {name}. Add a new migration instead."
                    )
                continue
            print(f"Applying {name}", flush=True)
            body = re.sub(r"\A\s*BEGIN;\s*", "", content, flags=re.IGNORECASE)
            body = re.sub(r"COMMIT;\s*\Z", "", body, flags=re.IGNORECASE)
            with conn.transaction():
                conn.execute(body, prepare=False)
                conn.execute(
                    "INSERT INTO schema_migration(name,sha256) VALUES (%s,%s)",
                    (name, digest),
                )


def setup():
    STATE.mkdir(exist_ok=True)
    path = pg_bin()
    (STATE / "native.json").write_text(json.dumps({"pg_bin": str(path)}))
    start_database()
    url = urlparse(settings.admin_dsn)
    target = url.path.lstrip("/")
    maintenance = settings.admin_dsn.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(maintenance, autocommit=True) as conn:
        if not conn.execute(
            "SELECT 1 FROM pg_database WHERE datname=%s", (target,)
        ).fetchone():
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    migrate()
    print("Local PostgreSQL and migrations ready.", flush=True)


def start_process(label, args):
    pidfile = STATE / f"{label}.pid.json"
    if pidfile.exists() and process_alive(json.loads(pidfile.read_text())):
        return
    log = open(STATE / f"{label}.log", "ab", buffering=0)
    try:
        process = subprocess.Popen(
            [sys.executable, *args],
            cwd=ROOT,
            stdout=log,
            stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    finally:
        log.close()
    # Keep process creation time to avoid terminating a reused PID during stop.
    import psutil

    pidfile.write_text(
        json.dumps(
            {"pid": process.pid, "created": psutil.Process(process.pid).create_time()}
        )
    )


def process_alive(record):
    import psutil

    try:
        process = psutil.Process(record["pid"])
        return (
            abs(process.create_time() - record["created"]) < 0.01
            and process.is_running()
        )
    except psutil.Error:
        return False


def stop():
    for path in STATE.glob("*.pid.json"):
        stop_process(path)
    if (DATA / "postmaster.pid").exists():
        command("pg_ctl", "-D", DATA, "-m", "fast", "-w", "stop")


def stop_process(path):
    import psutil

    record = json.loads(path.read_text())
    if process_alive(record):
        process = psutil.Process(record["pid"])
        process.terminate()
        try:
            process.wait(10)
        except psutil.TimeoutExpired:
            process.kill()
    path.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["setup", "start", "stop", "doctor", "migrate"]
    )
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.action == "setup":
        setup()
    elif args.action == "migrate":
        migrate()
    elif args.action == "start":
        setup()
        pidpath = STATE / "api.pid.json"
        if port_open(args.port) and not (
            pidpath.exists() and process_alive(json.loads(pidpath.read_text()))
        ):
            raise RuntimeError(
                f"API port {args.port} occupied. Use start.ps1 -Port another_port."
            )
        start_process("api", ["-m", "reporting.api", "--port", str(args.port)])
        desired = {f"worker-{i}.pid.json" for i in range(max(0, min(args.workers, 8)))}
        for existing in STATE.glob("worker-*.pid.json"):
            if existing.name not in desired:
                stop_process(existing)
        for i in range(max(0, min(args.workers, 8))):
            start_process(
                f"worker-{i}", ["-m", "reporting.worker", "--name", f"local-{i}"]
            )
        for _ in range(40):
            try:
                with urlopen(
                    f"http://127.0.0.1:{args.port}/health", timeout=1
                ) as response:
                    if response.status == 200:
                        print(
                            f"API and SQL documentation: http://127.0.0.1:{args.port}/docs"
                        )
                        return
            except OSError:
                time.sleep(0.25)
        raise RuntimeError("API did not start. Inspect .local/api.log.")
    elif args.action == "stop":
        stop()
    else:
        print("Python:", sys.version.split()[0])
        print("Project:", ROOT)
        command("postgres", "--version")
        with psycopg.connect(settings.admin_dsn) as conn:
            print(
                "Database:",
                conn.execute("SELECT current_database(), version()").fetchone(),
            )
            print(
                "Migrations:",
                conn.execute("SELECT count(*) FROM schema_migration").fetchone()[0],
            )


if __name__ == "__main__":
    main()
