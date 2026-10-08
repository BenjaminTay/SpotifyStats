from __future__ import annotations

import pytest

from scripts.versus_personal_browser_probe import classify_console, is_expected_forward_teardown

pytestmark = pytest.mark.unit

KNOWN_PRELOAD_WARNING = (
    "The resource https://stats.benjaminlei.site/assets/index-DHPPTUCB.js "
    "was preloaded using link preload but not used within a few seconds "
    "from the window's load event. Please make sure it wasn't preloaded for nothing."
)


def test_known_browser_preload_warning_is_accepted_and_raw_entry_is_preserved():
    warning = {"type": "warning", "text": KNOWN_PRELOAD_WARNING}
    messages = [warning]

    accepted, blocking = classify_console(messages)

    assert accepted == [warning]
    assert accepted[0] is warning
    assert blocking == []
    assert messages == [warning]


@pytest.mark.parametrize(
    "kind,text",
    [
        ("error", KNOWN_PRELOAD_WARNING),
        ("pageerror", KNOWN_PRELOAD_WARNING),
        ("warning", "Failed to preload resource: HTTP 500"),
        ("warning", KNOWN_PRELOAD_WARNING.replace("within a few seconds", "before loading")),
        ("error", "TypeError: Cannot read properties of undefined"),
        ("pageerror", "ChunkLoadError: Failed to load module script"),
    ],
)
def test_other_warning_and_real_error_remain_blocking(kind, text):
    entry = {"type": kind, "text": text}

    accepted, blocking = classify_console([entry])

    assert accepted == []
    assert blocking == [entry]


def test_accepted_preload_diagnostic_cannot_hide_an_adjacent_application_error():
    warning = {"type": "warning", "text": KNOWN_PRELOAD_WARNING}
    error = {"type": "error", "text": "Personal ranks request failed: HTTP 503"}
    messages = [warning, error]

    accepted, blocking = classify_console(messages)

    assert accepted == [warning]
    assert blocking == [error]
    assert messages == [warning, error]


@pytest.mark.parametrize(
    "closing,message,expected",
    [
        (False, "Response has been disposed", False),
        (False, "Target page, context or browser has been closed", False),
        (True, "Response has been disposed", True),
        (True, "Target page, context or browser has been closed", True),
        (True, "Request timed out", False),
        (False, "Connection refused", False),
        (True, "Unexpected invalid content encoding", False),
        (True, "Unexpected disposed buffer", False),
        (True, "Connection closed by malformed response", False),
    ],
)
def test_forward_teardown_acceptance_requires_closing_and_known_error(closing, message, expected):
    assert is_expected_forward_teardown(RuntimeError(message), closing) is expected
