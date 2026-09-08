"""Small, read-only web tools for the Brand Radar studio."""

from __future__ import annotations

import ipaddress
import queue
import re
import socket
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import httpx

MAX_BYTES = 1_500_000
MAX_TEXT = 30_000
REQUEST_SECONDS = 15
USER_AGENT = "BrandRadar/1.0 (public source reader)"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _public_target(url: str, dns_timeout: float = 5) -> tuple[str, str, str]:
    """Validate every resolved address and pin the request to a public IP."""
    try:
        parsed = urlsplit(url.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or any(ord(char) < 33 for char in url)
            or "\\" in url
        ):
            raise ValueError
        hostname = parsed.hostname.encode("idna").decode("ascii")
        if hostname.rstrip(".").lower() == "localhost" or hostname.lower().endswith((".localhost", ".local")):
            raise ValueError
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError
    except (ValueError, UnicodeError):
        raise ValueError("只允许不含账户信息的公开 HTTP / HTTPS 网页（80 / 443 端口）。") from None
    # The OS resolver has no per-call timeout. A daemon prevents a stalled DNS
    # lookup from holding the task or server shutdown indefinitely.
    resolved = queue.Queue(maxsize=1)
    def resolve():
        try:
            resolved.put(socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM))
        except OSError as exc:
            resolved.put(exc)
    threading.Thread(target=resolve, daemon=True).start()
    try:
        addresses = resolved.get(timeout=max(.05, dns_timeout))
    except queue.Empty:
        raise ValueError("网页域名解析超时。") from None
    if isinstance(addresses, OSError):
        raise ValueError("网页域名暂时无法解析。") from None
    ips = list(dict.fromkeys(item[4][0] for item in addresses))
    if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
        raise ValueError("不能读取本机、内网或保留地址。")
    clean = urlunsplit((parsed.scheme, parsed.netloc, parsed.path or "/", parsed.query, ""))
    return clean, hostname, ips[0]


