#!/usr/bin/env python3
"""Enqueue AnalyzeTrack jobs for every READY catalog track (full reindex).

Usage (from apps/backend, with Compose stack up):

    uv run python scripts/requeue_analysis.py
    uv run python scripts/requeue_analysis.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import func, select

from ox1audio_backend.db import SessionLocal
from ox1audio_backend.models import JobStatus, MlJob, Track, TrackStatus


async def requeue(*, dry_run: bool) -> int:
    async with SessionLocal() as session:
        tracks = (
            await session.scalars(select(Track).where(Track.status == TrackStatus.READY))
        ).all()
        print(f"ready_tracks={len(tracks)}")
        if dry_run:
            return 0

        # Avoid duplicate queued/running jobs for the same track.
        active = (
            await session.scalars(
                select(MlJob.track_id).where(
                    MlJob.status.in_([JobStatus.QUEUED, JobStatus.RUNNING])
                )
            )
        ).all()
        active_ids = set(active)

        created = 0
        for track in tracks:
            if track.id in active_ids:
                continue
            track.status = TrackStatus.QUEUED
            track.error_message = None
            session.add(MlJob(track_id=track.id, status=JobStatus.QUEUED))
            created += 1

        await session.commit()
        queued = await session.scalar(
            select(func.count()).select_from(MlJob).where(MlJob.status == JobStatus.QUEUED)
        )
        print(f"enqueued={created} ml_jobs_queued={queued}")
        return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count READY tracks without enqueueing jobs.",
    )
    args = parser.parse_args()
    asyncio.run(requeue(dry_run=args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
