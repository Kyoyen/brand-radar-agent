"""A task is one editable document, saved locally after each meaningful change."""

from __future__ import annotations

import copy
import json
import math
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
KINDS = {"observation", "idea", "source", "question", "note", "calendar"}
COLORS = {"cream", "sage", "rose", "lavender", "sand"}
CARD_STATUSES = {"draft", "kept", "archived"}
COLUMN = {"observation": 0, "note": 0, "question": 0, "calendar": 0, "source": 1, "idea": 2}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def finite(value, default=0.0, minimum=-100000, maximum=100000):
    if isinstance(value, bool):
        return default
    try:
        parsed = float(value)
        return max(minimum, min(maximum, parsed)) if math.isfinite(parsed) else default
    except (ValueError, TypeError):
        return default


class TaskStore:
    def __init__(self, root: Path | None = None):
        self.root = root or ROOT / "outputs" / "studio"
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, task_id: str) -> Path:
        if not re.fullmatch(r"task_[a-f0-9]{12}", task_id):
            raise KeyError("找不到这次企划")
        return self.root / f"{task_id}.json"

    def get(self, task_id: str) -> dict:
        with self.lock:
            try:
                task = json.loads(self.path(task_id).read_text(encoding="utf-8"))
                task.setdefault("edges", [])
                return task
            except FileNotFoundError as exc:
                raise KeyError("找不到这次企划") from exc

    def list(self) -> list[dict]:
        with self.lock:
            result = []
            for path in self.root.glob("task_*.json"):
                try:
                    task = json.loads(path.read_text(encoding="utf-8"))
                    result.append({key: task.get(key) for key in (
                        "id", "title", "question", "brand", "status", "created_at", "updated_at"
                    )} | {"card_count": len(task.get("cards", []))})
                except (ValueError, OSError):
                    continue
            return sorted(result, key=lambda item: item.get("updated_at") or "", reverse=True)

    def create(self, *, title: str, question: str, brand: str = "瑞幸咖啡",
               brand_context: str = "", sources: list[dict] | None = None,
               case_id: str | None = None) -> dict:
        timestamp = now()
        task = {
            "id": uid("task"), "title": title[:160] or "一件值得继续想的事",
            "question": question[:16000], "brand": brand[:100],
            "brand_context": brand_context[:24000], "case_id": case_id,
            "created_at": timestamp, "updated_at": timestamp,
            "status": "idle", "sources": [], "cards": [], "edges": [], "messages": [],
            "activity": [], "viewport": {"x": 0, "y": 0, "zoom": 1},
            "error": None, "model": None, "run_id": None,
        }
        with self.lock:
            save_json(self.path(task["id"]), task)
            for source in sorted(sources or [], key=lambda item: not bool(item.get("image_url"))):
                saved = self.add_source(task["id"], source)
                self.upsert_cards(task["id"], [{
                    "id": f"card_{saved['id']}", "kind": "source",
                    "title": saved["title"], "body": saved["excerpt"],
                    "source_ids": [saved["id"]], "color": "cream",
                }])
            return self.get(task["id"])

    def mutate(self, task_id: str, callback: Callable[[dict], None]) -> dict:
        with self.lock:
            task = self.get(task_id)
            callback(task)
            task["updated_at"] = now()
            save_json(self.path(task_id), task)
            return copy.deepcopy(task)

    def emit(self, task_id: str, label: str, detail: str = "") -> dict:
        activity = {"id": uid("activity"), "label": str(label)[:200],
                    "detail": str(detail)[:1500], "created_at": now(), "state": "done"}
        self.mutate(task_id, lambda task: task["activity"].append(activity))
        return activity

    def add_message(self, task_id: str, role: str, content: str,
                    selected_card_ids: list[str] | None = None) -> dict:
        message = {"id": uid("message"), "role": role, "content": str(content)[:20000],
                   "created_at": now(), "selected_card_ids": selected_card_ids or []}
        self.mutate(task_id, lambda task: task["messages"].append(message))
        return message

    def add_source(self, task_id: str, source: dict) -> dict:
        with self.lock:
            task = self.get(task_id)
            url = str(source.get("url") or "").strip() or None
            existing = next((item for item in task["sources"] if url and item.get("url") == url), None)
            text = str(source.get("text") or source.get("excerpt") or "")[:60000]
            record = {
                "id": existing["id"] if existing else str(source.get("id") or uid("src")),
                "title": str(source.get("title") or "补充材料")[:240], "url": url,
                "excerpt": str(source.get("excerpt") or text[:450])[:2000], "text": text,
                "published_at": source.get("published_at"),
                "accessed_at": source.get("accessed_at") or now(),
                "image_url": source.get("image_url") or None,
                "origin": source.get("origin", "manual"),
                "truncated": bool(source.get("truncated", False)),
            }
            if record["origin"] not in {"public", "manual", "replay"}:
                record["origin"] = "manual"
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", record["id"]):
                record["id"] = uid("src")
            if not existing and any(item["id"] == record["id"] for item in task["sources"]):
                record["id"] = uid("src")
            def update(document):
                if existing:
                    document["sources"] = [record if item["id"] == record["id"] else item
                                           for item in document["sources"]]
                else:
                    document["sources"].append(record)
            self.mutate(task_id, update)
            return copy.deepcopy(record)

    def upsert_cards(self, task_id: str, cards: list[dict], remove_ids: list[str] | None = None,
                     *, edges: list[dict] | None = None, remove_edge_ids: list[str] | None = None) -> dict:
        def update(task):
            self._upsert_cards(task, cards, remove_ids)
            self._upsert_edges(task, edges if edges is not None else [],
                               remove_edge_ids if remove_edge_ids is not None else [])
        return self.mutate(task_id, update)

    @staticmethod
    def _upsert_cards(task: dict, cards: list[dict], remove_ids: list[str] | None = None):
        if not isinstance(cards, list) or len(cards) > 40:
            raise ValueError("一次请更新不超过 40 张卡片")
        remove_ids = remove_ids if remove_ids is not None else []
        if not isinstance(remove_ids, list) or any(not isinstance(item, str) for item in remove_ids):
            raise ValueError("移除卡片需要 ID 数组")
        # The caller saves the whole document only after cards and edges validate.
        known_sources = {source["id"] for source in task["sources"]}
        for incoming in cards:
            if not isinstance(incoming, dict):
                raise ValueError("卡片内容应是一个对象")
            card_id = incoming.get("id") or uid("card")
            if not isinstance(card_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", card_id):
                raise ValueError("卡片 ID 只能包含字母、数字、下划线和短横线，最长 100 字符")
            existing = next((item for item in task["cards"] if item["id"] == card_id), None)
            kind = incoming.get("kind", existing["kind"] if existing else "note")
            if kind not in KINDS:
                raise ValueError("不支持的卡片类型")
            refs = incoming.get("source_ids", existing.get("source_ids", []) if existing else [])
            if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in known_sources for ref in refs):
                raise ValueError("卡片引用了尚未加入桌面的来源，请先读取该来源")
            if kind == "source" and not refs:
                raise ValueError("来源卡需要实际材料")
            if existing:
                record = dict(existing)
                content_changed = any(key in incoming and incoming[key] != existing.get(key)
                                      for key in ("title", "body", "source_ids"))
                if content_changed:
                    record["revisions"] = list(existing.get("revisions", [])) + [
                        {key: existing.get(key) for key in ("title", "body", "source_ids", "updated_at")}
                    ]
            else:
                column = COLUMN[kind]
                same_column = [item for item in task["cards"] if
                               COLUMN.get(item["kind"]) == column]
                record = {"id": card_id, "x": 32 + column * 360, "y": 64 + len(same_column) * 420,
                          "width": 320, "status": "draft"}
                for key in ("x", "y"):
                    if key in incoming:
                        record[key] = finite(incoming[key], record[key])
            record.update({
                "kind": kind, "title": str(incoming.get("title", record.get("title", "")))[:240],
                "body": str(incoming.get("body", record.get("body", "")))[:16000],
                "source_ids": list(dict.fromkeys(refs)), "updated_at": now(),
                "color": incoming.get("color", record.get("color", "cream")),
            })
            if record["color"] not in COLORS:
                record["color"] = "cream"
            if existing:
                # Model edits preserve user placement and adoption decisions.
                index = task["cards"].index(existing)
                task["cards"][index] = record
            else:
                task["cards"].append(record)
        # Archive rather than destroy a direction, keeping its history readable.
        for card in task["cards"]:
            if card["id"] in (remove_ids or []):
                card["status"] = "archived"
                card["updated_at"] = now()

    @staticmethod
    def _upsert_edges(task: dict, edges: list[dict], remove_ids: list[str]):
        if not isinstance(edges, list) or len(edges) > 100:
            raise ValueError("一次请更新不超过 100 条连线")
        if not isinstance(remove_ids, list) or any(not isinstance(item, str) for item in remove_ids):
            raise ValueError("移除连线需要 ID 数组")
        known_cards = {card["id"] for card in task["cards"]}
        task.setdefault("edges", [])
        for incoming in edges:
            if not isinstance(incoming, dict):
                raise ValueError("连线需要对象")
            edge_id = incoming.get("id") or uid("edge")
            if not isinstance(edge_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,100}", edge_id):
                raise ValueError("连线 ID 格式不正确")
            previous = next((edge for edge in task["edges"] if edge["id"] == edge_id), {})
            record = {key: incoming.get(key, previous.get(key, "")) for key in ("from_id", "to_id", "label")}
            if any(not isinstance(record[key], str) or record[key] not in known_cards for key in ("from_id", "to_id")):
                raise ValueError("连线两端必须是画布已有或本次新增的卡片 ID")
            if record["from_id"] == record["to_id"]:
                raise ValueError("请连接两张不同的卡片")
            record.update(id=edge_id, label=str(record["label"])[:160])
            if previous:
                task["edges"][task["edges"].index(previous)] = record
            else:
                task["edges"].append(record)
        task["edges"] = [edge for edge in task["edges"] if edge["id"] not in remove_ids]

    def patch(self, task_id: str, patch: dict) -> dict:
        def update(task):
            if "title" in patch:
                title = str(patch["title"]).strip()
                if not title:
                    raise ValueError("企划标题不能为空")
                task["title"] = title[:160]
            if "viewport" in patch:
                viewport = patch["viewport"]
                if not isinstance(viewport, dict):
                    raise ValueError("画布位置格式不正确")
                task["viewport"] = {
                    "x": finite(viewport.get("x")), "y": finite(viewport.get("y")),
                    "zoom": finite(viewport.get("zoom"), 1, .2, 2),
                }
            if "cards" in patch:
                incoming_cards = patch["cards"]
                if not isinstance(incoming_cards, list) or any(not isinstance(card, dict) for card in incoming_cards):
                    raise ValueError("卡片更新格式不正确")
                incoming_cards = [{**card, "id": card.get("id") or uid("card")} for card in incoming_cards]
                self._upsert_cards(task, incoming_cards)
                for incoming in incoming_cards:
                    # IDs are assigned before applying human position/status edits.
                    card = next((item for item in task["cards"] if item["id"] == incoming.get("id")), None)
                    if "status" in incoming:
                        if incoming["status"] not in CARD_STATUSES:
                            raise ValueError("卡片状态不正确")
                        card["status"] = incoming["status"]
                    for key in ("x", "y"):
                        if key in incoming:
                            card[key] = finite(incoming[key], card[key])
                    if "width" in incoming:
                        card["width"] = finite(incoming["width"], 320, 240, 700)
                    card["updated_at"] = now()
            self._upsert_edges(task, patch.get("edges", []), patch.get("remove_edge_ids", []))
        return self.mutate(task_id, update)

    def recover_interrupted(self):
        for task in self.list():
            if task["status"] == "running":
                self.mutate(task["id"], lambda item: item.update(
                    status="stopped", error="上次工作因服务关闭而中断，已有材料与草稿已保留。可以继续。"))
