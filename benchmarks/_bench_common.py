import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app/demos")
from _common import ADMIN_DSN, DSN, fixtures, new_admin, new_client  # noqa: E402,F401

RESULTS_DIR = Path("/app/benchmarks/results")


def percentiles(samples_ms):
    s = sorted(samples_ms)

    def pick(p):
        return s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))]

    return {
        "min": round(s[0], 2),
        "p50": round(pick(50), 2),
        "p95": round(pick(95), 2),
        "p99": round(pick(99), 2),
        "max": round(s[-1], 2),
    }


def check(cond, msg):
    print(f"  [{'PASS' if cond else 'FAIL'}] {msg}")
    if not cond:
        raise SystemExit(f"benchmark failed: {msg}")


def save(name, config, rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps({"config": config, "results": rows}, indent=2))
    print(f"  results -> {path}")


def print_table(title, headers, rows):
    print()
    print(f"  {title}")
    widths = []
    for i, h in enumerate(headers):
        values = [len(str(r[i])) for r in rows] + [len(str(h))]
        widths.append(max(values))
    print("  " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)))
    print("  " + "-+-".join("-" * w for w in widths))
    for r in rows:
        print("  " + " | ".join(str(r[i]).ljust(w) for i, w in enumerate(widths)))


def banner(title):
    print()
    print("=" * 64)
    print(f" {title}")
    print("=" * 64)
