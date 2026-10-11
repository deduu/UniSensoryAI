"""Tests for src/pipeline/stages/content_validation_stage.py."""

import sys
from typing import Any, Dict, List
from unittest.mock import MagicMock

import pytest
from PIL import Image

_MOCK_MODULES = [
    "fitz",
    "torch", "torch.cuda", "torch.nn", "torch.nn.functional",
    "torchvision", "torchvision.transforms",
    "transformers", "accelerate", "bitsandbytes",
]
for _mod in _MOCK_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

from src.inference.concurrency import reset_registry
from src.ingestion.pdf_hybrid import PageBundle
from src.pipeline.stages.content_validation_stage import ContentValidationStage


@pytest.fixture(autouse=True)
def _patch_concurrency(monkeypatch):
    reset_registry()
    monkeypatch.setattr(
        "src.inference.concurrency.ConfigLoader.get_model_config",
        lambda model_id, validate=True: {"provider": "openai", "concurrency": 8},
    )
    yield
    reset_registry()


class _ScriptedModel:
    def __init__(self, replies: List[str]) -> None:
        self._replies = list(replies)
        self.calls: List[Dict[str, Any]] = []

    def process(self, image: bytes, prompt: str) -> Dict[str, str]:
        self.calls.append({"prompt": prompt, "image_size": len(image)})
        if not self._replies:
            return {"content": ""}
        return {"content": self._replies.pop(0)}


def _full_page_bundle(page_no: int) -> PageBundle:
    return PageBundle(
        page_no=page_no,
        text_layer="",
        image_regions=[],
        full_page_image=Image.new("RGB", (16, 16), color="white"),
        needs_full_page_vlm=True,
    )


def _text_bundle(page_no: int, text: str) -> PageBundle:
    return PageBundle(
        page_no=page_no,
        text_layer=text,
        image_regions=[],
        full_page_image=None,
        needs_full_page_vlm=False,
    )


@pytest.mark.asyncio
async def test_no_findings_for_ok_response():
    model = _ScriptedModel(["OK", "OK"])
    stage = ContentValidationStage()
    ctx = {
        "model_id": "m",
        "model_instance": model,
        "raw_results": ["page one", "page two"],
        "page_bundles": [_full_page_bundle(1), _full_page_bundle(2)],
    }
    result = await stage.execute(ctx)
    assert result.get("validation_errors", []) == []
    assert len(model.calls) == 2


@pytest.mark.asyncio
async def test_records_findings():
    model = _ScriptedModel([
        "MISSING: footer page numbers\nHALLUCINATED: bogus disclaimer",
        "OK",
    ])
    stage = ContentValidationStage()
    ctx = {
        "model_id": "m",
        "model_instance": model,
        "raw_results": ["p1", "p2"],
        "page_bundles": [_full_page_bundle(1), _full_page_bundle(2)],
    }
    result = await stage.execute(ctx)

    errors = result["validation_errors"]
    assert len(errors) == 1
    assert errors[0]["stage"] == "content_validation"
    assert errors[0]["page"] == 1
    assert "MISSING:" in errors[0]["notes"]


@pytest.mark.asyncio
async def test_skips_text_layer_pages():
    """Text-layer pages did not pass through the VLM; nothing to audit."""
    model = _ScriptedModel([])
    stage = ContentValidationStage()
    ctx = {
        "model_id": "m",
        "model_instance": model,
        "raw_results": ["text body"],
        "page_bundles": [_text_bundle(1, "text body")],
    }
    result = await stage.execute(ctx)

    assert model.calls == []
    assert result.get("validation_errors", []) == []


@pytest.mark.asyncio
async def test_no_bundles_is_noop():
    """Office/image jobs (no PageBundles) skip the critic entirely."""
    model = _ScriptedModel([])
    stage = ContentValidationStage()
    ctx = {
        "model_id": "m",
        "model_instance": model,
        "raw_results": ["body"],
        # page_bundles absent
    }
    result = await stage.execute(ctx)
    assert model.calls == []
    assert result.get("validation_errors", []) == []


@pytest.mark.asyncio
async def test_skips_empty_extraction():
    """If a page returned no extracted text, the critic has nothing to audit."""
    model = _ScriptedModel([])
    stage = ContentValidationStage()
    ctx = {
        "model_id": "m",
        "model_instance": model,
        "raw_results": [""],
        "page_bundles": [_full_page_bundle(1)],
    }
    result = await stage.execute(ctx)
    assert model.calls == []
    assert result.get("validation_errors", []) == []


@pytest.mark.asyncio
async def test_model_failure_does_not_raise():
    class _Boom:
        def process(self, image, prompt):
            raise RuntimeError("model down")

    stage = ContentValidationStage()
    ctx = {
        "model_id": "m",
        "model_instance": _Boom(),
        "raw_results": ["page text"],
        "page_bundles": [_full_page_bundle(1)],
    }
    # Critic failure must not break the pipeline; treated as "no findings".
    result = await stage.execute(ctx)
    assert result.get("validation_errors", []) == []
