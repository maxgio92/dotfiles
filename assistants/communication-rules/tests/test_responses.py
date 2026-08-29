import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.responses import claude_code_allow, codex_allow, codex_deny
from core.types import Decision


def decision(verb: str, notice: str = "revise this text") -> Decision:
    return Decision(
        decision=verb,
        surface="B1",
        level="warning",
        notice=notice,
        inject_base_rules=False,
        append_correction=False,
    )


class CommandResponseTest(unittest.TestCase):
    def test_codex_non_blocking_response_does_not_override_permission(self) -> None:
        response = codex_allow(decision("allow-revise"))

        output = response["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertEqual(output["additionalContext"], "revise this text")
        self.assertNotIn("permissionDecision", output)

    def test_codex_deny_keeps_supported_permission_decision(self) -> None:
        response = codex_deny("blocked by communication rules")

        output = response["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertEqual(output["permissionDecisionReason"], "blocked by communication rules")

    def test_claude_allow_contract_is_unchanged(self) -> None:
        response = claude_code_allow(decision("allow-revise"))

        self.assertEqual(response["hookSpecificOutput"]["permissionDecision"], "allow")


if __name__ == "__main__":
    unittest.main()
