"""Codex hook extraction for the Communication Rules core."""

from __future__ import annotations

import re
from typing import Any

from core.config import Config
from core.dispatch import EVENT_GATE, EVENT_REMINDER, SCAN_NONE, SCAN_TEXT, Extraction
from core.extractors import claude_code
from core.types import ExtractorRecord


_SHELL_TOOLS = {"bash", "exec", "exec_command", "shell", "unified_exec"}
_PATCH_TOOLS = {"apply_patch", "patch"}
_PATCH_TARGET = re.compile(r"^\*\*\* (?:Add|Delete|Update) File: (.+)$", re.MULTILINE)


def _session(payload: dict[str, Any]) -> str:
    value = payload.get("session_id")
    return value if isinstance(value, str) else ""


def _extract_patch(payload: dict[str, Any], tool_name: str) -> Extraction:
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return Extraction(
            record=ExtractorRecord(session=_session(payload), turn=None, tool=tool_name, target=None, texts=[]),
            event_class=EVENT_GATE,
            surface="local",
            scan_mode=SCAN_NONE,
            unresolved=True,
        )

    patch = tool_input.get("patch")
    if not isinstance(patch, str):
        patch = tool_input.get("input")
    if not isinstance(patch, str):
        return Extraction(
            record=ExtractorRecord(session=_session(payload), turn=None, tool=tool_name, target=None, texts=[]),
            event_class=EVENT_GATE,
            surface="local",
            scan_mode=SCAN_NONE,
            unresolved=True,
        )

    match = _PATCH_TARGET.search(patch)
    target = match.group(1).strip() if match else None
    return Extraction(
        record=ExtractorRecord(
            session=_session(payload),
            turn=None,
            tool=tool_name,
            target=target,
            texts=[patch],
        ),
        event_class=EVENT_GATE,
        surface="local",
        scan_mode=SCAN_TEXT,
    )


def _normalize_tool_call(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    tool_name = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return normalized

    lowered = tool_name.lower()
    normalized_input = dict(tool_input)
    if lowered in _SHELL_TOOLS:
        normalized["tool_name"] = "Bash"
        if "command" not in normalized_input and isinstance(normalized_input.get("cmd"), str):
            normalized_input["command"] = normalized_input["cmd"]
    elif lowered == "write":
        normalized["tool_name"] = "Write"
        if "file_path" not in normalized_input and isinstance(normalized_input.get("path"), str):
            normalized_input["file_path"] = normalized_input["path"]
    elif lowered == "edit":
        edits = normalized_input.get("edits")
        if isinstance(edits, list):
            normalized["tool_name"] = "MultiEdit"
            normalized_input["edits"] = [
                {"new_string": edit.get("newText")}
                if isinstance(edit, dict) and isinstance(edit.get("newText"), str)
                else edit
                for edit in edits
            ]
        else:
            normalized["tool_name"] = "Edit"
            if "file_path" not in normalized_input and isinstance(normalized_input.get("path"), str):
                normalized_input["file_path"] = normalized_input["path"]
            if "new_string" not in normalized_input and isinstance(normalized_input.get("newText"), str):
                normalized_input["new_string"] = normalized_input["newText"]
    normalized["tool_input"] = normalized_input
    return normalized


def extract(event: str, payload: dict[str, Any], config: Config) -> Extraction:
    """Normalize Codex hook payloads and reuse the command-agent policy path."""
    if event == "PreToolUse":
        tool_name = payload.get("tool_name")
        if isinstance(tool_name, str) and tool_name.lower() in _PATCH_TOOLS:
            return _extract_patch(payload, tool_name)
        return claude_code.extract(event, _normalize_tool_call(payload), config)

    normalized = dict(payload)
    if event == "SubagentStop" and not normalized.get("transcript_path"):
        normalized["transcript_path"] = normalized.get("agent_transcript_path")
    if event == "SubagentStart":
        return Extraction(
            record=ExtractorRecord(session=_session(payload), turn=None, tool="", target=None, texts=[]),
            event_class=EVENT_REMINDER,
            scan_mode=SCAN_NONE,
        )
    return claude_code.extract(event, normalized, config)
