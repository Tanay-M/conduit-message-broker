"""Measure actual distinct customer reports, not just queue insertion speed."""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

import psutil

from . import service
from .seed import seed
from .settings import ROOT, settings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--customers", type=int, default=100)
    parser.add_argument("--orders", type=int, default=10)
    parser.add_argument("--workers", type=int, default=2, choices=range(1, 9))
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", default="artifacts/report-benchmark.json")
    args = parser.parse_args()
    loaded = seed(args.customers, args.orders)
    # Drain earlier report work so it does not contaminate this run's timing.
    subprocess.run(
        [sys.executable, "-m", "reporting.worker", "--drain"], cwd=ROOT, check=True
    )
    started = time.perf_counter()
    run = service.submit("customer_statement", "2026-01-01", "2027-01-01", bulk=True)
    enqueue_seconds = time.perf_counter() - started
    children = []
    logs = []
    try:
        for i in range(args.workers):
            log_path = ROOT / ".local" / f"benchmark-worker-{i}.log"
            handle = log_path.open("wb")
            logs.append(handle)
            children.append(
                subprocess.Popen(
                    [sys.executable, "-m", "reporting.worker", "--name", f"bench-{i}"],
                    cwd=ROOT,
                    stdout=handle,
                    stderr=handle,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
            )
        previous = None
        while time.perf_counter() - started < args.timeout:
            status = service.progress(run)
            if status != previous:
                print(json.dumps(status, default=str), flush=True)
                previous = status
            if (
                status["preparation_status"] == "ready"
                and status["completed"] + status["failed"] == status["expected"]
            ):
                break
            if status["preparation_status"] == "failed" or any(
                p.poll() is not None for p in children
            ):
                raise RuntimeError(
                    "Worker or data preparation failed; inspect .local/benchmark-worker-*.log"
                )
            time.sleep(2)
        else:
            raise RuntimeError(
                "Benchmark timeout; requests remain saved and can be resumed"
            )
    finally:
        for process in children:
            process.terminate()
        for process in children:
            process.wait()
        for log in logs:
            log.close()
    elapsed = time.perf_counter() - started
    with service.connect() as conn:
        results = conn.execute(
            """SELECT x.* FROM reporting.report_result x
            JOIN reporting.report_request q USING(request_id) WHERE q.run_id=%s""",
            (run,),
        ).fetchall()
        timing = conn.execute(
            """SELECT
            extract(epoch FROM (r.prepared_at-r.created_at)) AS preparation_seconds,
            percentile_cont(.5) WITHIN GROUP(ORDER BY extract(epoch FROM (q.completed_at-q.created_at))) AS completion_p50_seconds,
            percentile_cont(.95) WITHIN GROUP(ORDER BY extract(epoch FROM (q.completed_at-q.created_at))) AS completion_p95_seconds
            FROM reporting.report_run r JOIN reporting.report_request q USING(run_id)
            WHERE r.run_id=%s GROUP BY r.run_id""",
            (run,),
        ).fetchone()
        environment = conn.execute(
            "SELECT version() AS postgres,current_setting('shared_buffers') AS shared_buffers"
        ).fetchone()
    files = 0
    size = 0
    for result in results:
        for extension in ("csv", "html"):
            path = settings.output_dir / result[extension + "_path"]
            content = path.read_bytes()
            if hashlib.sha256(content).hexdigest() != result[extension + "_sha256"]:
                raise RuntimeError(f"Output checksum mismatch: {path.name}")
            files += 1
            size += len(content)
    output = {
        "run_id": str(run),
        "dataset": loaded,
        "workers": args.workers,
        "submission_seconds": enqueue_seconds,
        "end_to_end_seconds": elapsed,
        "completed_per_second": status["completed"] / elapsed,
        "status": status,
        "timing": timing,
        "verified_result_rows": len(results),
        "verified_files": files,
        "output_bytes": size,
        "sum_worker_sql_seconds": sum(r["sql_seconds"] for r in results),
        "sum_worker_render_seconds": sum(r["render_seconds"] for r in results),
        "environment": {
            **environment,
            "os": platform.platform(),
            "python": platform.python_version(),
            "logical_cpus": os.cpu_count(),
            "memory_bytes": psutil.virtual_memory().total,
        },
        "limits": "Single measured run, shared local machine; includes SQL, queue and CSV/HTML rendering. Not a pure PostgreSQL or PDF benchmark.",
    }
    target = ROOT / args.output
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, default=str, indent=2))
    print(
        f"Verified {len(results)} distinct report results and {files} files. Evidence: {target}",
        flush=True,
    )
    if status["failed"] or len(results) != status["expected"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
