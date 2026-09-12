import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import Config
from core.detection import extract_post_texts, has_api_post_signal, is_bash_gh_post, is_known_post_command, scan_bash
from core.extractors.claude_code import external_target


class GhPostCommandPathTest(unittest.TestCase):
    """A path-qualified post helper must classify the same as its bare name.

    ``is_known_post_command`` already compares the basename; ``is_bash_gh_post``
    must agree, or a ``bin/gh-review-reply`` post lands on the local-file (B1)
    policy instead of the irretractable external (B2) one.
    """

    COMMANDS = (
        "gh-review-reply",
        "bin/gh-review-reply",
        "/home/user/.local/bin/gh-review-reply",
    )

    def test_gh_review_reply_is_external_regardless_of_path(self) -> None:
        for prefix in self.COMMANDS:
            command = f"{prefix} https://github.com/a/b/pull/1#discussion_r5 --body-file reply.md"
            with self.subTest(command=command):
                self.assertTrue(is_known_post_command(command.split()))
                self.assertTrue(is_bash_gh_post(command))

    def test_path_qualified_gh_api_post_is_external(self) -> None:
        command = "/usr/bin/gh api repos/a/b/issues -f title=x"
        self.assertTrue(is_known_post_command(command.split()))
        self.assertTrue(is_bash_gh_post(command))

    def test_unrelated_command_with_matching_suffix_is_not_external(self) -> None:
        self.assertFalse(is_bash_gh_post("cat notes/gh-review-reply --body-file reply.md"))
        self.assertFalse(is_bash_gh_post("gh pr view 1"))

    def test_compound_command_with_a_gh_post_segment_is_external(self) -> None:
        for command in (
            "cd repo && gh pr comment 1 --body-file reply.md",
            "git fetch && ./bin/gh-review-reply https://github.com/a/b/pull/1#discussion_r5 --body-file reply.md",
            "true || GH_TOKEN=x gh api repos/a/b/issues -XPOST",
        ):
            with self.subTest(command=command):
                self.assertTrue(is_bash_gh_post(command))
        self.assertFalse(is_bash_gh_post("cd repo && gh pr view 1"))

    def test_piped_or_multiline_gh_post_is_external(self) -> None:
        for command in (
            "cat reply.md | gh pr comment 1 -F -",
            "true | gh-review-reply https://github.com/a/b/pull/1#discussion_r5 --body-file reply.md",
            "cd repo\ngh pr comment 1 --body-file reply.md",
            "bash -c 'true | gh pr comment 1 --body hi'",
        ):
            with self.subTest(command=command):
                self.assertTrue(is_bash_gh_post(command))
        self.assertFalse(is_bash_gh_post("cat notes.md | gh pr view 1"))


class GhApiWriteFormsTest(unittest.TestCase):
    """Every pflag spelling of a gh api write must count, matching the pi gate."""

    WRITES = (
        "gh api repos/a/b/issues -XPOST",
        "gh api repos/a/b/issues -X POST",
        "gh api repos/a/b/comments/5 -X=DELETE",
        "gh api repos/a/b/issues -f=body=x",
        "gh api repos/a/b/issues --method=POST",
        "gh api repos/a/b/issues --method PATCH",
        "gh api repos/a/b/issues -fbody=x",
        "gh api repos/a/b/issues -Fbody=@f",
        "gh api repos/a/b/issues --field=body=x",
        "gh api repos/a/b/issues --raw-field=body=x",
        "gh api repos/a/b/issues --input=file",
        "gh api repos/a/b/issues --input -",
    )
    READS = (
        "gh api repos/a/b/pulls/1",
        "gh api repos/a/b/pulls/1 -X GET",
        "gh api repos/a/b/pulls/1 -XGET --jq .title",
        "gh api repos/a/b/pulls/1 -H 'Accept: application/json'",
        # An attached ``-f...`` token outside ``gh api`` is an option value, not
        # a request field.
        "gh pr list --search '-flaky'",
        "gh issue list --label -foo",
    )

    def test_write_forms_are_posts(self) -> None:
        for command in self.WRITES:
            with self.subTest(command=command):
                argv = command.split()
                self.assertTrue(has_api_post_signal(argv[2:]))
                self.assertTrue(is_known_post_command(argv))
                self.assertTrue(is_bash_gh_post(command))

    def test_equals_joined_short_field_is_extracted(self) -> None:
        texts, unresolved = extract_post_texts(["gh", "api", "x", "-f=body=delve"], {})
        self.assertEqual(texts, ["delve"])
        self.assertFalse(unresolved)

    def test_read_forms_are_not_posts(self) -> None:
        for command in self.READS:
            with self.subTest(command=command):
                self.assertFalse(is_bash_gh_post(command))


class ScanBashPipeTest(unittest.TestCase):
    """The body scan reaches a gh post behind a pipe, as the classifier does."""

    def test_piped_gh_post_body_is_scanned(self) -> None:
        config = Config(
            rules_text="",
            reminder_prompt=None,
            block_message=None,
            policy={"hardGateBannedTerms": ["delve"]},
        )
        self.assertTrue(scan_bash("true | gh pr comment 1 --body 'we delve into it'", config))
        self.assertFalse(scan_bash("true | gh pr comment 1 --body 'fixed in a1b2c3d'", config))
        self.assertFalse(scan_bash("cat notes.md | gh pr view 1", config))
        # A quoted '|' argument is a bare token after shlex; it must not cut a
        # gh api post off its body.
        self.assertTrue(
            scan_bash("gh api repos/a/b/issues/1/comments --template '|' -f body='we delve into it'", config)
        )


class ExternalTargetTest(unittest.TestCase):
    """The yield notice names the post helper by basename, in any chained position."""

    def test_names_the_post_segment(self) -> None:
        config = Config(rules_text="", reminder_prompt=None, block_message=None, policy={})
        cases = {
            "gh pr comment 1 --body-file f": "gh pr comment",
            "./bin/gh-review-reply https://github.com/a/b/pull/1#discussion_r5 --body-file f": "gh-review-reply https://github.com/a/b/pull/1#discussion_r5 --body-file",
            "cd repo && gh issue comment 2 --body-file f": "gh issue comment",
        }
        for command, want in cases.items():
            with self.subTest(command=command):
                self.assertEqual(external_target("Bash", {"command": command}, config), want)


if __name__ == "__main__":
    unittest.main()
