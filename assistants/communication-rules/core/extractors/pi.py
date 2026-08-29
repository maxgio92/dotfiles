"""Pi event extraction for the Communication Rules core."""

from __future__ import annotations

from typing import Any

from core.config import Config
from core.dispatch import (
    EVENT_CONTEXT,
    EVENT_FACING,
    EVENT_GATE,
    EVENT_PASS,
    SCAN_BASH,
    SCAN_NONE,
    SCAN_TEXT,
    Extraction,
)
from core.detection import bash_prose_sink, is_bash_gh_post
from core.extractors.claude_code import (
    collect_post_texts,
    external_target,
    is_post_capable_mcp_tool,
)
from core.types import ExtractorRecord


def _record(session: str, tool: str = "", target: str | None = None) -> ExtractorRecord:
    return ExtractorRecord(session=session, turn=None, tool=tool, target=target, texts=[])


def _pass(session: str) -> Extraction:
    return Extraction(record=_record(session), event_class=EVENT_PASS, scan_mode=SCAN_NONE)


def _existing_blocked(payload: dict[str, Any]) -> bool:
    return payload.get("existing_blocked") is True


def _extract_tool_call(payload: dict[str, Any], session: str, config: Config) -> Extraction:
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return Extraction(
            record=_record(session),
            event_class=EVENT_GATE,
            surface="local",
            scan_mode=SCAN_NONE,
            unresolved=True,
            existing_blocked=_existing_blocked(payload),
        )

    normalized_name = tool_name.lower()
    is_external = is_post_capable_mcp_tool(tool_name, config.post_tool_terms)
    if normalized_name == "bash":
        command = tool_input.get("command")
        is_external = isinstance(command, str) and is_bash_gh_post(command)

    surface = "external" if is_external else "local"
    target: str | None = None
    if is_external:
        # The shared helper understands structured MCP targets and Bash gh posts.
        helper_name = "Bash" if normalized_name == "bash" else tool_name
        target = external_target(helper_name, tool_input, config)
    elif normalized_name in {"write", "edit"}:
        path = tool_input.get("path")
        target = path if isinstance(path, str) and path else None

    record = _record(session, tool_name, target)
    common = {
        "record": record,
        "event_class": EVENT_GATE,
        "surface": surface,
        "existing_blocked": _existing_blocked(payload),
    }

    if normalized_name == "write":
        content = tool_input.get("content")
        if not isinstance(content, str):
            return Extraction(scan_mode=SCAN_NONE, unresolved=True, **common)
        record.texts = [content]
        return Extraction(scan_mode=SCAN_TEXT, **common)

    if normalized_name == "edit":
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return Extraction(scan_mode=SCAN_NONE, unresolved=True, **common)
        replacements: list[str] = []
        for edit in edits:
            if not isinstance(edit, dict) or not isinstance(edit.get("newText"), str):
                return Extraction(scan_mode=SCAN_NONE, unresolved=True, **common)
            replacements.append(edit["newText"])
        record.texts = ["\n\n".join(replacements)]
        return Extraction(scan_mode=SCAN_TEXT, **common)

    if normalized_name == "bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return Extraction(scan_mode=SCAN_NONE, unresolved=True, **common)
        record.texts = [command]
        if not is_external:
            record.target = bash_prose_sink(command)
        return Extraction(scan_mode=SCAN_BASH, **common)

    if is_external:
        texts = collect_post_texts(tool_input, frozenset(config.post_text_keys))
        if not texts:
            return Extraction(scan_mode=SCAN_NONE, unresolved=True, **common)
        record.texts = ["\n\n".join(texts)]
        return Extraction(scan_mode=SCAN_TEXT, **common)

    return _pass(session)


def extract(event: str, payload: dict[str, Any], config: Config) -> Extraction:
    """Normalize the Pi extension payload for the shared policy engine."""
    session_id = payload.get("session_id")
    session = session_id if isinstance(session_id, str) else ""

    if event == "Context":
        return Extraction(record=_record(session), event_class=EVENT_CONTEXT, scan_mode=SCAN_NONE)
    if event == "ToolCall":
        return _extract_tool_call(payload, session, config)
    if event == "AgentEnd":
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            return _pass(session)
        record = _record(session, "AgentEnd")
        record.texts = [text]
        return Extraction(
            record=record,
            event_class=EVENT_FACING,
            scan_mode=SCAN_TEXT,
            existing_blocked=_existing_blocked(payload),
        )
    return _pass(session)
