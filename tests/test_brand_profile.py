from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from framework.brand_profile import (
    BrandInterview,
    load_brand_profile,
    save_brand_profile,
)


def _brand_markdown(answers: list[str]) -> str:
    titles = (
        "1. 希望被怎样记住",
        "2. 最重要的人与场景",
        "3. 承诺与可信依据",
        "4. 声音与反例",
        "5. 热点与竞品判断",
        "6. 红线与人工确认",
    )
    return "# 测试品牌档案\n\n" + "\n\n".join(
        f"## {title}\n{answer}" for title, answer in zip(titles, answers, strict=True)
    ) + "\n"


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

    def test_partial_answers_render_all_six_sections_with_default_profile_values(self) -> None:
        default_answers = [f"默认回答 {index}" for index in range(1, 7)]
        with tempfile.TemporaryDirectory() as directory:
            default = Path(directory) / "BRAND.md"
            default.write_text(_brand_markdown(default_answers), encoding="utf-8")
            interview = BrandInterview(default_path=default)
            interview.answer("定制回答 1")
            for _ in range(5):
                interview.answer("跳过")

            rendered = interview.render_brand_markdown()

        self.assertEqual(6, rendered.count("## "))
        self.assertIn("定制回答 1", rendered)
        self.assertIn("默认回答 2", rendered)

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

    def test_replace_failure_removes_the_temporary_profile_file(self) -> None:
        interview = BrandInterview()
        interview.answer("定制定位")
        for _ in range(5):
            interview.answer("skip")

        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "memory/brand/BRAND.md"
            with patch.object(Path, "replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    save_brand_profile(interview, destination)

            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix(".md.tmp").exists())


class BrandProfileLoadingTests(unittest.TestCase):
    def test_temporary_default_profile_controls_skips_and_answered_count(self) -> None:
        default_answers = [f"默认回答 {index}" for index in range(1, 7)]
        custom_first_answer = "定制回答 1"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            default = root / "BRAND.md"
            local = root / "memory/brand/BRAND.md"
            default.write_text(_brand_markdown(default_answers), encoding="utf-8")
            local.parent.mkdir(parents=True)
            local.write_text(
                _brand_markdown([custom_first_answer, *default_answers[1:]]),
                encoding="utf-8",
            )

            profile_before_default_change = load_brand_profile(
                default_path=default, local_path=local
            )
            self.assertEqual(1, profile_before_default_change.answered_questions)

            default_answers[0] = custom_first_answer
            default.write_text(_brand_markdown(default_answers), encoding="utf-8")
            interview = BrandInterview(default_path=default)
            for _ in interview.questions:
                interview.answer("skip")
            profile_after_default_change = load_brand_profile(
                default_path=default, local_path=local
            )

            self.assertIn(custom_first_answer, interview.render_brand_markdown())
            self.assertEqual(0, profile_after_default_change.answered_questions)

    def test_loads_explicit_then_local_then_default_profile(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            default = root / "BRAND.md"
            local = root / "memory/brand/BRAND.md"
            explicit = root / "other-brand.md"
            default_answers = [f"默认回答 {index}" for index in range(1, 7)]
            default.write_text(_brand_markdown(default_answers), encoding="utf-8")
            local.parent.mkdir(parents=True)
            local.write_text(
                _brand_markdown(["本机定制回答", *default_answers[1:]]), encoding="utf-8"
            )
            explicit.write_text(
                _brand_markdown(["显式定制回答", *default_answers[1:]]), encoding="utf-8"
            )

            self.assertEqual(
                explicit,
                load_brand_profile(explicit, default_path=default, local_path=local).path,
            )
            self.assertEqual(
                local, load_brand_profile(default_path=default, local_path=local).path
            )
            local.unlink()
            profile = load_brand_profile(default_path=default, local_path=local)

            self.assertEqual(default, profile.path)
            self.assertEqual("default", profile.mode)
            self.assertEqual(64, len(profile.fingerprint))


if __name__ == "__main__":
    unittest.main()
