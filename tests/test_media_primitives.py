"""Low-level media I/O must not depend on synthesis or video orchestration."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from math_books import media_io


class TestMediaPrimitives(unittest.TestCase):
    def test_topic_and_qa_imports_do_not_load_the_synthesis_or_builder_layers(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import math_books.topics; import math_books.voiceover_qa; "
                'assert "math_books.video_builder" not in sys.modules; '
                'assert "math_books.tts_engine" not in sys.modules',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_failed_sidecar_publication_preserves_previous_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "render.json"
            path.write_text('{"previous": true}')
            with patch.object(Path, "replace", side_effect=OSError("interrupted publication")):
                with self.assertRaises(OSError):
                    media_io.atomic_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text()), {"previous": True})
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_invalid_json_does_not_damage_old_sidecar(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.json"
            media_io.atomic_json(path, {"events": []})
            with self.assertRaises(ValueError):
                media_io.atomic_json(path, {"time": float("nan")})
            self.assertEqual(json.loads(path.read_text()), {"events": []})
            self.assertEqual(list(Path(directory).iterdir()), [path])
