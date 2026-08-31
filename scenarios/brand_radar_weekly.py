"""Brand Radar weekly Replay scenario.

The scenario is deliberately local and read-only: it reads one manifest and
the files explicitly listed by that manifest, performs stable version and
merge bookkeeping, and exposes the resulting evidence to one model call.
It has no network, publishing, messaging, advertising, or budget tools.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any


ALLOWED_SOURCE_TYPES = {"REPLAY", "PUBLIC", "MANUAL"}
ALLOWED_VERIFICATION_STATUSES = {"verified", "unverified"}

WEEKLY_TOOL_ORDER = (
    "read_weekly_settings",
    "read_weekly_source_pack",
    "resolve_weekly_versions",
    "merge_weekly_events",
)


def _tool(name: str, description: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    }


WEEKLY_TOOLS = [
    _tool("read_weekly_settings", "读取本次周企划的品牌、品类、地区、竞品、关键词、时间窗和业务问题。"),
    _tool("read_weekly_source_pack", "只读取 manifest 明确列出的本地 Replay / PUBLIC / MANUAL 材料并保留来源。"),
    _tool("resolve_weekly_versions", "按日期、有效期、版本组和核验状态标记当前、重复、过期、被覆盖与待核材料。"),
    _tool("merge_weekly_events", "按 event_key 合并同一营销事件的多份材料，保留每个来源 ID。"),
]


class WeeklySourcePackError(ValueError):
    """The Replay pack is missing, unsafe, or structurally invalid."""


class WeeklyPipelineError(RuntimeError):
    """The fixed weekly pipeline was called out of order or could not finish."""


def _parse_iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise WeeklySourcePackError(f"{field} 必须是 YYYY-MM-DD 字符串")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise WeeklySourcePackError(f"{field} 不是有效的 ISO 日期：{value}") from exc


def _require_string(data: dict[str, Any], field: str, where: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise WeeklySourcePackError(f"{where}.{field} 必须是非空字符串")
    return value.strip()


def _require_string_list(data: dict[str, Any], field: str, where: str) -> list[str]:
    value = data.get(field)
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise WeeklySourcePackError(f"{where}.{field} 必须是非空字符串数组")
    return [item.strip() for item in value]


class WeeklyScenarioRuntime:
    """Validated, in-memory runtime for one source pack."""

    def __init__(self, source_pack: str | Path):
        supplied = Path(source_pack).expanduser()
        if not supplied.is_absolute():
            supplied = Path.cwd() / supplied
        self.manifest_path = supplied.resolve()
        if not self.manifest_path.is_file():
            raise WeeklySourcePackError(f"观察包 manifest 不存在：{source_pack}")

        self.pack_root = self.manifest_path.parent.resolve()
        self.manifest = self._load_manifest()
        self.settings = self._validate_settings(self.manifest.get("settings"))
        self.materials = self._validate_materials(self.manifest.get("materials"))
        self._results: dict[str, dict[str, Any]] = {}
        self._next_tool_index = 0

    @property
    def display_path(self) -> str:
        repo_root = Path(__file__).resolve().parents[1]
        try:
            return self.manifest_path.relative_to(repo_root).as_posix()
        except ValueError:
            return str(self.manifest_path)

    def _load_manifest(self) -> dict[str, Any]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise WeeklySourcePackError(f"观察包 manifest 无法读取或不是有效 JSON：{self.manifest_path}") from exc
        if not isinstance(data, dict):
            raise WeeklySourcePackError("观察包 manifest 顶层必须是对象")
        if data.get("schema_version") != "1.0":
            raise WeeklySourcePackError("观察包 schema_version 必须是 1.0")
        if data.get("pack_mode") != "REPLAY":
            raise WeeklySourcePackError("本场景只接受 pack_mode=REPLAY")
        _require_string(data, "pack_id", "manifest")
        return data

    def _validate_settings(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise WeeklySourcePackError("manifest.settings 必须是对象")

        settings = {
            "brand": _require_string(value, "brand", "settings"),
            "category": _require_string(value, "category", "settings"),
            "regions": _require_string_list(value, "regions", "settings"),
            "competitors": _require_string_list(value, "competitors", "settings"),
            "keywords": _require_string_list(value, "keywords", "settings"),
            "business_question": _require_string(value, "business_question", "settings"),
        }

        for window_name in ("observation_window", "calendar_window"):
            window = value.get(window_name)
            if not isinstance(window, dict):
                raise WeeklySourcePackError(f"settings.{window_name} 必须是对象")
            start = _parse_iso_date(window.get("start"), f"settings.{window_name}.start")
            end = _parse_iso_date(window.get("end"), f"settings.{window_name}.end")
            if start > end:
                raise WeeklySourcePackError(f"settings.{window_name} 的 start 不能晚于 end")
            settings[window_name] = {"start": start.isoformat(), "end": end.isoformat()}

        observation = settings["observation_window"]
        calendar = settings["calendar_window"]
        if calendar["start"] > observation["start"] or calendar["end"] < observation["end"]:
            raise WeeklySourcePackError("calendar_window 必须覆盖 observation_window")

        safety = value.get("safety_boundaries", [])
        if not isinstance(safety, list) or not all(isinstance(item, str) and item.strip() for item in safety):
            raise WeeklySourcePackError("settings.safety_boundaries 必须是字符串数组")
        settings["safety_boundaries"] = [item.strip() for item in safety]

        review_deadline = value.get("review_deadline")
        if review_deadline is not None:
            settings["review_deadline"] = _parse_iso_date(review_deadline, "settings.review_deadline").isoformat()
        return settings

    def _safe_pack_file(self, relative_path: str, field: str) -> Path:
        candidate = (self.pack_root / relative_path).resolve()
        try:
            candidate.relative_to(self.pack_root)
        except ValueError as exc:
            raise WeeklySourcePackError(f"{field} 不能指向观察包目录之外：{relative_path}") from exc
        return candidate

    def _validate_materials(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or not value:
            raise WeeklySourcePackError("manifest.materials 必须是非空数组")

        seen: set[str] = set()
        materials: list[dict[str, Any]] = []
        for index, raw in enumerate(value):
            where = f"materials[{index}]"
            if not isinstance(raw, dict):
                raise WeeklySourcePackError(f"{where} 必须是对象")

            source_id = _require_string(raw, "source_id", where)
            if source_id in seen:
                raise WeeklySourcePackError(f"source_id 重复：{source_id}")
            seen.add(source_id)

            source_type = _require_string(raw, "source_type", where).upper()
            if source_type not in ALLOWED_SOURCE_TYPES:
                raise WeeklySourcePackError(f"{where}.source_type 非法：{source_type}")
            verification = _require_string(raw, "verification_status", where).lower()
            if verification not in ALLOWED_VERIFICATION_STATUSES:
                raise WeeklySourcePackError(f"{where}.verification_status 非法：{verification}")

            relative_file = _require_string(raw, "file", where)
            material = dict(raw)
            material.update(
                source_id=source_id,
                title=_require_string(raw, "title", where),
                source_type=source_type,
                source_date=_parse_iso_date(raw.get("source_date"), f"{where}.source_date").isoformat(),
                file=relative_file,
                resolved_file=self._safe_pack_file(relative_file, f"{where}.file"),
                event_key=_require_string(raw, "event_key", where),
                verification_status=verification,
                brands=_require_string_list(raw, "brands", where),
                regions=_require_string_list(raw, "regions", where),
            )

            url = material.get("url")
            if url is not None and (not isinstance(url, str) or not url.strip()):
                raise WeeklySourcePackError(f"{where}.url 必须是非空字符串或 null")
            material["url"] = url.strip() if isinstance(url, str) else None

            for field in ("valid_from", "valid_to"):
                if material.get(field) is not None:
                    material[field] = _parse_iso_date(material[field], f"{where}.{field}").isoformat()
            if material.get("version_rank") is not None and not isinstance(material["version_rank"], int):
                raise WeeklySourcePackError(f"{where}.version_rank 必须是整数")
            if material.get("duplicate_of") is not None and not isinstance(material["duplicate_of"], str):
                raise WeeklySourcePackError(f"{where}.duplicate_of 必须是 source_id 字符串")

            supersedes = material.get("supersedes", [])
            if not isinstance(supersedes, list) or not all(isinstance(item, str) for item in supersedes):
                raise WeeklySourcePackError(f"{where}.supersedes 必须是 source_id 数组")
            material["supersedes"] = supersedes
            materials.append(material)

        known_ids = {item["source_id"] for item in materials}
        for material in materials:
            refs = list(material.get("supersedes", []))
            if material.get("duplicate_of"):
                refs.append(material["duplicate_of"])
            unknown = sorted(set(refs) - known_ids)
            if unknown:
                raise WeeklySourcePackError(
                    f"{material['source_id']} 引用了不存在的 source_id：{', '.join(unknown)}"
                )
        return materials

    def execute(self, tool_name: str, arguments: dict[str, Any] | None = None) -> str:
        arguments = arguments or {}
        if arguments:
            return json.dumps({"error": f"工具 {tool_name} 不接受参数"}, ensure_ascii=False)
        if tool_name not in WEEKLY_TOOL_ORDER:
            return json.dumps({"error": f"未知 weekly 工具：{tool_name}"}, ensure_ascii=False)

        expected = WEEKLY_TOOL_ORDER[self._next_tool_index] if self._next_tool_index < len(WEEKLY_TOOL_ORDER) else None
        if tool_name != expected:
            return json.dumps(
                {"error": f"阶段顺序错误：当前必须执行 {expected or '无'}，不能执行 {tool_name}"},
                ensure_ascii=False,
            )

        result = {
            "read_weekly_settings": self._read_settings,
            "read_weekly_source_pack": self._read_materials,
            "resolve_weekly_versions": self._resolve_versions,
            "merge_weekly_events": self._merge_events,
        }[tool_name]()
        self._results[tool_name] = result
        self._next_tool_index += 1
        return json.dumps(result, ensure_ascii=False)

    def _read_settings(self) -> dict[str, Any]:
        return {"pack_id": self.manifest["pack_id"], "pack_mode": "REPLAY", "settings": self.settings}

    def _read_materials(self) -> dict[str, Any]:
        read_success: list[str] = []
        read_failed: list[dict[str, str]] = []
        loaded: list[dict[str, Any]] = []
        for material in self.materials:
            try:
                content = material["resolved_file"].read_text(encoding="utf-8")
                if not content.strip():
                    raise ValueError("文件为空")
            except (OSError, UnicodeError, ValueError) as exc:
                read_failed.append({"source_id": material["source_id"], "reason": f"材料读取失败：{type(exc).__name__}"})
                continue
            read_success.append(material["source_id"])
            loaded.append({"source": self._public_source_record(material), "content": content.strip()})
        return {
            "pack_id": self.manifest["pack_id"],
            "read_success": read_success,
            "read_failed": read_failed,
            "materials": loaded,
        }

    def _resolve_versions(self) -> dict[str, Any]:
        read_result = self._results["read_weekly_source_pack"]
        available = set(read_result["read_success"])
        failed = {item["source_id"] for item in read_result["read_failed"]}
        observation_start = date.fromisoformat(self.settings["observation_window"]["start"])

        newest_by_group: dict[str, dict[str, Any]] = {}
        for material in self.materials:
            group = material.get("version_group")
            if not group or material["source_id"] not in available:
                continue
            rank = material.get("version_rank", 0)
            current = newest_by_group.get(group)
            if current is None or rank > current.get("version_rank", 0):
                newest_by_group[group] = material

        decisions: list[dict[str, Any]] = []
        for material in self.materials:
            source_id = material["source_id"]
            status = "current"
            effective_source_id = source_id
            reason = "材料可用于本次判断"

            if source_id in failed:
                status, reason = "failed", "本地材料读取失败"
            elif material.get("duplicate_of"):
                status = "duplicate"
                effective_source_id = material["duplicate_of"]
                reason = f"与 {effective_source_id} 描述同一事件，合并来源而不重复计数"
            elif material.get("version_group"):
                newest = newest_by_group[material["version_group"]]
                if newest["source_id"] != source_id:
                    status = "superseded"
                    effective_source_id = newest["source_id"]
                    expiry = (
                        f"，且有效期已于 {material['valid_to']} 结束"
                        if material.get("valid_to")
                        and date.fromisoformat(material["valid_to"]) < observation_start
                        else ""
                    )
                    reason = f"同组已有更高版本 {effective_source_id}{expiry}"
            if (
                status == "current"
                and material.get("valid_to")
                and date.fromisoformat(material["valid_to"]) < observation_start
            ):
                status, reason = "expired", f"有效期已在观察窗前结束（{material['valid_to']}）"
            if status == "current" and material["verification_status"] == "unverified":
                status, reason = "unverified", "来源尚未完成公开核验，只能进入待核"

            decisions.append(
                {
                    "source_id": source_id,
                    "status": status,
                    "effective_source_id": effective_source_id,
                    "reason": reason,
                }
            )
        return {"decisions": decisions}

    def _merge_events(self) -> dict[str, Any]:
        loaded_by_id = {
            item["source"]["source_id"]: item
            for item in self._results["read_weekly_source_pack"]["materials"]
        }
        decisions = {
            item["source_id"]: item
            for item in self._results["resolve_weekly_versions"]["decisions"]
        }
        usable_statuses = {"current", "duplicate", "unverified"}
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for material in self.materials:
            source_id = material["source_id"]
            if source_id in loaded_by_id and decisions[source_id]["status"] in usable_statuses:
                groups[material["event_key"]].append(material)

        events: list[dict[str, Any]] = []
        for event_key, items in groups.items():
            source_ids = [item["source_id"] for item in items]
            events.append(
                {
                    "event_key": event_key,
                    "source_ids": source_ids,
                    "primary_source_id": next(
                        (item["source_id"] for item in items if decisions[item["source_id"]]["status"] == "current"),
                        source_ids[0],
                    ),
                    "brands": sorted({brand for item in items for brand in item["brands"]}),
                    "regions": sorted({region for item in items for region in item["regions"]}),
                    "verification_status": (
                        "unverified"
                        if all(item["verification_status"] == "unverified" for item in items)
                        else "verified"
                    ),
                    "material_count": len(items),
                }
            )
        return {"events": events}

    def prompt_payload(self) -> dict[str, Any]:
        self._require_complete()
        return {
            "settings": self.settings,
            "materials": self._results["read_weekly_source_pack"]["materials"],
            "version_decisions": self._results["resolve_weekly_versions"]["decisions"],
            "merge_records": self._results["merge_weekly_events"]["events"],
        }

    def validator_payload(self) -> dict[str, Any]:
        self._require_complete()
        read_result = self._results["read_weekly_source_pack"]
        version_decisions = self._results["resolve_weekly_versions"]["decisions"]
        excluded = [
            {"source_id": item["source_id"], "reason": item["reason"]}
            for item in version_decisions
            if item["status"] in {"failed", "expired", "superseded"}
        ]
        return {
            "observation_settings": self.settings,
            "source_catalog": [self._public_source_record(item) for item in self.materials],
            "material_log": {
                "read_success": read_result["read_success"],
                "read_failed": read_result["read_failed"],
                "excluded": excluded,
            },
            "version_decisions": version_decisions,
            "merge_records": self._results["merge_weekly_events"]["events"],
        }

    def load_expected_candidate(self) -> dict[str, Any]:
        relative = self.manifest.get("expected_result_file", "expected-result.json")
        if not isinstance(relative, str) or not relative:
            raise WeeklySourcePackError("manifest.expected_result_file 必须是观察包内文件")
        path = self._safe_pack_file(relative, "manifest.expected_result_file")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise WeeklySourcePackError(f"Mock 期望结果无法读取或不是有效 JSON：{relative}") from exc
        if not isinstance(data, dict):
            raise WeeklySourcePackError("Mock 期望结果顶层必须是对象")
        return data

    def _require_complete(self) -> None:
        if self._next_tool_index != len(WEEKLY_TOOL_ORDER):
            raise WeeklyPipelineError("weekly 工具链尚未完整执行")

    @staticmethod
    def _public_source_record(material: dict[str, Any]) -> dict[str, Any]:
        return {
            "source_id": material["source_id"],
            "title": material["title"],
            "source_type": material["source_type"],
            "source_date": material["source_date"],
            "url": material["url"],
            "file": material["file"],
            "verification_status": material["verification_status"],
        }


def execute_weekly_tool(runtime: WeeklyScenarioRuntime, tool_name: str, arguments: dict[str, Any]) -> str:
    """Runner-compatible executor kept explicit so no global source-pack state exists."""

    return runtime.execute(tool_name, arguments)
