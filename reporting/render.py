"""Deterministic local artifacts; output locations are relative and request-based."""

import csv
import hashlib
import html
import io
import os
from pathlib import Path
import uuid


def documents(report):
    rows = report["rows"]
    fields = sorted({key for row in rows for key in row})
    output = io.StringIO(newline="")
    if fields:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    else:
        output.write("No records for the selected period\n")
    title = html.escape(report["title"])
    cells = "".join("<th>" + html.escape(field) + "</th>" for field in fields)
    body = "".join(
        "<tr>"
        + "".join(
            "<td>" + html.escape(str(row.get(field, ""))) + "</td>" for field in fields
        )
        + "</tr>"
        for row in rows
    )
    page = (
        '<!doctype html><html><head><meta charset="utf-8"><title>' + title + "</title>"
        "<style>body{font:16px Arial;margin:2rem}table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:.5rem}</style></head><body>"
        "<h1>"
        + title
        + "</h1><p>Demonstration data | Run "
        + str(report["run_id"])
        + " | Template version "
        + str(report["version"])
        + "</p>"
        "<p>Period "
        + str(report["start_date"])
        + " to "
        + str(report["end_date"])
        + " (end exclusive)</p>"
        "<table><thead><tr>"
        + cells
        + "</tr></thead><tbody>"
        + body
        + "</tbody></table>"
        + ("<p>No records for this period.</p>" if not rows else "")
        + "</body></html>"
    )
    return {"csv": output.getvalue().encode("utf-8"), "html": page.encode("utf-8")}


def publish(root, request_id, content):
    # Only UUID-based names derived internally; no caller-controlled filesystem paths.
    name = str(uuid.UUID(str(request_id)))
    folder = Path(root) / name[:2]
    folder.mkdir(parents=True, exist_ok=True)
    result = {}
    for extension, data in content.items():
        path = folder / f"{name}.{extension}"
        temporary = folder / f".{name}.{uuid.uuid4().hex}.{extension}.tmp"
        try:
            with temporary.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        result[extension + "_path"] = path.relative_to(root).as_posix()
        result[extension + "_sha256"] = hashlib.sha256(data).hexdigest()
    return result
