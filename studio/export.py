"""Readable exports of the user's current work, with its actual sources."""

from __future__ import annotations

from html import escape
from urllib.parse import urlsplit


LABELS = {"observation": "观察与判断", "idea": "创意方向", "source": "研究材料",
          "question": "值得继续查的问题", "note": "工作稿", "calendar": "时间与节点"}


def markdown(task: dict) -> str:
    lines = [f"# {task['title']}", "", task.get("question", ""), "",
             f"品牌：{task.get('brand', '')} · 更新：{task.get('updated_at', '')[:10]}", "",
             "本地企划工作稿。创意与推断用于讨论，公开材料不代表品牌合作或执行授权。", ""]
    sources = {source["id"]: source for source in task["sources"]}
    for card in task["cards"]:
        if card["status"] == "archived" or card["kind"] == "source":
            continue
        lines.extend([f"## {card['title']}", "", f"{LABELS.get(card['kind'], '工作稿')}"
                      + (" · 已保留" if card["status"] == "kept" else ""), "", card["body"], ""])
        for source_id in card.get("source_ids", []):
            source = sources.get(source_id)
            if source:
                lines.append(f"依据：{source['title']}" + (f" — {source['url']}" if source.get("url") else "（补充材料）"))
        lines.append("")
    lines.extend(["## 研究材料", ""])
    for source in task["sources"]:
        lines.extend([f"### {source['title']}", "", source.get("excerpt", ""), "",
                      source.get("url") or "用户补充材料",
                      f"发布：{source.get('published_at') or '未标注'} · 读取：{source.get('accessed_at', '')[:10]}", ""])
    return "\n".join(lines)


def html(task: dict) -> str:
    def paragraphs(text):
        return "".join(f"<p>{escape(part).replace(chr(10), '<br>')}</p>" for part in str(text).split("\n\n") if part)
    def source_link(source):
        label = escape(source["title"])
        url = source.get("url") or ""
        if urlsplit(url).scheme in {"http", "https"}:
            return f'<a href="{escape(url, quote=True)}" target="_blank" rel="noreferrer">{label} ↗</a>'
        return label
    sources = {source["id"]: source for source in task["sources"]}
    sections = []
    for card in task["cards"]:
        if card["status"] == "archived" or card["kind"] == "source":
            continue
        references = " · ".join(source_link(sources[ref]) for ref in card.get("source_ids", []) if ref in sources)
        sections.append(f'<article><div class="label">{LABELS.get(card["kind"], "工作稿")}'
                        f'{" · 已保留" if card["status"] == "kept" else ""}</div>'
                        f'<h2>{escape(card["title"])}</h2>{paragraphs(card["body"])}'
                        f'<footer>{references}</footer></article>')
    materials = "".join(f'<li>{source_link(source)}{paragraphs(source.get("excerpt", ""))}'
                        f'<small>发布：{escape(str(source.get("published_at") or "未标注"))} · '
                        f'读取：{escape(source.get("accessed_at", "")[:10])}</small></li>'
                        for source in task["sources"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(task['title'])} · Brand Radar</title>
<style>body{{margin:0;background:#f4f0e7;color:#242a26;font:16px/1.8 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}
main{{max-width:860px;margin:64px auto;padding:0 28px}}h1{{font-size:38px;line-height:1.25;letter-spacing:-1px}}h2{{font-size:25px;line-height:1.4}}
.masthead{{letter-spacing:3px;font-size:12px;color:#6e776b}}.intro{{font-size:18px}}article{{background:#fffdf8;padding:30px 34px;margin:25px 0;border:1px solid #ded8cc;border-radius:12px;break-inside:avoid}}
.label,small,footer{{font-size:12px;color:#677363}}footer{{border-top:1px solid #e6e0d4;padding-top:14px}}a{{color:#35634e;text-underline-offset:3px}}li{{margin:24px 0}}.note{{font-size:13px;color:#697266}}
@media(max-width:600px){{main{{margin:30px auto;padding:0 18px}}h1{{font-size:28px}}article{{padding:22px}}}}@media print{{body{{background:white}}main{{margin:0;max-width:none}}}}</style></head>
<body><main><div class="masthead">BRAND RADAR / 企划工作稿</div><h1>{escape(task['title'])}</h1>
<div class="intro">{paragraphs(task.get('question', ''))}</div>
<p class="note">{escape(task.get('brand', ''))} · {escape(task.get('updated_at', '')[:10])} · 创意与推断用于讨论，公开材料不代表品牌合作或执行授权。</p>
{''.join(sections)}<h2>研究材料</h2><ol>{materials}</ol></main></body></html>'''
