"""Brand Radar weekly Replay scenario.

The scenario is deliberately local and read-only: it reads one manifest and
the files explicitly listed by that manifest, performs stable version and
merge bookkeeping, and exposes the resulting evidence to a bounded single-Agent
decision loop.
It has no network, publishing, messaging, advertising, or budget tools.
"""

from __future__ import annotations

import copy
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

INVESTIGATION_ACTION_NAMES = (
    "inspect_local_evidence",
    "compare_event_versions",
    "compare_competitor_evidence",
    "cross_check_conflicting_evidence",
)
MAX_INVESTIGATION_ACTIONS = 3


def _investigation_tool(name: str, description: str, argument: str) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {argument: {"type": "string"}},
                "required": [argument],
                "additionalProperties": False,
            },
        },
    }


INVESTIGATION_TOOLS = [
    _investigation_tool(
        "inspect_local_evidence",
        "检查当前观察包中一份材料的正文摘要与核验状态。",
        "source_id",
    ),
    _investigation_tool(
        "compare_event_versions",
        "比较当前观察包内同一版本组的版本关系与有效状态。",
        "version_group",
    ),
    _investigation_tool(
        "compare_competitor_evidence",
        "比较当前观察包内指定竞品已有材料与证据缺口。",
        "competitor",
    ),
    _investigation_tool(
        "cross_check_conflicting_evidence",
        "交叉核对当前观察包内同一事件的冲突与待核状态。",
        "event_key",
    ),
]

