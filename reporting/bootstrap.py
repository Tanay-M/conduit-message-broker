"""Extract only PostgreSQL server/client dependencies, omitting optional GUI tools."""

import sys
from zipfile import ZipFile

from .settings import ROOT


if __name__ == "__main__":
    destination = (ROOT / ".runtime").resolve()
    with ZipFile(sys.argv[1]) as archive:
        for entry in archive.infolist():
            if entry.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                target = (destination / entry.filename).resolve()
                if not target.is_relative_to(destination):
                    raise ValueError("Archive contains an escaping path")
                archive.extract(entry, destination)
