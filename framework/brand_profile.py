"""Brand profile loading and the reusable six-question interview state machine."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BRAND_PATH = ROOT / "BRAND.md"
LOCAL_BRAND_PATH = ROOT / "memory/brand/BRAND.md"

SECTION_TITLES = (
    "1. 希望被怎样记住",
    "2. 最重要的人与场景",
    "3. 承诺与可信依据",
    "4. 声音与反例",
    "5. 热点与竞品判断",
    "6. 红线与人工确认",
)

@dataclass(frozen=True)
class BrandProfile:
    path: Path
    content: str
    mode: Literal["default", "custom"]
    answered_questions: int
    fingerprint: str


@dataclass(frozen=True)
class BrandQuestion:
    index: int
    title: str
    prompt: str


def _parse_answers(content: str) -> list[str | None]:
    sections = {
        title: body.strip()
        for title, body in re.findall(
            r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", content, flags=re.MULTILINE | re.DOTALL
        )
    }
    return [sections.get(title) or None for title in SECTION_TITLES]


def _load_default_answers(default_path: Path) -> tuple[str, ...]:
    answers = _parse_answers(default_path.read_text(encoding="utf-8"))
    if any(answer is None for answer in answers):
        raise ValueError(f"通用品牌档案缺少六个完整章节：{default_path}")
    return tuple(answer for answer in answers if answer is not None)


def _answered_questions(content: str, default_answers: tuple[str, ...]) -> int:
    return sum(
        answer is not None and answer != default
        for answer, default in zip(_parse_answers(content), default_answers, strict=True)
    )


def load_brand_profile(
    explicit_path: str | Path | None = None,
    *,
    default_path: Path = DEFAULT_BRAND_PATH,
    local_path: Path = LOCAL_BRAND_PATH,
) -> BrandProfile:
    """Load an explicit, local, or repository-default profile in that order."""
    default_answers = _load_default_answers(default_path)
    if explicit_path is not None:
        path = Path(explicit_path).expanduser()
        mode: Literal["default", "custom"] = "custom"
    elif local_path.exists():
        path = local_path
        mode = "custom"
    else:
        path = default_path
        mode = "default"

    content = path.read_text(encoding="utf-8")
    return BrandProfile(
        path=path,
        content=content,
        mode=mode,
        answered_questions=_answered_questions(content, default_answers),
        fingerprint=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


class BrandInterview:
    """State-only six-question brand interview; callers supply all terminal or GUI I/O."""

    def __init__(
        self,
        existing_content: str | None = None,
        *,
        default_path: Path = DEFAULT_BRAND_PATH,
    ) -> None:
        existing_answers = _parse_answers(existing_content or "")
        self._default_answers = _load_default_answers(default_path)
        self.questions = tuple(
            BrandQuestion(index=index, title=title, prompt="")
            for index, title in enumerate(SECTION_TITLES)
        )
        self._answers = [
            answer or default
            for answer, default in zip(existing_answers, self._default_answers, strict=True)
        ]
        self._position = 0
        self._user_answered = [False] * len(self.questions)

    @property
    def is_complete(self) -> bool:
        return self._position == len(self.questions)

    @property
    def has_user_answers(self) -> bool:
        return any(self._user_answered)

    def next_question(self) -> BrandQuestion:
        if self.is_complete:
            raise RuntimeError("六个品牌问题已经回答完成")
        question = self.questions[self._position]
        return BrandQuestion(
            index=question.index,
            title=question.title,
            prompt=self._prompt_for(question.index),
        )

    def answer(self, value: str) -> None:
        if self.is_complete:
            raise RuntimeError("六个品牌问题已经回答完成")
        normalized = value.strip()
        if normalized and normalized.lower() != "skip" and normalized != "跳过":
            self._answers[self._position] = normalized
            self._user_answered[self._position] = True
        self._position += 1

    def render_brand_markdown(self) -> str:
        sections = "\n\n".join(
            f"## {title}\n{answer}"
            for title, answer in zip(SECTION_TITLES, self._answers, strict=True)
        )
        return f"# Brand Radar 品牌档案\n\n{sections}\n"

    def _prompt_for(self, index: int) -> str:
        prompts = (
            "品牌希望被怎样记住？",
            f"你希望“{self._answers[0]}”服务谁？他们在什么场景下需要品牌？",
            f"要让“{self._answers[0]}”可信，品牌承诺是什么，哪些事实能让人相信？",
            f"围绕“{self._answers[1]}”，品牌应该像怎样的人说话，绝不能像谁？",
            f"在“{self._answers[2]}”和“{self._answers[3]}”的前提下，什么热点或竞品机会值得跟，什么宁可错过？",
            f"为了守住“{self._answers[0]}”，哪些表达或动作绝不能做，什么情况必须交给人确认？",
        )
        return prompts[index]


def save_brand_profile(interview: BrandInterview, destination: Path = LOCAL_BRAND_PATH) -> bool:
    """Atomically save completed, non-empty interview work; skip-only sessions stay local-free."""
    if not interview.is_complete:
        raise ValueError("完成六个品牌问题后才能保存")
    if not interview.has_user_answers:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    try:
        temporary.write_text(interview.render_brand_markdown(), encoding="utf-8")
        temporary.replace(destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return True


__all__ = [
    "BrandInterview",
    "BrandProfile",
    "BrandQuestion",
    "DEFAULT_BRAND_PATH",
    "LOCAL_BRAND_PATH",
    "load_brand_profile",
    "save_brand_profile",
]
