#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from reddit_research_agent import (
    build_research_packet,
    collect_research_posts,
    fallback_summary,
    summarize_with_openai,
)


ROOT = Path(__file__).parent
HOST = "127.0.0.1"
PORT = int(os.environ.get("PORT", "8000"))


def read_text_file(name: str) -> bytes:
    return (ROOT / name).read_bytes()


class ResearchHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_bytes(read_text_file("index.html"), "text/html; charset=utf-8")
            return
        if self.path == "/styles.css":
            self._send_bytes(read_text_file("styles.css"), "text/css; charset=utf-8")
            return
        if self.path == "/app.js":
            self._send_bytes(read_text_file("app.js"), "application/javascript; charset=utf-8")
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if self.path != "/api/research":
            self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return

        try:
            payload = self._read_json_body()
            topic = str(payload.get("topic", "")).strip()
            if not topic:
                self._send_json({"error": "Topic is required."}, status=HTTPStatus.BAD_REQUEST)
                return

            api_key = str(payload.get("apiKey", "")).strip() or None
            model = str(payload.get("model", "gpt-5.4-mini")).strip() or "gpt-5.4-mini"
            output_language = str(payload.get("outputLanguage", "English")).strip() or "English"
            subreddit = str(payload.get("subreddit", "")).strip() or None
            limit = _bounded_int(payload.get("limit"), default=6, low=1, high=12)
            comments_per_post = _bounded_int(
                payload.get("commentsPerPost"), default=4, low=0, high=8
            )
            time_filter = _enum_value(
                payload.get("time"),
                {"hour", "day", "week", "month", "year", "all"},
                "year",
            )
            sort = _enum_value(
                payload.get("sort"),
                {"relevance", "hot", "top", "new", "comments"},
                "relevance",
            )
            top_upvoted_only = bool(payload.get("topUpvotedOnly", True))
            use_ai = bool(payload.get("useAi", True))
            discovery_mode = bool(payload.get("discoveryMode", False))

            posts, research_context = collect_research_posts(
                topic,
                subreddit=subreddit,
                limit=limit,
                sort=sort,
                time_filter=time_filter,
                comments_per_post=comments_per_post,
                discovery_mode=discovery_mode,
                top_upvoted_only=top_upvoted_only,
            )
            research_packet = build_research_packet(topic, posts, research_context)

            ai_notice = None
            if use_ai:
                try:
                    summary = summarize_with_openai(
                        topic,
                        posts,
                        model,
                        api_key=api_key,
                        output_language=output_language,
                        research_context=research_context,
                    )
                except RuntimeError as exc:
                    summary = fallback_summary(topic, posts, research_context)
                    ai_notice = str(exc)
            else:
                summary = fallback_summary(topic, posts, research_context)

            self._send_json(
                {
                    "topic": topic,
                    "summary": summary,
                    "aiNotice": ai_notice,
                    "sampleSize": len(posts),
                    "posts": research_packet["posts"],
                    "analysisMode": research_packet["analysis_mode"],
                    "discoveryMode": research_context["discovery_mode"],
                    "discoveryQueries": research_context["queries"],
                }
            )
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_bytes(self, content: bytes, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload).encode("utf-8")
        self._send_bytes(data, "application/json; charset=utf-8", status=status)


def _bounded_int(value: Any, *, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(number, high))


def _enum_value(value: Any, allowed: set[str], default: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in allowed else default


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), ResearchHandler)
    print(f"redditAI running at http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