_INVESTIGATION_ARGUMENTS = {
    "inspect_local_evidence": "source_id",
    "compare_event_versions": "version_group",
    "compare_competitor_evidence": "competitor",
    "cross_check_conflicting_evidence": "event_key",
}


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
        self._investigation_signatures: set[str] = set()

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

        ranked_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for material in self.materials:
            group = material.get("version_group")
            if not group or material["source_id"] not in available:
                continue
            ranked_by_group[group].append(material)

        newest_by_group: dict[str, dict[str, Any]] = {}
        unresolved_groups: dict[str, list[str]] = {}
        selected_rank_by_group: dict[str, int] = {}
        for group, items in ranked_by_group.items():
            effective_items = [
                item
                for item in items
                if not item.get("valid_to")
                or date.fromisoformat(item["valid_to"]) >= observation_start
            ]
            if not effective_items:
                continue
            highest_rank = max(item.get("version_rank", 0) for item in effective_items)
            selected_rank_by_group[group] = highest_rank
            highest = [
                item
                for item in effective_items
                if item.get("version_rank", 0) == highest_rank
            ]
            explicitly_superseded = {
                source_id
                for item in highest
                for source_id in item.get("supersedes", [])
            }
            candidates = [
                item
                for item in highest
                if not item.get("duplicate_of")
                and item["source_id"] not in explicitly_superseded
            ]
            if len(candidates) == 1:
                newest_by_group[group] = candidates[0]
            else:
                unresolved_groups[group] = sorted(item["source_id"] for item in candidates or highest)

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
            elif (
                material.get("version_group") in unresolved_groups
                and source_id in unresolved_groups[material["version_group"]]
            ):
                conflict_ids = unresolved_groups[material["version_group"]]
                status = "unresolved_conflict"
                reason = (
                    "同一版本组存在并列最高版本且无明确覆盖或重复关系："
                    + "、".join(conflict_ids)
                    + "；保留冲突等待查证或人工判断"
                )
            elif material.get("version_group") in unresolved_groups:
                conflict_ids = unresolved_groups[material["version_group"]]
                is_expired = bool(
                    material.get("valid_to")
                    and date.fromisoformat(material["valid_to"]) < observation_start
                )
                if (
                    is_expired
                    and material.get("version_rank", 0)
                    >= selected_rank_by_group[material["version_group"]]
                ):
                    status, reason = (
                        "expired",
                        f"有效期已在观察窗前结束（{material['valid_to']}）",
                    )
                else:
                    status = "superseded"
                    expiry = f"，且有效期已于 {material['valid_to']} 结束" if is_expired else ""
                    reason = (
                        "同组已有更高的并列候选 "
                        + "、".join(conflict_ids)
                        + f"；旧材料不进入当前事实卡{expiry}"
                    )
            elif material.get("version_group") in newest_by_group:
                newest = newest_by_group[material["version_group"]]
                if newest["source_id"] != source_id:
                    is_expired = bool(
                        material.get("valid_to")
                        and date.fromisoformat(material["valid_to"]) < observation_start
                    )
                    if (
                        is_expired
                        and material.get("version_rank", 0)
                        >= newest.get("version_rank", 0)
                    ):
                        status, reason = (
                            "expired",
                            f"有效期已在观察窗前结束（{material['valid_to']}）",
                        )
                    else:
                        status = "superseded"
                        effective_source_id = newest["source_id"]
                        expiry = f"，且有效期已于 {material['valid_to']} 结束" if is_expired else ""
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
        usable_statuses = {"current", "duplicate", "unverified", "unresolved_conflict"}
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
                        if any(
                            item["verification_status"] == "unverified"
                            or decisions[item["source_id"]]["status"] == "unresolved_conflict"
                            for item in items
                        )
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

    def observation_payload(self) -> dict[str, Any]:
        """Return the compact pack-bound view used to plan investigation actions."""

        self._require_complete()
        decisions = {
            item["source_id"]: item
            for item in self._results["resolve_weekly_versions"]["decisions"]
        }
        evidence_index = [
            {
                "source_id": item["source_id"],
                "title": item["title"],
                "source_date": item["source_date"],
                "event_key": item["event_key"],
                "version_group": item.get("version_group"),
                "version_rank": item.get("version_rank", 0),
                "brands": item["brands"],
                "regions": item["regions"],
                "verification_status": item["verification_status"],
                "version_status": decisions[item["source_id"]]["status"],
            }
            for item in self.materials
        ]
        represented_competitors = {
            competitor
            for item in self.materials
            for competitor in self.settings["competitors"]
            if competitor in item["brands"]
            and decisions[item["source_id"]]["status"]
            in {"current", "duplicate", "unverified", "unresolved_conflict"}
        }
        return {
            "pack_id": self.manifest["pack_id"],
            "marketing_goal": {
                field: copy.deepcopy(self.settings[field])
                for field in (
                    "brand",
                    "category",
                    "regions",
                    "competitors",
                    "keywords",
                    "business_question",
                    "observation_window",
                )
            },
            "evidence_index": evidence_index,
            "attention_required": {
                "unresolved_version_groups": sorted(
                    {
                        item["version_group"]
                        for item in self.materials
                        if item.get("version_group")
                        and decisions[item["source_id"]]["status"] == "unresolved_conflict"
                    }
                ),
                "unverified_source_ids": sorted(
                    item["source_id"]
                    for item in self.materials
                    if item["verification_status"] == "unverified"
                ),
                "excluded_source_ids": sorted(
                    source_id
                    for source_id, decision in decisions.items()
                    if decision["status"] in {"failed", "expired", "superseded"}
                ),
                "competitors_without_evidence": sorted(
                    set(self.settings["competitors"]) - represented_competitors
                ),
            },
            "investigation_constraints": {
                "max_actions": MAX_INVESTIGATION_ACTIONS,
                "allowed_actions": list(INVESTIGATION_ACTION_NAMES),
                "reference_whitelist": {
                    "source_ids": sorted(item["source_id"] for item in self.materials),
                    "event_keys": sorted({item["event_key"] for item in self.materials}),
                    "version_groups": sorted(
                        {item["version_group"] for item in self.materials if item.get("version_group")}
                    ),
                    "competitors": list(self.settings["competitors"]),
                },
            },
        }

    def execute_investigation_action(
        self,
        action_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute one distinct, pack-bound, local read-only investigation action."""

        self._require_complete()
        argument_name = _INVESTIGATION_ARGUMENTS.get(action_name)
        if argument_name is None:
            raise WeeklyPipelineError(f"调查动作不在调查白名单：{action_name}")
        if not isinstance(arguments, dict) or set(arguments) != {argument_name}:
            raise WeeklyPipelineError(f"调查动作 {action_name} 只接受参数 {argument_name}")
        argument_value = arguments[argument_name]
        if not isinstance(argument_value, str) or not argument_value.strip():
            raise WeeklyPipelineError(f"调查动作 {action_name} 的 {argument_name} 必须是非空字符串")
        argument_value = argument_value.strip()

        allowed_values = {
            "source_id": {item["source_id"] for item in self.materials},
            "event_key": {item["event_key"] for item in self.materials},
            "version_group": {
                item["version_group"] for item in self.materials if item.get("version_group")
            },
            "competitor": set(self.settings["competitors"]),
        }[argument_name]
        if argument_value not in allowed_values:
            raise WeeklyPipelineError(
                f"调查参数 {argument_name}={argument_value!r} 不在当前观察包白名单"
            )

        normalized_arguments = {argument_name: argument_value}
        signature = f"{action_name}::{json.dumps(normalized_arguments, sort_keys=True, ensure_ascii=False)}"
        if signature in self._investigation_signatures:
            raise WeeklyPipelineError(f"调查动作签名重复：{signature}")
        if len(self._investigation_signatures) >= MAX_INVESTIGATION_ACTIONS:
            raise WeeklyPipelineError(f"本次调查最多允许 {MAX_INVESTIGATION_ACTIONS} 个不同动作")
        self._investigation_signatures.add(signature)

        return {
            "inspect_local_evidence": self._inspect_local_evidence,
            "compare_event_versions": self._compare_event_versions,
            "compare_competitor_evidence": self._compare_competitor_evidence,
            "cross_check_conflicting_evidence": self._cross_check_conflicting_evidence,
        }[action_name](normalized_arguments)

    def generation_payload(self, trace: dict[str, Any]) -> dict[str, Any]:
        """Attach a recorded investigation trace to the complete generation evidence."""

        self._require_complete()
        if not isinstance(trace, dict):
            raise WeeklyPipelineError("investigation trace 必须是对象")
        return {
            **self.prompt_payload(),
            "investigation_trace": copy.deepcopy(trace),
        }

    def _inspect_local_evidence(self, arguments: dict[str, str]) -> dict[str, Any]:
        source_id = arguments["source_id"]
        material = next(item for item in self.materials if item["source_id"] == source_id)
        decision = self._decision_by_source()[source_id]
        loaded = self._loaded_by_source().get(source_id)
        if loaded is None:
            outcome = "local_evidence_unavailable"
            summary = f"{material['title']} 的本地材料未能读取。"
            hint = "不要根据标题补写事实；保留读取失败并交给人工补证。"
        elif decision["status"] == "unresolved_conflict":
            outcome = "unresolved_conflict"
            summary = self._material_summary(material, loaded["content"])
            hint = "该材料处于未解决版本冲突中，不能单独作为当前有效事实。"
        elif decision["status"] in {"failed", "expired", "superseded"}:
            outcome = "excluded_from_current_decision"
            summary = self._material_summary(material, loaded["content"])
            hint = f"该材料状态为 {decision['status']}，只保留审计记录，不进入当前事实卡。"
        elif material["verification_status"] == "unverified":
            outcome = "needs_verification"
            summary = self._material_summary(material, loaded["content"])
            hint = "只能形成待核判断，并列出需要补充的公开证据。"
        else:
            outcome = "verified_evidence"
            summary = self._material_summary(material, loaded["content"])
            hint = "可结合营销目标判断价值，但不得超出材料原文推导经营或合作事实。"
        return self._feedback(
            "inspect_local_evidence", arguments, [source_id], summary, outcome, hint
        )

    def _compare_event_versions(self, arguments: dict[str, str]) -> dict[str, Any]:
        version_group = arguments["version_group"]
        items = [item for item in self.materials if item.get("version_group") == version_group]
        decisions = self._decision_by_source()
        source_ids = [item["source_id"] for item in items]
        summaries = [
            f"{item['source_id']} rank={item.get('version_rank', 0)} status={decisions[item['source_id']]['status']}"
            for item in items
        ]
        if any(decisions[source_id]["status"] == "unresolved_conflict" for source_id in source_ids):
            outcome = "unresolved_conflict"
            hint = "没有唯一当前版；保留冲突并交由进一步查证或人工判断。"
        else:
            outcome = "latest_version_resolved"
            current = next(
                (source_id for source_id in source_ids if decisions[source_id]["status"] in {"current", "unverified"}),
                source_ids[0],
            )
            hint = f"以 {current} 作为当前版本；重复材料只补充来源，被覆盖材料不进入事实卡。"
        return self._feedback(
            "compare_event_versions",
            arguments,
            source_ids,
            "；".join(summaries),
            outcome,
            hint,
        )

    def _compare_competitor_evidence(self, arguments: dict[str, str]) -> dict[str, Any]:
        competitor = arguments["competitor"]
        items = [item for item in self.materials if competitor in item["brands"]]
        if not items:
            return self._feedback(
                "compare_competitor_evidence",
                arguments,
                [],
                f"当前观察包没有 {competitor} 的直接材料。",
                "no_pack_evidence",
                "材料缺口不等于竞品没有动作；只能记录缺证，不能推断市场空位。",
            )

        decisions = self._decision_by_source()
        usable_statuses = {"current", "duplicate", "unverified", "unresolved_conflict"}
        usable_items = [
            item
            for item in items
            if decisions[item["source_id"]]["status"] in usable_statuses
        ]
        if not usable_items:
            source_ids = [item["source_id"] for item in items]
            statuses = sorted(
                {decisions[source_id]["status"] for source_id in source_ids}
            )
            return self._feedback(
                "compare_competitor_evidence",
                arguments,
                source_ids,
                f"当前观察包只有 {competitor} 的过期、被替换或读取失败材料（状态：{'、'.join(statuses)}）。",
                "no_current_pack_evidence",
                "这些材料不能作为当前竞品动作；只能记录当前证据缺口，并保留旧材料用于追溯。",
            )

        source_ids = [item["source_id"] for item in usable_items]
        version_states = {
            decisions[item["source_id"]]["status"] for item in usable_items
        }
        verification_states = {item["verification_status"] for item in usable_items}
        if "unresolved_conflict" in version_states:
            outcome = "unresolved_conflict"
            hint = "竞品材料存在未解决版本冲突，只能形成待核判断。"
        elif verification_states == {"verified", "unverified"}:
            outcome = "mixed_verification"
            hint = "已核材料与待核补充必须分层使用，整体不能提升为确定竞品事实。"
        elif verification_states == {"unverified"}:
            outcome = "unverified_only"
            hint = "现有竞品材料只能进入待核，不支持确定性比较。"
        else:
            outcome = "verified_competitor_evidence"
            hint = "可比较材料明确写出的动作，但不能把未出现的其他竞品推断为没有动作。"
        loaded_by_source = self._loaded_by_source()
        summary = "；".join(
            self._material_summary(item, loaded_by_source[item["source_id"]]["content"])
            for item in usable_items
            if item["source_id"] in loaded_by_source
        )
        return self._feedback(
            "compare_competitor_evidence", arguments, source_ids, summary, outcome, hint
        )

    def _cross_check_conflicting_evidence(self, arguments: dict[str, str]) -> dict[str, Any]:
        event_key = arguments["event_key"]
        items = [item for item in self.materials if item["event_key"] == event_key]
        source_ids = [item["source_id"] for item in items]
        decisions = self._decision_by_source()
        statuses = {decisions[source_id]["status"] for source_id in source_ids}
        verification_states = {item["verification_status"] for item in items}
        if "unresolved_conflict" in statuses:
            outcome = "unresolved_conflict"
            hint = "并列最高版本没有明确关系，不能选一份作为当前真值；保留待核并交人判断。"
        elif verification_states == {"verified", "unverified"}:
            outcome = "mixed_verification"
            hint = "待核补充不能提升已核材料的结论范围，合并事件整体保持待核。"
        elif len(items) == 1:
            outcome = "single_source_no_conflict"
            hint = "当前包只有一份相关材料，不能把未发现冲突等同于已经多源核验。"
        else:
            outcome = "consistent_evidence"
            hint = "材料关系没有显示未解决冲突，仍按各自来源范围形成判断。"
        loaded_by_source = self._loaded_by_source()
        summary = "；".join(
            self._material_summary(item, loaded_by_source[item["source_id"]]["content"])
            for item in items
            if item["source_id"] in loaded_by_source
        )
        return self._feedback(
            "cross_check_conflicting_evidence", arguments, source_ids, summary, outcome, hint
        )

    def _decision_by_source(self) -> dict[str, dict[str, Any]]:
        return {
            item["source_id"]: item
            for item in self._results["resolve_weekly_versions"]["decisions"]
        }

    def _loaded_by_source(self) -> dict[str, dict[str, Any]]:
        return {
            item["source"]["source_id"]: item
            for item in self._results["read_weekly_source_pack"]["materials"]
        }

    @staticmethod
    def _material_summary(material: dict[str, Any], content: str) -> str:
        lines = [line.strip() for line in content.splitlines()]
        section_start = next(
            (index + 1 for index, line in enumerate(lines) if line.startswith("## ")),
            1,
        )
        body = " ".join(line.lstrip("- >").strip() for line in lines[section_start:] if line.strip())
        if len(body) > 800:
            body = body[:797].rstrip() + "..."
        return f"{material['title']}：{body or '材料未提供可摘取的正文摘要。'}"

    @staticmethod
    def _feedback(
        action: str,
        arguments: dict[str, str],
        source_ids: list[str],
        summary: str,
        outcome: str,
        decision_hint: str,
    ) -> dict[str, Any]:
        return {
            "action": action,
            "arguments": arguments,
            "source_ids": source_ids,
            "summary": summary,
            "outcome": outcome,
            "decision_hint": decision_hint,
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
