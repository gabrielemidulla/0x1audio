"""Ingest worker entrypoint: python -m tunelink_backend.worker"""

from __future__ import annotations

import asyncio

from tunelink_backend.ingest.runner import run_forever


def main() -> None:
    asyncio.run(run_forever())


if __name__ == "__main__":
    main()