def _download(url: str, seconds: float = REQUEST_SECONDS) -> tuple[str, str, str]:
    """Fetch with bounded redirects, bytes, timeout, and DNS rebinding protection."""
    deadline = time.monotonic() + seconds
    try:
        with httpx.Client(follow_redirects=False, trust_env=False) as client:
            for _ in range(5):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("网页读取超时；已有材料仍然保留。")
                clean, hostname, ip = _public_target(url, dns_timeout=min(5, remaining))
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("网页读取超时；已有材料仍然保留。")
                parsed = urlsplit(clean)
                host_header = parsed.netloc
                request_url = httpx.URL(clean).copy_with(host=ip)
                with client.stream(
                    "GET", request_url,
                    headers={"Host": host_header, "User-Agent": USER_AGENT, "Accept": "text/html,text/plain,application/rss+xml,application/xml;q=0.9"},
                    timeout=httpx.Timeout(min(remaining, 8.0)),
                    extensions={"sni_hostname": hostname},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("网页跳转缺少目标地址。")
                        url = urljoin(clean, location)
                        continue
                    if response.status_code >= 400:
                        raise ValueError(f"网页返回 HTTP {response.status_code}，未取得正文。")
                    content_type = response.headers.get("content-type", "").lower()
                    if not any(kind in content_type for kind in ("text/", "xml", "json", "xhtml")):
                        raise ValueError("这个链接不是可读取的文本网页；请提供原文页面。")
                    chunks: list[bytes] = []
                    size = 0
                    for chunk in response.iter_bytes(chunk_size=16_384):
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise ValueError("网页过大，停止读取；请提供更具体的原文链接。")
                        if time.monotonic() >= deadline:
                            raise ValueError("网页读取超时；已有材料仍然保留。")
                        chunks.append(chunk)
                    encoding = response.encoding or "utf-8"
                    return b"".join(chunks).decode(encoding, errors="replace"), clean, content_type
            raise ValueError("网页跳转过多，停止读取。")
    except httpx.TimeoutException:
        raise ValueError("网页读取超时；可以换一个公开来源。") from None
    except (httpx.HTTPError, OSError):
        raise ValueError("暂时无法连接该公开网页；没有生成替代内容。") from None


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.title: list[str] = []
        self.hidden_depth = 0
        self.in_title = False
        self.image_url: str | None = None
        self.published_at: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs = dict(attrs)
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden_depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = attrs.get("property") or attrs.get("name")
            if key in {"og:image", "twitter:image"} and not self.image_url:
                self.image_url = attrs.get("content")
            if key in {"article:published_time", "date", "datePublished"} and not self.published_at:
                self.published_at = attrs.get("content")
        if tag in {"p", "br", "div", "section", "article", "h1", "h2", "h3", "li", "tr"} and not self.hidden_depth:
            self.text.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg", "template"}:
            self.hidden_depth = max(0, self.hidden_depth - 1)
        if tag == "title":
            self.in_title = False
        if tag in {"p", "div", "li", "article"} and not self.hidden_depth:
            self.text.append("\n")

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title.append(data)
        elif not self.hidden_depth:
            self.text.append(data)


def fetch_url(url: str) -> dict:
    """Return a real source, ready for store.add_source; never invent page text."""
    started = time.monotonic()
    raw, final_url, content_type = _download(url)
    parser = _PageParser()
    if "html" in content_type:
        parser.feed(raw)
        title = " ".join("".join(parser.title).split())
        text = "\n".join(line.strip() for line in "".join(parser.text).splitlines() if line.strip())
    else:
        title, text = "", raw.strip()
    truncated = len(text) > MAX_TEXT
    text = text[:MAX_TEXT]
    if len(text.strip()) < 40:
        raise ValueError("页面没有可读取的正文，可能需要登录或由脚本加载。")
    source = {
        "title": (title or urlsplit(final_url).hostname or "公开网页")[:250],
        "url": final_url,
        "excerpt": re.sub(r"\s+", " ", text)[:350],
        "text": text,
        "truncated": truncated,
        "accessed_at": _now(),
        "origin": "public",
    }
    if parser.published_at:
        source["published_at"] = parser.published_at[:100]
    if parser.image_url:
        try:
            remaining = REQUEST_SECONDS - (time.monotonic() - started)
            if remaining <= 0:
                return source
            image_url, _, _ = _public_target(urljoin(final_url, parser.image_url), dns_timeout=min(3, remaining))
            source["image_url"] = image_url
        except ValueError:
            pass
    return source


class _SearchParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[dict] = []
        self.current: dict | None = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and "result__a" in attrs.get("class", ""):
            href = attrs.get("href", "")
            if href.startswith("//"):
                href = "https:" + href
            parsed = urlsplit(href)
            url = parse_qs(parsed.query).get("uddg", [href])[0]
            if urlsplit(url).scheme in {"http", "https"}:
                self.current = {"title": "", "url": url, "excerpt": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["title"] += data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.current["title"] = self.current["title"].strip()
            self.items.append(self.current)
            self.current = None


def search_web(query: str, limit: int = 5) -> dict:
    """Search public indexes; snippets are discovery leads, not read sources."""
    query = str(query).strip()[:500]
    if not query:
        raise ValueError("请提供具体的检索词。")
    limit = max(1, min(int(limit), 8))
    failures: list[str] = []
    chinese_terms = re.findall(r"[\u3400-\u9fff]{2,}", query)
    anchor = max(chinese_terms, key=len) if chinese_terms else None
    search_queries = [query]
    if anchor and anchor != query:
        # RSS sometimes collapses a multi-term Chinese query to one character.
        # A single entity is an explicit broader fallback, never a claim that
        # the requested date/topic filters have been satisfied.
        search_queries.append(anchor)
    try:
        for index_query in search_queries:
            raw, _, _ = _download("https://www.bing.com/search?" + urlencode({"q": index_query, "format": "rss", "mkt": "zh-CN", "setlang": "zh-hans"}), seconds=8)
            root = ET.fromstring(raw)
            items = [{"title": item.findtext("title", ""), "url": item.findtext("link", ""), "excerpt": item.findtext("description", "")[:500]} for item in root.findall(".//item")]
            items = [item for item in items if urlsplit(item["url"]).scheme in {"http", "https"}]
            if anchor and not any(anchor in (item["title"] + item["excerpt"]) for item in items):
                continue
            if items:
                note = "搜索摘要只作线索。请打开相关原文后引用。"
                if index_query != query:
                    note += "原检索没有相关结果；当前是按主体词扩大范围的结果，日期和其他条件未获验证。"
                return {"query": query, "effective_query": index_query, "engine": "Bing", "results": items[:limit], "note": note}
        failures.append("Bing 没有返回可用结果")
    except (ValueError, ET.ParseError):
        failures.append("Bing 暂时不可用")
    try:
        raw, _, _ = _download("https://html.duckduckgo.com/html/?" + urlencode({"q": query}), seconds=10)
        parser = _SearchParser()
        parser.feed(raw)
        if parser.items:
            return {"query": query, "engine": "DuckDuckGo", "results": parser.items[:limit], "note": "搜索结果只作线索。请打开原文后引用。"}
        failures.append("DuckDuckGo 没有返回结果，可能遇到访问限制")
    except ValueError:
        failures.append("DuckDuckGo 暂时不可用")
    return {"query": query, "results": [], "error": "；".join(failures) + "。可以继续使用用户提供的公开链接或已有材料。"}
