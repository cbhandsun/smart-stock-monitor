"""Regression tests that credentials never survive logging boundaries."""

import ast
import io
import logging
from pathlib import Path

from core.logging_utils import (
    RedactingFormatter,
    SensitiveDataFilter,
    redact_text,
    sanitize_log_data,
)


def test_redact_text_removes_bearer_and_jwt_tokens():
    jwt_token = "eyJheader.payload.signature"
    message = f"Authorization: Bearer super-secret token={jwt_token}"
    redacted = redact_text(message)

    assert "super-secret" not in redacted
    assert jwt_token not in redacted
    assert "[REDACTED]" in redacted


def test_structured_metadata_redacts_sensitive_keys_recursively():
    sanitized = sanitize_log_data(
        {
            "headers": {"Authorization": "Bearer secret"},
            "nested": {"api_key": "abc", "status": "ok"},
        }
    )

    assert sanitized["headers"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["status"] == "ok"


def test_exception_message_is_redacted_after_formatting():
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.addFilter(SensitiveDataFilter())
    handler.setFormatter(RedactingFormatter("%(levelname)s %(message)s"))
    logger = logging.getLogger("test-redaction")
    logger.handlers = [handler]
    logger.propagate = False
    logger.setLevel(logging.ERROR)

    try:
        raise RuntimeError("password=hunter2")
    except RuntimeError:
        logger.exception("request failed")

    rendered = output.getvalue()
    assert "hunter2" not in rendered
    assert "[REDACTED]" in rendered


def test_production_logs_do_not_interpolate_raw_exception_objects():
    repository_root = Path(__file__).resolve().parents[1]
    violations = []
    for relative_root in (
        "auth",
        "components",
        "core",
        "database",
        "modules",
        "pages",
        "tasks",
        "utils",
    ):
        for path in (repository_root / relative_root).rglob("*.py"):
            if path.as_posix().endswith(("modules/cache.py", "modules/utils.py")):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(
                    node.func, ast.Attribute
                ):
                    continue
                if node.func.attr not in {
                    "debug",
                    "info",
                    "warning",
                    "error",
                    "exception",
                    "critical",
                }:
                    continue
                if (
                    not isinstance(node.func.value, ast.Name)
                    or node.func.value.id != "logger"
                ):
                    continue
                for argument in node.args:
                    if not isinstance(argument, ast.JoinedStr):
                        continue
                    names = {
                        formatted.value.id
                        for formatted in argument.values
                        if isinstance(formatted, ast.FormattedValue)
                        and isinstance(formatted.value, ast.Name)
                    }
                    if names & {"e", "exc", "err", "error"}:
                        violations.append(
                            f"{path.relative_to(repository_root)}:{node.lineno}"
                        )

    assert violations == []
