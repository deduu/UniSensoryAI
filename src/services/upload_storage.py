"""Resolve persisted upload locations across manual and container deployments."""

import asyncio
import os
from pathlib import Path, PurePosixPath
from typing import Annotated

from pydantic import StringConstraints, TypeAdapter, ValidationError

_STORED_PATH = TypeAdapter(Annotated[str, StringConstraints(strict=True, min_length=1)])
_DIRECTORY = TypeAdapter(Path)


def get_upload_directory() -> Path:
    """Return the deployment's configured upload directory without accessing disk.

    Returns:
        The configured upload path, or the existing local-development default.
    """
    return _DIRECTORY.validate_python(os.getenv("UPLOADS_DIR") or "data/uploads")


def _resolve_upload_path(stored_path: str, upload_dir: Path) -> Path:
    root = upload_dir.resolve()
    portable = PurePosixPath(stored_path.replace("\\", "/"))
    if ".." in portable.parts or "\x00" in stored_path or not portable.name:
        raise FileNotFoundError("Uploaded file is unavailable.")

    candidate = Path(stored_path).resolve()
    if candidate.parent != root:
        # The uploader stores flat files. Only known upload locations and plain
        # filenames can move between hosts; arbitrary paths cannot select a copy.
        if len(portable.parts) > 1 and portable.parent.name not in {"uploads", root.name}:
            raise FileNotFoundError("Uploaded file is unavailable.")
        candidate = (root / portable.name).resolve()

    if candidate.parent != root or not candidate.is_file():
        raise FileNotFoundError("Uploaded file is unavailable.")
    return candidate


async def resolve_upload_path(stored_path: str, *, upload_dir: Path | None = None) -> Path:
    """Find an existing upload after a host or operating-system change.

    Args:
        stored_path: Previously persisted native path or upload filename.
        upload_dir: Current upload root, defaulting to the deployment setting.

    Returns:
        An existing file contained directly in the current upload directory.

    Raises:
        FileNotFoundError: The path is invalid, unrelated, missing, or outside storage.
    """
    try:
        validated = _STORED_PATH.validate_python(stored_path)
    except ValidationError:
        raise FileNotFoundError("Uploaded file is unavailable.") from None
    return await asyncio.to_thread(
        _resolve_upload_path,
        validated,
        upload_dir if upload_dir is not None else get_upload_directory(),
    )
