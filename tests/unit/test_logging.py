"""Tests for src/utils/logging.py — structured logging configuration."""

import json
import logging

import pytest
import structlog

from src.utils.logging import configure_logging, get_logger


class TestConfigureLogging:
    def test_json_output_produces_valid_json(self, capsys):
        """JSON mode should emit parseable JSON lines."""
        configure_logging(json_output=True, log_level="INFO")
        test_logger = get_logger("test.json")
        test_logger.info("test_event", key="value", count=42)

        captured = capsys.readouterr()
        # Should contain valid JSON with our fields
        for line in captured.out.strip().split("\n"):
            if "test_event" in line:
                data = json.loads(line)
                assert data["event"] == "test_event"
                assert data["key"] == "value"
                assert data["count"] == 42
                assert "timestamp" in data
                assert "level" in data or "log_level" in data
                break
        else:
            pytest.fail("Did not find test_event in log output")

    def test_console_output_is_human_readable(self, capsys):
        """Console mode should produce human-readable output."""
        configure_logging(json_output=False, log_level="INFO")
        test_logger = get_logger("test.console")
        test_logger.info("console_event", detail="readable")

        captured = capsys.readouterr()
        assert "console_event" in captured.out
        assert "readable" in captured.out

    def test_log_level_filtering(self, capsys):
        """Messages below configured level should be suppressed."""
        configure_logging(json_output=False, log_level="WARNING")
        test_logger = get_logger("test.level")
        test_logger.info("should_not_appear")
        test_logger.warning("should_appear")

        captured = capsys.readouterr()
        assert "should_not_appear" not in captured.out
        assert "should_appear" in captured.out


class TestGetLogger:
    def test_returns_bound_logger(self):
        """get_logger should return a structlog BoundLogger."""
        configure_logging(json_output=False)
        logger = get_logger("test.bound")
        # structlog loggers have info, warning, error methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert hasattr(logger, "bind")

    def test_logger_supports_context_binding(self, capsys):
        """Bound context should appear in log output."""
        configure_logging(json_output=True, log_level="INFO")
        logger = get_logger("test.bind")
        bound = logger.bind(request_id="abc-123")
        bound.info("bound_event")

        captured = capsys.readouterr()
        for line in captured.out.strip().split("\n"):
            if "bound_event" in line:
                data = json.loads(line)
                assert data["request_id"] == "abc-123"
                break
