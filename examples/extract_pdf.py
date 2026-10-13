"""Run the reusable extraction facade from an external application's entry point."""

import argparse
import asyncio
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import structlog

from src.extraction import ExternalSchema, ExtractionOptions, PdfSource, build_extraction_service


async def main() -> None:
    """Read CLI inputs, extract a PDF, print JSON, and release owned providers."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--mode", choices=("text", "multimodal"), default="text")
    parser.add_argument(
        "--ocr", action="store_true", help="Use the configured vision profile for scans"
    )
    parser.add_argument("--config", type=Path, help="Deployment YAML with model profile bindings")
    parser.add_argument(
        "--schema", type=Path, help="External JSON Schema object or versioned envelope"
    )
    args = parser.parse_args()
    schema = None
    if args.schema is not None:
        value = json.loads(await asyncio.to_thread(args.schema.read_text, encoding="utf-8"))
        schema = (
            ExternalSchema.model_validate(value)
            if "json_schema" in value
            else ExternalSchema(json_schema=value)
        )
    structlog.configure(
        processors=[structlog.processors.JSONRenderer()],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    # The CLI owns this process: third-party informational prints go to stderr.
    with redirect_stdout(sys.stderr):
        service = await build_extraction_service(config_path=args.config)
        try:
            result = await service.extract(
                PdfSource(path=args.pdf),
                options=ExtractionOptions(
                    content_mode=args.mode,
                    text_strategy="native_then_ocr" if args.ocr else "native_only",
                ),
                schema=schema,
            )
        finally:
            await service.aclose()
    await asyncio.to_thread(print, result.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())
