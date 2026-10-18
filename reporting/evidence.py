"""Execute the review SQL with code and actual output captured together."""

import os
import subprocess
from urllib.parse import urlparse

from .local import pg_bin
from .settings import ROOT, settings


if __name__ == "__main__":
    url = urlparse(settings.admin_dsn)
    environment = {**os.environ, "PGPASSWORD": url.password or ""}
    target = ROOT / "artifacts/dbms-evidence.txt"
    target.parent.mkdir(exist_ok=True)
    with target.open("w", encoding="utf-8") as handle:
        result = subprocess.run(
            [
                str(pg_bin() / "psql.exe"),
                "-X",
                "-h",
                url.hostname,
                "-p",
                str(url.port),
                "-U",
                url.username,
                "-d",
                url.path.lstrip("/"),
                "-a",
                "-f",
                str(ROOT / "db/evidence/reporting_review.sql"),
            ],
            env=environment,
            stdout=handle,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=ROOT,
        )
    print(target)
    raise SystemExit(result.returncode)
