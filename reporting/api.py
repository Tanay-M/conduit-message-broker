"""ASGI launcher with the Windows selector loop required by psycopg async."""

import argparse
import asyncio
import sys

import uvicorn


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = uvicorn.Server(
        uvicorn.Config("server.app.main:app", host="127.0.0.1", port=args.port)
    )
    if sys.platform == "win32":
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            runner.run(server.serve())
    else:
        asyncio.run(server.serve())


if __name__ == "__main__":
    main()
