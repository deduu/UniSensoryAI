"""Seed the database with the existing Acme AI policy for the demo.

Uploads data/demo/acme_existing_ai_policy.docx via POST /v1/process_document,
polls until parsing completes, and prints the resulting document ID.
After this runs, the proposed-policy upload's policy review will have a real
reference corpus to compare against.

Usage:
    python scripts/demo_seed.py
    python scripts/demo_seed.py --api http://localhost:8000 --model gpt-4o

Environment overrides:
    DEMO_API_URL    base API URL (default http://localhost:8000)
    DEMO_MODEL_ID   model id used for the inference stage (default gpt-4o)
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests


_DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"
_EXISTING_POLICY = _DEMO_DIR / "acme_existing_ai_policy.docx"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--api",
        default=os.environ.get("DEMO_API_URL", "http://localhost:8000"),
        help="Base URL of the running API (default %(default)s)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DEMO_MODEL_ID", "gpt-4o"),
        help="Model id to use for the inference stage (default %(default)s)",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=_EXISTING_POLICY,
        help="Policy file to upload (default %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=180,
        help="Seconds to wait for processing to complete (default %(default)s)",
    )
    return parser.parse_args()


def _upload(api: str, file_path: Path, model_id: str) -> str:
    if not file_path.exists():
        raise SystemExit(f"File not found: {file_path}. Run scripts/build_demo_docs.py first.")
    with open(file_path, "rb") as fh:
        response = requests.post(
            f"{api}/v1/process_document",
            files={"file": (file_path.name, fh)},
            data={"model_id": model_id},
            timeout=30,
        )
    if response.status_code != 202:
        raise SystemExit(
            f"Upload failed ({response.status_code}): {response.text[:500]}"
        )
    payload = response.json()
    job_id = payload.get("job_id")
    if not job_id:
        raise SystemExit(f"Upload response missing job_id: {payload}")
    return job_id


def _poll(api: str, job_id: str, timeout: int) -> dict:
    deadline = time.monotonic() + timeout
    last_status = None
    while time.monotonic() < deadline:
        response = requests.get(f"{api}/v1/jobs/{job_id}", timeout=10)
        if response.status_code != 200:
            raise SystemExit(
                f"Status fetch failed ({response.status_code}): {response.text[:500]}"
            )
        payload = response.json()
        status = payload.get("status")
        if status != last_status:
            print(f"  status: {status}")
            last_status = status
        if status == "COMPLETED":
            return payload
        if status == "FAILED":
            error = (payload.get("meta") or {}).get("error", "unknown error")
            raise SystemExit(f"Job failed: {error}")
        time.sleep(2)
    raise SystemExit(f"Timed out after {timeout}s waiting for job {job_id}")


def main() -> None:
    args = _parse_args()
    print(f"Seeding demo policy from {args.file}")
    print(f"API: {args.api}    model: {args.model}")

    try:
        job_id = _upload(args.api, args.file, args.model)
    except requests.ConnectionError:
        sys.exit(
            f"Could not connect to {args.api}. Start the API first: "
            "uvicorn src.api.server:app --reload --port 8000"
        )

    print(f"Job queued: {job_id}")
    payload = _poll(args.api, job_id, args.timeout)

    documents = payload.get("documents") or []
    if not documents:
        sys.exit("Job completed but produced no documents.")

    document = documents[0]
    print()
    print("Seeded existing policy successfully.")
    print(f"  job_id      = {job_id}")
    print(f"  document_id = {document.get('id')}")
    print(f"  filename    = {document.get('filename')}")
    print(
        "Now upload the proposal (data/demo/acme_proposed_ai_policy.docx) via "
        "the dashboard at http://localhost:5173 and run the policy review."
    )


if __name__ == "__main__":
    main()
