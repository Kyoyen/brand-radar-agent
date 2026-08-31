from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN_PY = ROOT / "run.py"
REPLAY_MANIFEST = ROOT / "data/replay/coffee-week-2026-09-07/manifest.json"
OUTPUTS_DIR = ROOT / "outputs"
API_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "MOONSHOT_API_KEY",
    "ZHIPU_API_KEY",
    "ZHIPUAI_API_KEY",
)


def _environment_without_api_keys() -> dict[str, str]:
    environment = os.environ.copy()
    for variable in API_KEY_ENV_VARS:
        environment.pop(variable, None)
    environment["LLM_PROVIDER"] = "deepseek"
    environment["PYTHON_DOTENV_DISABLED"] = "1"
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUN_PY), *arguments],
        cwd=ROOT,
        env=_environment_without_api_keys(),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def _output_file_set() -> set[str]:
    if not OUTPUTS_DIR.exists():
        return set()
    return {
        path.relative_to(OUTPUTS_DIR).as_posix()
        for path in OUTPUTS_DIR.rglob("*")
        if path.is_file()
    }


class WeeklyCliTests(unittest.TestCase):
    def test_require_api_without_key_fails_before_reading_or_writing(self) -> None:
        before = _output_file_set()
        result = _run_cli(
            "--weekly",
            "--source-pack",
            str(REPLAY_MANIFEST),
            "--require-api",
        )
        after = _output_file_set()

        self.assertNotEqual(0, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("DEEPSEEK_API_KEY", result.stdout)
        self.assertIn("未读取材料", result.stdout)
        self.assertNotIn("已启用 MockProvider", result.stdout + result.stderr)
        self.assertEqual(before, after)

    def test_help_lists_weekly_flags(self) -> None:
        result = _run_cli("--help")

        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
        for flag in ("--weekly", "--source-pack", "--require-api"):
            with self.subTest(flag=flag):
                self.assertIn(flag, result.stdout)

    def test_list_remains_compatible(self) -> None:
        result = _run_cli("--list")

        self.assertEqual(0, result.returncode, msg=result.stdout + result.stderr)
        self.assertIn("可用场景", result.stdout)


if __name__ == "__main__":
    unittest.main()
