"""Tests for src/pipeline/prompts.py — PromptRegistry resolution."""

from pathlib import Path

import pytest

from src.pipeline.prompts import (
    PromptRegistry,
    get_prompts,
    reset_prompts,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_prompts()
    yield
    reset_prompts()


@pytest.fixture
def prompts_yaml(tmp_path) -> Path:
    """Write a small prompts.yaml fixture and return its path."""
    payload = """
prompts:
  generic:
    page: "Generic page prompt."
    figure: "Generic figure prompt."
    table: "Generic table prompt."
  invoice:
    page: "Invoice page prompt."
    table: "Invoice table prompt."
  receipt:
    page: "Receipt page prompt."
"""
    fp = tmp_path / "prompts.yaml"
    fp.write_text(payload, encoding="utf-8")
    return fp


def test_exact_subtype_region_match(prompts_yaml):
    reg = PromptRegistry(config_path=prompts_yaml)
    assert reg.get("invoice", "page") == "Invoice page prompt."
    assert reg.get("invoice", "table") == "Invoice table prompt."


def test_falls_back_to_generic_when_subtype_missing(prompts_yaml):
    reg = PromptRegistry(config_path=prompts_yaml)
    # "invoice" has no "figure" entry → falls back to generic.figure.
    assert reg.get("invoice", "figure") == "Generic figure prompt."


def test_falls_back_to_generic_when_subtype_unknown(prompts_yaml):
    reg = PromptRegistry(config_path=prompts_yaml)
    assert reg.get("martian", "page") == "Generic page prompt."


def test_no_subtype_uses_generic(prompts_yaml):
    reg = PromptRegistry(config_path=prompts_yaml)
    assert reg.get(None, "page") == "Generic page prompt."
    # Default region is "page".
    assert reg.get() == "Generic page prompt."


def test_falls_back_to_builtin_when_config_missing(tmp_path):
    # Point at a non-existent file so the registry uses the built-in map.
    reg = PromptRegistry(config_path=tmp_path / "does_not_exist.yaml")
    page_prompt = reg.get("anything", "page")
    assert "faithful Markdown" in page_prompt


def test_real_config_loads(tmp_path):
    """Confirm the shipped configs/prompts.yaml resolves invoice prompts."""
    reg = get_prompts()  # uses default config path
    page = reg.get("invoice", "page")
    # At minimum, the invoice prompt must mention invoice-specific concepts.
    assert "invoice" in page.lower() or "line item" in page.lower()


def test_singleton():
    a = get_prompts()
    b = get_prompts()
    assert a is b
    reset_prompts()
    c = get_prompts()
    assert c is not a
