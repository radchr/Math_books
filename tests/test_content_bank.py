"""Tests for the git-backed scenario bank, rebuildable SQLite index, promote workflow, and CLI."""

from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from math_books.cli import main as cli_main
from math_books.content_bank import (
    index_path,
    load_bank_entry,
    promote_bank_entry,
    query_bank,
    sync_bank_index,
)
from math_books.lessons import load_lesson
from math_books.topics import project_root


class TestContentBank(unittest.TestCase):
    def test_repository_sample_bank_entries_validate_and_query(self):
        root = project_root()
        entries = query_bank(root)
        ids = {e["id"] for e in entries}
        self.assertTrue({"perelman_echo_distance", "basketball_three_vs_chain_draft"} <= ids)

        physics_entries = query_bank(root, domain="physics", tag="acoustics")
        self.assertEqual([e["id"] for e in physics_entries], ["perelman_echo_distance"])

        bar_drafts = query_bank(root, status="draft", template="compare_bars")
        self.assertEqual([e["id"] for e in bar_drafts], ["basketball_three_vs_chain_draft"])

    def test_promote_exports_lesson_and_keeps_reusable_bank_record(self):
        src_root = project_root()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(src_root / "content" / "bank", root / "content" / "bank")

            # Promoting an idea without lesson_draft fails clearly
            idea_only = json.loads((root / "content/bank/perelman_echo_distance.json").read_text(encoding="utf-8"))
            idea_only.update(id="synthetic_idea", status="idea", lesson_draft=None, promoted_lesson=None)
            (root / "content/bank/synthetic_idea.json").write_text(json.dumps(idea_only), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "has no lesson_draft"):
                promote_bank_entry(root, "synthetic_idea")

            # Colliding with legacy topic fails clearly
            with self.assertRaisesRegex(ValueError, "collides with a legacy topic"):
                promote_bank_entry(root, "basketball_three_vs_chain_draft", topic="buzzer")

            result = promote_bank_entry(root, "basketball_three_vs_chain_draft", topic="endgame_choice")
            self.assertEqual(result["topic"], "endgame_choice")
            self.assertEqual(result["status"], "promoted")

            # Exported lesson loads cleanly in all 3 languages
            for lang in ("uk", "ru", "en"):
                scenes = load_lesson(root, "endgame_choice", lang)
                self.assertEqual(len(scenes), 3)

            # Original bank record remains in content/bank/ with updated status + link
            bank_entry = load_bank_entry(root, "basketball_three_vs_chain_draft")
            self.assertEqual(bank_entry["status"], "promoted")
            self.assertEqual(bank_entry["promoted_lesson"]["topic"], "endgame_choice")
            self.assertTrue(index_path(root).is_file())

            # Re-promoting to the same topic refuses overwrite, while a remix topic succeeds
            with self.assertRaises(FileExistsError):
                promote_bank_entry(root, "basketball_three_vs_chain_draft", topic="endgame_choice")
            remix = promote_bank_entry(root, "basketball_three_vs_chain_draft", topic="endgame_choice_v2")
            self.assertEqual(remix["topic"], "endgame_choice_v2")

    def test_sqlite_index_rebuilds_when_bank_files_change(self):
        src_root = project_root()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shutil.copytree(src_root / "content" / "bank", root / "content" / "bank")
            sync_bank_index(root)
            self.assertEqual(len(query_bank(root, status="parked")), 0)

            entry_file = root / "content" / "bank" / "perelman_echo_distance.json"
            data = json.loads(entry_file.read_text(encoding="utf-8"))
            data["status"] = "parked"
            entry_file.write_text(json.dumps(data), encoding="utf-8")

            parked = query_bank(root, status="parked")
            self.assertEqual([e["id"] for e in parked], ["perelman_echo_distance"])

    def test_cli_bank_list_and_catalog(self):
        out = io.StringIO()
        with redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            cli_main(["bank", "catalog"])
        self.assertEqual(cm.exception.code, 0)
        catalog = json.loads(out.getvalue())
        self.assertIn("compare_bars", {item["name"] for item in catalog})

        out2 = io.StringIO()
        with (
            patch("math_books.cli.project_root", return_value=project_root()),
            redirect_stdout(out2),
            self.assertRaises(SystemExit) as cm2,
        ):
            cli_main(["bank", "list", "--json"])
        self.assertEqual(cm2.exception.code, 0)
        listed = json.loads(out2.getvalue())
        self.assertGreaterEqual(len(listed), 2)
