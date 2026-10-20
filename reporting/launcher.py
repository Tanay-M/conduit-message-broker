"""Double-click demo startup using the existing native service lifecycle."""

import argparse
import csv
import json
import socket
import subprocess
import sys
import webbrowser
from uuid import uuid4

import psutil

from . import demo_operations, local, seed
from .service import connect
from .settings import ROOT


def existing_api_port():
    """Reuse only a live, creation-time-verified API owned by this checkout."""
    record_path = local.STATE / "api.pid.json"
    if not record_path.exists():
        return None
    record = json.loads(record_path.read_text())
    if not local.process_alive(record):
        return None
    args = psutil.Process(record["pid"]).cmdline()
    if "-m" not in args or args[args.index("-m") + 1] != "reporting.api":
        raise RuntimeError(
            "The recorded API process is unexpected. Inspect .local/api.pid.json."
        )
    port = int(args[args.index("--port") + 1]) if "--port" in args else 8000
    if not 1 <= port <= 65535:
        raise RuntimeError("The recorded API port is invalid.")
    return port


def choose_port(preferred):
    running = existing_api_port()
    if running is not None:
        print(f"Reusing this project's running API on port {running}.", flush=True)
        return running
    for port in range(preferred, min(preferred + 20, 65536)):
        try:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", port))
            return port
        except OSError:
            continue
    raise RuntimeError("No available API port nearby. Try -Port 8100 with the launcher.")


def prepare_demo():
    """Supply small fixtures on a clean laptop without resetting existing data."""
    with connect() as conn:
        ready = conn.execute(
            """SELECT EXISTS(SELECT 1 FROM reporting.customer WHERE customer_ref='DEMO-000001')
                AND (SELECT count(*)=30 FROM reporting.product WHERE sku IN
                    (SELECT 'SKU-' || generate_series(1,30))) AS ready"""
        ).fetchone()["ready"]
    if not ready:
        print("Preparing a small sample sales dataset (20 customers).", flush=True)
        seed.seed(customers=20, orders_per_customer=5)
    print(demo_operations.prepare(), flush=True)


def prepare_import_files():
    """Give each launch a matching error/correction pair with fresh order refs."""
    directory = local.STATE / "demo-inputs"
    directory.mkdir(parents=True, exist_ok=True)
    token = uuid4().hex[:12].upper()
    headers = ["OrderNo", "ClientCode", "OrderDate", "LineNo", "ItemCode", "Qty", "Rate"]
    good = f"LIVE-{token}-GOOD"
    bad = f"LIVE-{token}-BAD"
    rows = [
        [good, "DEMO-000001", "2026-10-01", 1, "SKU-1", 2, "25.00"],
        [good, "DEMO-000001", "2026-10-01", 2, "SKU-2", 1, "50.00"],
        [bad, "DEMO-000001", "2026-10-02", 1, "SKU-1", 1, "-10.00"],
    ]
    for filename, price in [
        ("01-sales-with-error.csv", "-10.00"),
        ("02-sales-corrected.csv", "10.00"),
    ]:
        rows[-1][-1] = price
        with (directory / filename).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(headers)
            writer.writerows(rows)
    print(f"Fresh matching demo CSV files: {directory}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--workers", type=int, choices=range(1, 9), default=2)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    port = choose_port(args.port)
    subprocess.run(
        [
            sys.executable, "-m", "reporting.local", "start",
            "--port", str(port), "--workers", str(args.workers),
        ],
        cwd=ROOT,
        check=True,
    )
    prepare_demo()
    prepare_import_files()
    for index in range(args.workers):
        record_path = local.STATE / f"worker-{index}.pid.json"
        if not record_path.exists() or not local.process_alive(
            json.loads(record_path.read_text())
        ):
            raise RuntimeError(
                f"Worker {index} stopped. Inspect .local/worker-{index}.log."
            )
    url = f"http://127.0.0.1:{port}/"
    print(f"\nReady: {url}", flush=True)
    print("Default demo login: admin / Conduit@123 (unless you changed it).", flush=True)
    print("Services keep running when this launcher window closes.", flush=True)
    print("After the demo, double-click STOP_CONDUIT.bat to stop them.", flush=True)
    print("Demo walkthrough: docs/DEMO_WALKTHROUGH.md", flush=True)
    if not args.no_browser:
        try:
            if not webbrowser.open(url):
                print("Open the Ready URL above in your browser.", flush=True)
        except webbrowser.Error:
            print("Open the Ready URL above in your browser.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Conduit startup failed: {exc}", file=sys.stderr)
        sys.exit(1)
