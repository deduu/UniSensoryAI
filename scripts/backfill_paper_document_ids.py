"""Add missing PAPER source IDs from stored artifacts; dry-run unless --apply.

Run in the application's configured environment, for example:
    python scripts/backfill_paper_document_ids.py --tenant-id TENANT --job-id JOB
    python scripts/backfill_paper_document_ids.py --tenant-id TENANT --job-id JOB --apply

Only meta.document_id is added. Source artifacts, versions, approvals, archive
state, all other metadata and processing timestamps remain unchanged.

Tenant-wide batches inspect the first --limit jobs before skipping existing IDs;
repeating a batch does not advance a cursor. The default is 20 and the maximum is
100. Use an exact --job-id for records outside that window.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Permit the same direct script invocation as existing repository utilities.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.paper.workspace.backfill_query import SourceIdentityBackfillQuery
from src.services.paper_source_identity_backfill import backfill_source_identities


def _arguments() -> SourceIdentityBackfillQuery:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--job-id")
    parser.add_argument("--limit", type=int, default=20)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="Validate and report without writes (default)."
    )
    mode.add_argument(
        "--apply", action="store_true", help="Commit validated additive metadata repairs."
    )
    args = parser.parse_args()
    return SourceIdentityBackfillQuery(
        tenant_id=args.tenant_id, job_id=args.job_id, limit=args.limit, apply=args.apply
    )


async def _main(query: SourceIdentityBackfillQuery) -> int:
    if not os.getenv("DATABASE_URL"):
        await asyncio.to_thread(load_dotenv, dotenv_path=Path.cwd() / ".env")
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL is required in the application environment.", file=sys.stderr)
        return 2
    engine = create_async_engine(url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            result = await backfill_source_identities(db, query)
            if query.apply:
                await asyncio.wait_for(db.commit(), timeout=15)
            else:
                await db.rollback()
            print(result.model_dump_json())
        return 0
    except Exception:  # noqa: BLE001 - do not expose credentials, paths or source content
        print("Source index repair failed; uncommitted changes were rolled back.", file=sys.stderr)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main(_arguments())))
