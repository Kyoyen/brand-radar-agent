from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from framework.brand_profile import (
    BrandInterview,
    DEFAULT_ANSWERS,
    load_brand_profile,
    save_brand_profile,
)


class BrandInterviewTests(unittest.TestCase):
    def test_answer_advances_to_a_follow_up_that_uses_the_previous_answer(self) -> None:
        interview = BrandInterview()

        self.assertEqual(6, len(interview.questions))
        interview.answer("让日常咖啡更轻松")

        self.assertIn("让日常咖啡更轻松", interview.next_question().prompt)

    def test_skipping_every_question_does_not_create_a_local_profile(self) -> None:
        interview = BrandInterview()
        for _ in interview.questions:
            interview.answer("skip")

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "memory/brand/BRAND.md"
            written = save_brand_profile(interview, destination)

            self.assertFalse(written)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix(".md.tmp").exists())

    def test_partial_answers_render_all_six_sections_with_defaults(self) -> None:
        interview = BrandInterview()
        interview.answer("让日常咖啡更轻松")
        for _ in range(5):
            interview.answer("跳过")

        rendered = interview.render_brand_markdown()

        self.assertEqual(6, rendered.count("## "))
        self.assertIn("让日常咖啡更轻松", rendered)
        self.assertIn(DEFAULT_ANSWERS[1], rendered)

    def test_blank_update_keeps_the_existing_answer(self) -> None:
        first = BrandInterview()
        first.answer("成为上班路上的轻松一杯")
        for _ in range(5):
            first.answer("skip")

        updated = BrandInterview(existing_content=first.render_brand_markdown())
        updated.answer("")
        for _ in range(5):
            updated.answer("")

        self.assertIn("成为上班路上的轻松一杯", updated.render_brand_markdown())

    def test_completed_profile_is_written_atomically_without_a_tmp_file(self) -> None:
        interview = BrandInterview()
        interview.answer("让日常咖啡更轻松")
        for _ in range(5):
            interview.answer("skip")

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "memory/brand/BRAND.md"
            written = save_brand_profile(interview, destination)

            self.assertTrue(written)
            self.assertIn("让日常咖啡更轻松", destination.read_text(encoding="utf-8"))
            self.assertFalse(destination.with_suffix(".md.tmp").exists())


class BrandProfileLoadingTests(unittest.TestCase):
    def test_loads_explicit_then_local_then_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            default = root / "BRAND.md"
            local = root / "memory/brand/BRAND.md"
            explicit = root / "other-brand.md"
            default.write_text("default", encoding="utf-8")
            local.parent.mkdir(parents=True)
            local.write_text("local", encoding="utf-8")
            explicit.write_text("explicit", encoding="utf-8")

            self.assertEqual(
                "explicit",
                load_brand_profile(explicit, default_path=default, local_path=local).content,
            )
            self.assertEqual(
                "local", load_brand_profile(default_path=default, local_path=local).content
            )
            local.unlink()
            profile = load_brand_profile(default_path=default, local_path=local)

            self.assertEqual("default", profile.content)
            self.assertEqual("default", profile.mode)
            self.assertEqual(64, len(profile.fingerprint))


if __name__ == "__main__":
    unittest.main()
