"""Read the dedicated simulator canvas after an opt-in live acceptance run.

Usage: python3 ios/tests/live_acceptance_readback.py <app data container> visual|voice
Only synthetic acceptance boards are inspected; no connection settings are read.
"""

import json
import re
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in {"visual", "voice"}:
        print("usage: live_acceptance_readback.py <app data container> visual|voice")
        return 2
    support = Path(sys.argv[1]) / "Library" / "Application Support"
    boards = json.loads((support / "live-acceptance-boards.json").read_text())
    mode = sys.argv[2]
    title = "合成视觉材料验收" if mode == "visual" else "合成分段口述验收"
    board = next((item for item in boards if item["title"] == title), None)
    if board is None:
        print(json.dumps({"passed": False, "reason": "acceptance board missing"}, ensure_ascii=False))
        return 1
    cards = {card["id"]: card for card in board["cards"] if card.get("status") != "archived"}
    edges = board["edges"]
    originals = [card for card in cards.values() if card.get("title") == "合成图片与手绘素材"]
    original_ok = len(originals) == 1 and {block["kind"] for block in originals[0].get("blocks", [])} >= {"image", "drawing"}
    diagnostics = {"boardID": board["id"], "cardCount": len(cards), "edgeCount": len(edges), "originalPreserved": original_ok}
    if mode == "visual":
        generated = [card for card in cards.values() if card not in originals]
        def text(card):
            return " ".join([card.get("title", ""), card.get("body", "")] + [block.get("text", "") for block in card.get("blocks", [])]).upper()
        labels = {
            "PLUM": lambda value: "PLUM" in value,
            "ORBIT": lambda value: "ORBIT" in value,
            "7": lambda value: re.search(r"(?<!\d)7(?!\d)", value) is not None,
            "9": lambda value: re.search(r"(?<!\d)9(?!\d)", value) is not None,
        }
        matches = {label: [card["id"] for card in generated if check(text(card))] for label, check in labels.items()}
        paths = {(edge["fromID"], edge["toID"]) for edge in edges}
        direction = lambda a, b: any((x, y) in paths for x in matches[a] for y in matches[b] if x != y)
        diagnostics.update({"labelCardCounts": {key: len(value) for key, value in matches.items()},
                            "imageDirection": direction("PLUM", "ORBIT"), "drawingDirection": direction("7", "9"),
                            "generatedSourceLinks": sum(bool(card.get("sourceIDs")) for card in generated)})
        passed = original_ok and all(matches.values()) and direction("PLUM", "ORBIT") and direction("7", "9")
    else:
        evidence_file = support / "live-acceptance-evidence.json"
        evidence = json.loads(evidence_file.read_text()) if evidence_file.exists() else {}
        theme = [card["id"] for card in cards.values() if "周末活动主题" in card.get("title", "")]
        execution = [card["id"] for card in cards.values() if "周末活动执行" in card.get("title", "")]
        direction = any(edge["fromID"] in theme and edge["toID"] in execution for edge in edges)
        diagnostics.update(evidence)
        diagnostics["themeToExecution"] = direction
        passed = original_ok and direction and evidence.get("firstValidUpdateSeconds") is not None and evidence.get("firstBatchSequence", 0) > 0 and evidence.get("finalSequence", 0) > evidence.get("firstBatchSequence", 0)
    diagnostics["passed"] = bool(passed)
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
