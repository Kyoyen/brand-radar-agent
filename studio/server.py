"""Local HTTP entry point. The same task document drives the canvas and agent."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from dotenv import load_dotenv

from studio import export
from studio.store import ROOT, TaskStore, now, uid

load_dotenv(ROOT / ".env")
MAX_BODY = 2_000_000


def read_cases() -> list[dict]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "data" / "cases").glob("*.json"))]


def connection_status() -> dict:
    from framework.llm_client import DEFAULT_MODELS, PROVIDER_KEY_ENV, PROVIDER_KEY_ENV_FALLBACKS
    provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
    keys = [PROVIDER_KEY_ENV.get(provider, "")] + list(PROVIDER_KEY_ENV_FALLBACKS.get(provider, ()))
    return {"configured": any(os.getenv(key, "").strip() for key in keys if key),
            "provider": provider, "model": os.getenv("LLM_MODEL") or DEFAULT_MODELS.get(provider, "")}


class Studio:
    def __init__(self, store: TaskStore | None = None):
        self.store = store or TaskStore()
        self.store.recover_interrupted()
        self.runs: dict[str, tuple[threading.Thread, threading.Event]] = {}
        self.run_lock = threading.RLock()

    def start(self, task_id: str, content: str, selected: list[str]) -> dict:
        from studio.agent import run_agent
        if not content.strip():
            raise ValueError("先写下这次想推进的问题")
        if not connection_status()["configured"]:
            raise ValueError("还没有连接模型。在项目 .env 中填写模型 Key 后重启即可。")
        with self.run_lock:
            active = self.runs.get(task_id)
            if active and active[0].is_alive():
                raise RuntimeError("正在处理这次企划，请等这一轮完成或先停止")
            task = self.store.get(task_id)
            valid_ids = {card["id"] for card in task["cards"]}
            if any(card_id not in valid_ids for card_id in selected):
                raise ValueError("选中的卡片已不在桌面上，请重新选择")
            self.store.add_message(task_id, "user", content, selected)
            run_id = uid("run")
            self.store.mutate(task_id, lambda task: task.update(status="running", error=None, run_id=run_id))
            stop_event = threading.Event()
            thread = threading.Thread(target=run_agent, args=(task_id, self.store, stop_event),
                                      name=f"radar-{task_id}", daemon=True)
            self.runs[task_id] = (thread, stop_event)
            thread.start()
            return {"task_id": task_id, "run_id": run_id}

    def stop(self, task_id: str) -> dict:
        with self.run_lock:
            task = self.store.get(task_id)
            run = self.runs.get(task_id)
            if run and run[0].is_alive():
                run[1].set()
                self.store.emit(task_id, "正在停止", "当前请求返回后停止，已完成的草稿会保留")
            elif task["status"] == "running":
                self.store.mutate(task_id, lambda item: item.update(status="stopped"))
            return self.store.get(task_id)

    def shutdown(self):
        with self.run_lock:
            for thread, event in self.runs.values():
                if thread.is_alive():
                    event.set()


class Handler(BaseHTTPRequestHandler):
    server_version = "BrandRadar"

    @property
    def app(self) -> Studio:
        return self.server.app

    def log_message(self, message, *args):
        # Requests may contain private questions; log only unusual status codes.
        if len(args) > 1 and str(args[1]) not in {"200", "201", "202", "304"}:
            print(f"[HTTP] {self.command} {str(args[1])}", flush=True)

    def _send(self, value, status=200, content_type="application/json; charset=utf-8", attachment=None):
        body = (json.dumps(value, ensure_ascii=False).encode("utf-8")
                if content_type.startswith("application/json") else value.encode("utf-8") if isinstance(value, str) else value)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if attachment:
            self.send_header("Content-Disposition", f'attachment; filename="{attachment}"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _local_request(self):
        host = urlsplit("http://" + self.headers.get("Host", "")).hostname
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise PermissionError("企划桌面仅接受本机访问")
        origin = self.headers.get("Origin")
        if origin and urlsplit(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise PermissionError("请从本机企划桌面发起操作")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise PermissionError("请从本机企划桌面发起操作")

    def _body(self) -> dict:
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ValueError("请使用 JSON 提交内容")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("请求长度不正确") from None
        if not 0 < size <= MAX_BODY:
            raise ValueError("内容为空或超过 2 MB，请分次添加材料")
        try:
            result = json.loads(self.rfile.read(size))
        except ValueError:
            raise ValueError("提交的内容无法读取") from None
        if not isinstance(result, dict):
            raise ValueError("请求内容需要是 JSON 对象")
        return result

    def _dispatch(self):
        self._local_request()
        parsed = urlsplit(self.path)
        path = parsed.path.rstrip("/")
        store = self.app.store
        method = self.command
        if method == "GET" and path == "/api/status":
            self._send(connection_status() | {"running_task_ids": [item["id"] for item in store.list() if item["status"] == "running"]})
        elif method == "GET" and path == "/api/cases":
            self._send({"cases": [{key: case.get(key) for key in ("id", "title", "description", "question", "brand")}
                                  for case in read_cases()]})
        elif path == "/api/tasks" and method == "GET":
            self._send({"tasks": store.list()})
        elif path == "/api/tasks" and method == "POST":
            data = self._body()
            case = next((case for case in read_cases() if case["id"] == data.get("case_id")), None)
            if data.get("case_id") and case is None:
                raise ValueError("找不到这个研究起点")
            case = case or {}
            question = str(data.get("question") or case.get("question") or "").strip()
            if not question:
                raise ValueError("写下一句想推进的问题，就可以开始")
            self._send(store.create(title=str(data.get("title") or case.get("title") or question[:32]),
                                    question=question, brand=str(data.get("brand") or case.get("brand") or "瑞幸咖啡"),
                                    brand_context=case.get("brand_context", ""), sources=case.get("sources", []),
                                    case_id=case.get("id")), status=201)
        elif path == "/api/brand" and method in {"GET", "PUT"}:
            custom = ROOT / "memory" / "brand" / "BRAND.md"
            if method == "PUT":
                content = str(self._body().get("content", "")).strip()
                if not content or len(content) > 24000:
                    raise ValueError("品牌底稿需要有内容，并控制在 24000 字以内")
                custom.parent.mkdir(parents=True, exist_ok=True)
                temporary = custom.with_suffix(".md.tmp")
                temporary.write_text(content + "\n", encoding="utf-8")
                temporary.replace(custom)
            brand_file = custom if custom.exists() else ROOT / "BRAND.md"
            self._send({"content": brand_file.read_text(encoding="utf-8"),
                        "source": "custom" if custom.exists() else "default"})
        elif path.startswith("/api/tasks/"):
            parts = path.split("/")
            task_id = parts[3]
            if len(parts) == 4 and method == "GET":
                self._send(store.get(task_id))
            elif len(parts) == 4 and method == "PATCH":
                self._send(store.patch(task_id, self._body()))
            elif len(parts) == 5 and parts[4] == "messages" and method == "POST":
                data = self._body()
                selected = data.get("selected_card_ids", [])
                if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected):
                    raise ValueError("请选择桌面上的卡片")
                self._send(self.app.start(task_id, str(data.get("content", ""))[:16000], selected), status=202)
            elif len(parts) == 5 and parts[4] == "stop" and method == "POST":
                self._send(self.app.stop(task_id))
            elif len(parts) == 5 and parts[4] == "sources" and method == "POST":
                data = self._body()
                store.get(task_id)
                if data.get("url"):
                    from studio.tools import fetch_url
                    source = fetch_url(str(data["url"]))
                else:
                    text = str(data.get("text") or "").strip()
                    if not text:
                        raise ValueError("请粘贴材料正文或填写公开链接")
                    if len(text) > 60000:
                        raise ValueError("一份材料请控制在 60000 字以内")
                    source = {"title": str(data.get("title") or "我补充的材料")[:240],
                              "text": text, "excerpt": text[:450], "origin": "manual"}
                saved = store.add_source(task_id, source)
                current = store.get(task_id)
                if not any(card["kind"] == "source" and saved["id"] in card["source_ids"] for card in current["cards"]):
                    store.upsert_cards(task_id, [{"id": f"card_{saved['id']}", "kind": "source", "title": saved["title"],
                                                  "body": saved["excerpt"], "source_ids": [saved["id"]], "color": "cream"}])
                store.emit(task_id, "加入了新材料", saved["title"])
                self._send(store.get(task_id))
            elif len(parts) == 5 and parts[4] == "export" and method == "GET":
                task = store.get(task_id)
                fmt = parse_qs(parsed.query).get("format", ["html"])[0]
                if fmt == "md":
                    self._send(export.markdown(task), content_type="text/markdown; charset=utf-8", attachment=f"brand-radar-{task_id}.md")
                else:
                    self._send(export.html(task), content_type="text/html; charset=utf-8", attachment=f"brand-radar-{task_id}.html")
            else:
                self._send({"error": "没有这个操作"}, 404)
        elif path.startswith("/api/"):
            self._send({"error": "没有这个接口"}, 404)
        elif method in {"GET", "HEAD"}:
            self._static(parsed.path)
        else:
            self._send({"error": "没有这个操作"}, 404)

    def _static(self, path):
        dist = ROOT / "web" / "dist"
        relative = path.lstrip("/") or "index.html"
        candidate = (dist / relative).resolve()
        if not candidate.is_relative_to(dist.resolve()):
            raise PermissionError("无法访问这个文件")
        if not candidate.is_file():
            if Path(relative).suffix:
                self._send("Not found", 404, "text/plain; charset=utf-8")
                return
            candidate = dist / "index.html"
        if not candidate.is_file():
            self._send("企划桌面还没有构建。请在 web 目录运行 npm install 和 npm run build，再刷新。", 503,
                       "text/plain; charset=utf-8")
            return
        content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
        self._send(candidate.read_bytes(), content_type=content_type)

    def _handle(self):
        try:
            self._dispatch()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except KeyError as exc:
            self._send({"error": str(exc).strip("'")}, 404)
        except PermissionError as exc:
            self._send({"error": str(exc)}, 403)
        except ValueError as exc:
            self._send({"error": str(exc)}, 400)
        except RuntimeError as exc:
            self._send({"error": str(exc)}, 409)
        except Exception as exc:
            print(f"[HTTP] {type(exc).__name__}", flush=True)
            self._send({"error": "操作暂未完成，已有企划内容保留。请重试。"}, 500)

    do_GET = _handle
    do_HEAD = _handle
    do_POST = _handle
    do_PATCH = _handle
    do_PUT = _handle


def serve(port: int = 8765):
    app = Studio()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.app = app
    print(f"\nBrand Radar · 你的企划桌面\nhttp://127.0.0.1:{port}\n", flush=True)
    try:
        server.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:
        print("\n已停止，企划留在本机。", flush=True)
    finally:
        app.shutdown()
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Brand Radar · 本地企划桌面")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.port)


if __name__ == "__main__":
    main()
