#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import textwrap
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    import certifi
except ImportError:
    certifi = None


REDDIT_BASE_URL = "https://www.reddit.com"
OPENAI_BASE_URL = "https://api.openai.com/v1/responses"
USER_AGENT = "reddit-research-agent/0.1 (by u/reddit_research_agent)"
STOP_WORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "get",
    "got",
    "had",
    "has",
    "have",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "like",
    "me",
    "more",
    "my",
    "not",
    "of",
    "on",
    "one",
    "or",
    "our",
    "out",
    "people",
    "really",
    "so",
    "some",
    "than",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "up",
    "us",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "who",
    "will",
    "with",
    "would",
    "why",
    "you",
    "your",
}
GENERIC_TOPIC_WORDS = {
    "best",
    "good",
    "top",
    "great",
    "help",
    "tips",
    "advice",
    "workflow",
    "tool",
    "tools",
    "software",
    "app",
    "apps",
    "solution",
    "solutions",
    "platform",
    "platforms",
    "say",
    "says",
    "said",
    "saying",
    "year",
    "years",
    "thing",
    "things",
    "reddit",
    "user",
    "users",
    "experience",
    "experiences",
    "opinion",
    "opinions",
    "review",
    "reviews",
    "common",
    "history",
    "discussion",
    "discussions",
    "thread",
    "threads",
    "question",
    "questions",
    "challenge",
    "challenges",
    "concern",
    "concerns",
    "perspective",
    "perspectives",
    "controversy",
    "like",
    "likes",
    "dislike",
    "dislikes",
}
KEYWORD_ALIASES = {
    "smartphone": {"smartphone", "smartphones", "iphone", "android", "samsung", "pixel"},
    "phone": {"phone", "phones", "smartphone", "smartphones", "mobile", "iphone", "android", "samsung", "pixel"},
    "laptop": {"laptop", "laptops", "notebook", "macbook", "thinkpad"},
    "car": {"car", "cars", "vehicle", "vehicles", "auto"},
    "movie": {"movie", "movies", "film", "films"},
}
META_NOISE_MARKERS = (
    "acceptable ways to share",
    "not allowed",
    "follow all rules",
    "youtube video description",
    "contact the moderators",
    "i am a bot",
    "read the sidebar",
    "read the rules",
    "automoderator",
)
PAIN_MARKERS = (
    "annoy",
    "frustrat",
    "pain",
    "hate",
    "hard",
    "difficult",
    "problem",
    "issue",
    "broken",
    "waste",
    "manual",
    "tedious",
    "messy",
    "slow",
    "time consuming",
    "can't",
    "cannot",
    "missing",
    "lack",
    "stuck",
)
REQUEST_MARKERS = (
    "i need",
    "need this",
    "looking for",
    "wish there was",
    "does this exist",
    "should exist",
    "any tool",
    "recommend a tool",
)
WORKAROUND_MARKERS = (
    "workaround",
    "hack",
    "manually",
    "copy and paste",
    "spreadsheet",
    "zapier",
    "script",
    "bookmark",
    "multiple tabs",
    "extra steps",
    "glue together",
    "export then import",
)
PAY_MARKERS = (
    "i would pay",
    "would gladly pay",
    "take my money",
    "happy to pay",
    "worth paying",
    "pay for this",
    "paid for",
    "subscription",
)
ROI_MARKERS = (
    "save time",
    "saves me time",
    "save money",
    "saving money",
    "cost me",
    "losing money",
    "hours",
    "billable",
    "revenue",
    "productivity",
    "faster",
    "automation",
)
TIME_LOSS_MARKERS = (
    "waste time",
    "wasting time",
    "takes too long",
    "time consuming",
    "hours",
    "slow",
    "manual",
    "repetitive",
    "again and again",
)
MONEY_LOSS_MARKERS = (
    "lose money",
    "losing money",
    "cost me",
    "costs me",
    "expensive mistake",
    "missed revenue",
    "lost revenue",
    "conversion loss",
    "paying for",
)
DATA_LOSS_MARKERS = (
    "lost data",
    "data loss",
    "lost information",
    "can't find",
    "cannot find",
    "missing information",
    "deleted",
    "overwritten",
    "forgotten",
    "buried",
    "context lost",
)
FREQUENCY_MARKERS = (
    "every day",
    "daily",
    "all the time",
    "constantly",
    "every week",
    "each time",
    "whenever",
    "again and again",
    "repeatedly",
)
URGENCY_MARKERS = (
    "urgent",
    "asap",
    "immediately",
    "need now",
    "right now",
    "can't work",
    "blocked",
    "stuck without",
)
WEAK_SIGNAL_MARKERS = (
    "cool",
    "nice",
    "fun",
    "interesting",
    "neat",
    "looks good",
    "i'll try it",
    "sounds fun",
)
CONVENIENCE_MARKERS = (
    "more convenient",
    "convenient",
    "shortcut",
    "fewer clicks",
    "less clicking",
    "quicker",
    "slightly faster",
    "nice to have",
    "handy",
)
NEGATIVE_SIGNAL_MARKERS = (
    "already do this",
    "just use",
    "built into",
    "native feature",
    "wrong place",
    "wouldn't install",
    "would not install",
    "too niche",
    "tiny edge case",
    "manual installation",
    "why not just use",
)
BROWSER_MARKERS = (
    "browser",
    "chrome",
    "extension",
    "tab",
    "tabs",
    "web",
    "website",
    "page",
    "pages",
    "dashboard",
    "gmail",
    "linkedin",
    "shopify",
    "notion",
    "stripe",
    "reddit",
    "site",
)
PRIVACY_MARKERS = (
    "privacy",
    "tracking",
    "cookie",
    "cookies",
    "ad blocker",
    "consent",
    "data leak",
    "security",
    "spam",
)
B2B_MARKERS = (
    "client",
    "customers",
    "sales",
    "pipeline",
    "ops",
    "workflow",
    "team",
    "manager",
    "agency",
    "business",
    "crm",
    "support",
    "leads",
)
CONSUMER_MARKERS = (
    "shopping",
    "student",
    "personal",
    "home",
    "family",
    "gaming",
    "travel",
)
CROWDED_CATEGORY_MARKERS = (
    "ad blocker",
    "password",
    "coupon",
    "vpn",
    "grammar",
    "translate",
    "screenshot",
    "notes",
    "todo",
    "calendar",
)
COSMETIC_MARKERS = (
    "theme",
    "themes",
    "color",
    "colors",
    "font",
    "fonts",
    "ui tweak",
    "cosmetic",
    "look nicer",
    "visual only",
)
DISCOVERY_INTENT_MARKERS = (
    "find idea",
    "find ideas",
    "discover ideas",
    "opportunity",
    "opportunities",
    "monetizable",
    "profitable",
    "what should i build",
    "browser extension ideas",
    "chrome extension ideas",
    "small saas ideas",
)
OPPORTUNITY_INTENT_MARKERS = DISCOVERY_INTENT_MARKERS + (
    "business idea",
    "business ideas",
    "startup",
    "founder",
    "build next",
    "what should we build",
    "monetization",
    "monetize",
    "pricing",
    "revenue",
    "mrr",
    "arr",
    "subscription",
    "willingness to pay",
)


@dataclass
class RedditComment:
    author: str
    score: int
    body: str


@dataclass
class RedditPost:
    title: str
    subreddit: str
    author: str
    score: int
    num_comments: int
    permalink: str
    url: str
    selftext: str
    created_utc: float
    comments: list[RedditComment]
    matched_queries: list[str]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Research a topic on Reddit and summarize the findings."
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="What you want the agent to research on Reddit.",
    )
    parser.add_argument(
        "--subreddit",
        help="Optional subreddit to search inside, for example 'python' or 'Entrepreneur'.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=6,
        help="How many Reddit posts to research. Default: 6",
    )
    parser.add_argument(
        "--comments-per-post",
        type=int,
        default=4,
        help="How many top comments to inspect per post. Default: 4",
    )
    parser.add_argument(
        "--time",
        default="year",
        choices=["hour", "day", "week", "month", "year", "all"],
        help="Reddit time filter for search. Default: year",
    )
    parser.add_argument(
        "--sort",
        default="relevance",
        choices=["relevance", "hot", "top", "new", "comments"],
        help="Reddit sorting mode. Default: relevance",
    )
    parser.add_argument(
        "--model",
        default="gpt-5.4-mini",
        help="OpenAI model used for summarization. Default: gpt-5.4-mini",
    )
    parser.add_argument(
        "--language",
        default="English",
        help="Desired output language for the final AI-written report. Default: English",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Skip OpenAI summarization and use a local fallback summary instead.",
    )
    parser.add_argument(
        "--discovery",
        action="store_true",
        help="Force discovery mode for broad opportunity hunting across multiple sub-queries.",
    )
    parser.add_argument(
        "--save-json",
        help="Optional path to save the gathered Reddit research as JSON.",
    )
    return parser


def fetch_json(url: str, headers: dict[str, str] | None = None) -> Any:
    request_headers = {"User-Agent": USER_AGENT}
    if headers:
        request_headers.update(headers)

    request = Request(normalize_url(url), headers=request_headers)
    try:
        with urlopen(request, timeout=30, context=build_ssl_context()) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"HTTP {exc.code} while fetching {url}\n{detail[:300]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching {url}: {exc}") from exc


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc.encode("idna").decode("ascii"),
            quote(parts.path, safe="/%"),
            quote(parts.query, safe="=&%+"),
            quote(parts.fragment, safe="%"),
        )
    )


def build_ssl_context() -> ssl.SSLContext:
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def normalize_output_language(value: str | None) -> str:
    lowered = clean_text(value or "").lower()
    if lowered in {"russian", "russkiy", "русский", "ru", "russian language"}:
        return "Russian"
    if lowered in {"georgian", "ქართული", "ka", "kartuli", "georgian language"}:
        return "Georgian"
    return "English"


def general_report_sections_for_language(language: str) -> str:
    if language == "Russian":
        return (
            "1. Сводка данных\n"
            "2. TL;DR\n"
            "3. Ключевые выводы\n"
            "4. Топ постов\n"
            "5. Полезные цитаты\n"
            "6. Источники"
        )
    if language == "Georgian":
        return (
            "1. მონაცემების შეჯამება\n"
            "2. TL;DR\n"
            "3. მთავარი მიგნებები\n"
            "4. საუკეთესო პოსტები\n"
            "5. სასარგებლო ციტატები\n"
            "6. წყაროების შენიშვნები"
        )
    return (
        "1. Data Summary\n"
        "2. TL;DR\n"
        "3. Key Points\n"
        "4. Top Posts\n"
        "5. Useful Quotes\n"
        "6. Source Notes"
    )


def search_reddit(
    topic: str,
    *,
    subreddit: str | None,
    limit: int,
    sort: str,
    time_filter: str,
    comments_per_post: int,
    top_upvoted_only: bool = False,
) -> list[RedditPost]:
    query = quote_plus(topic)
    fetch_limit = min(max(limit * 5, limit), 25)
    effective_sort = "top" if top_upvoted_only else sort
    if subreddit:
        url = (
            f"{REDDIT_BASE_URL}/r/{subreddit}/search.json?q={query}"
            f"&restrict_sr=1&sort={effective_sort}&t={time_filter}&limit={fetch_limit}&raw_json=1"
        )
    else:
        url = (
            f"{REDDIT_BASE_URL}/search.json?q={query}"
            f"&sort={effective_sort}&t={time_filter}&limit={fetch_limit}&raw_json=1"
        )

    payload = fetch_json(url)
    candidates: list[RedditPost] = []
    for item in payload.get("data", {}).get("children", []):
        data = item.get("data", {})
        permalink = data.get("permalink", "")
        candidates.append(
            RedditPost(
            title=clean_text(data.get("title", "")),
            subreddit=data.get("subreddit", ""),
            author=data.get("author", ""),
            score=int(data.get("score", 0)),
            num_comments=int(data.get("num_comments", 0)),
            permalink=permalink,
            url=f"{REDDIT_BASE_URL}{permalink}" if permalink else "",
            selftext=clean_text(data.get("selftext", "")),
            created_utc=float(data.get("created_utc", 0)),
            comments=[],
            matched_queries=[topic],
            )
        )

    if top_upvoted_only:
        candidates.sort(key=lambda post: (post.score, post.num_comments), reverse=True)
        candidates = candidates[: max(limit * 3, limit)]

    posts = rank_posts_for_topic(topic, candidates, limit)
    for post in posts:
        if post.permalink and comments_per_post > 0:
            post.comments = fetch_top_comments(post.permalink, comments_per_post)
            time.sleep(0.35)
    return posts


def rank_posts_for_topic(topic: str, posts: list[RedditPost], limit: int) -> list[RedditPost]:
    keywords = extract_topic_keywords(topic)
    if not keywords:
        return posts[:limit]

    keyword_groups = build_keyword_groups(keywords)
    scored: list[tuple[int, int, int, RedditPost]] = []
    min_matches = 2 if len(keyword_groups) >= 2 else 1
    for post in posts:
        title_tokens = tokenize_for_matching(post.title)
        body_tokens = tokenize_for_matching(post.selftext)
        title_matches = count_keyword_group_matches(title_tokens, keyword_groups)
        body_matches = count_keyword_group_matches(body_tokens, keyword_groups)
        total_matches = title_matches + body_matches
        if len(keyword_groups) >= 2 and title_matches == 0:
            continue
        if total_matches < min_matches:
            continue
        scored.append((title_matches, total_matches, post.score, post))

    if not scored:
        return []

    scored.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    return [post for _, _, _, post in scored[:limit]]


def should_use_discovery_mode(topic: str) -> bool:
    lowered = topic.lower()
    if any(marker in lowered for marker in DISCOVERY_INTENT_MARKERS):
        return True
    broad_terms = sum(
        1 for token in ("browser", "chrome", "extension", "extensions", "saas", "tools")
        if token in lowered
    )
    niche_terms = len(extract_topic_keywords(topic))
    return broad_terms >= 2 and niche_terms <= 3


def determine_analysis_mode(
    topic: str,
    research_context: dict[str, Any] | None = None,
) -> str:
    if research_context and research_context.get("analysis_mode") in {"general", "opportunity"}:
        return str(research_context["analysis_mode"])
    lowered = topic.lower()
    if any(marker in lowered for marker in OPPORTUNITY_INTENT_MARKERS):
        return "opportunity"
    return "general"


def should_use_opportunity_analysis(
    topic: str,
    research_context: dict[str, Any] | None = None,
) -> bool:
    return determine_analysis_mode(topic, research_context) == "opportunity"


def build_discovery_queries(topic: str, max_queries: int = 12) -> list[str]:
    niche = extract_discovery_niche(topic)
    suffix = f" for {niche}" if niche else ""
    queries = [
        f"people complaining about losing tabs and not finding pages again{suffix}",
        f"people saying they waste time doing the same thing in the browser every day{suffix}",
        f"users frustrated with copying data between websites manually{suffix}",
        f"people checking the same websites over and over for updates and getting annoyed{suffix}",
        f'I wish there was a tool that automatically saves pages and links before I lose them{suffix}',
        f"people using hacks or workarounds to organize too many tabs bookmarks and notes{suffix}",
        f"people complaining that exporting or saving content from websites is harder than it should be{suffix}",
        f"users frustrated because browser workflows break and waste time when websites change{suffix}",
        f"people saying they cannot find information they already saw online before{suffix}",
        f"people annoyed by manually checking prices availability or changes across multiple websites{suffix}",
        f"developers complaining about repetitive browser tasks during debugging testing or admin work{suffix}",
        f"analysts or researchers frustrated with collecting information from many tabs and sources manually{suffix}",
        f"people complaining that bookmarks screenshots and notes become useless messes over time{suffix}",
        f"users saying they rely on spreadsheets or copy paste because no browser tool solves it properly{suffix}",
        f"people worried about losing browser sessions research history or important web context{suffix}",
    ]
    return dedupe_queries(queries)[:max_queries]


def build_general_discovery_queries(topic: str, max_queries: int = 10) -> list[str]:
    focus = general_topic_focus(topic)
    queries = [
        topic,
        f"what Reddit users say about {focus}",
        f"{focus} experiences on Reddit",
        f"{focus} opinions Reddit",
        f"why do people like {focus}",
        f"why do people dislike {focus}",
        f"{focus} controversy Reddit",
        f"{focus} common questions Reddit",
        f"{focus} history discussion Reddit",
        f"{focus} challenges discussion Reddit",
    ]
    return dedupe_queries(queries)[:max_queries]


def general_topic_focus(topic: str) -> str:
    keywords = extract_topic_keywords(topic)
    if keywords:
        return " ".join(keywords[:5])
    return clean_text(topic)


def build_general_queries(topic: str, max_queries: int = 8) -> list[str]:
    focus = general_topic_focus(topic)
    queries = [
        topic,
        f"{focus} reddit experience",
        f"{focus} opinion",
        f"{focus} review",
        f"{focus} common problems",
        f"why do people like {focus}",
        f"why do people dislike {focus}",
        f"{focus} advice",
    ]
    return dedupe_queries(queries)[:max_queries]


def build_collection_queries(
    topic: str,
    discovery_mode: bool,
    opportunity_mode: bool,
    max_queries: int = 8,
) -> list[str]:
    if discovery_mode:
        if opportunity_mode:
            return build_discovery_queries(topic, max_queries=max_queries)
        return build_general_discovery_queries(topic, max_queries=max_queries)
    if not opportunity_mode:
        return build_general_queries(topic, max_queries=max_queries)

    focus = discovery_topic_focus(topic)
    queries = [
        topic,
        f"{focus} pain",
        f"{focus} frustration",
        f"{focus} repetitive workflow",
        f"{focus} wasting time",
        f"{focus} losing money",
        f"{focus} losing information",
        f'{focus} "wish there was a tool"',
        f"{focus} workaround",
    ]
    return dedupe_queries(queries)[:max_queries]


def build_fallback_queries(topic: str, discovery_mode: bool, opportunity_mode: bool) -> list[str]:
    focus = discovery_topic_focus(topic)
    base = extract_discovery_niche(topic) or focus
    if discovery_mode:
        if opportunity_mode:
            queries = [
                f"{base} browser pain",
                f"{base} manual task",
                f"{base} repeated problem",
                f"{base} save time",
            ]
        else:
            general_base = general_topic_focus(topic)
            queries = [
                general_base,
                f"{general_base} Reddit thread",
                f"{general_base} perspectives",
                f"{general_base} discussion",
                f"{general_base} concerns",
            ]
    elif not opportunity_mode:
        general_base = general_topic_focus(topic)
        queries = [
            general_base,
            f"{general_base} discussion",
            f"{general_base} pros cons",
            f"{general_base} alternatives",
            f"{general_base} issues",
        ]
    else:
        queries = [
            base,
            f"{base} problem",
            f"{base} manual process",
            f"{base} save time",
        ]
    return dedupe_queries(queries)


def dedupe_queries(queries: list[str]) -> list[str]:
    deduped: list[str] = []
    seen = set()
    for query in queries:
        normalized = clean_text(query).lower()
        if not normalized or normalized in seen:
            continue
        deduped.append(clean_text(query))
        seen.add(normalized)
    return deduped


def extract_discovery_niche(topic: str) -> str:
    lowered = topic.lower()
    cleaned = lowered
    for phrase in (
        "find monetizable",
        "find profitable",
        "browser extension ideas",
        "chrome extension ideas",
        "browser extensions",
        "browser extension",
        "chrome extensions",
        "chrome extension",
        "small saas ideas",
        "saas ideas",
        "opportunities",
        "opportunity",
        "ideas",
        "idea",
        "what should i build",
        "find",
        "discover",
        "monetizable",
        "profitable",
    ):
        cleaned = cleaned.replace(phrase, " ")
    tokens = [
        token
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", cleaned)
        if token not in STOP_WORDS and token not in GENERIC_TOPIC_WORDS
    ]
    return " ".join(tokens[:4]).strip()


def collect_research_posts(
    topic: str,
    *,
    subreddit: str | None,
    limit: int,
    sort: str,
    time_filter: str,
    comments_per_post: int,
    discovery_mode: bool | None = None,
    top_upvoted_only: bool = False,
    analysis_mode: str | None = None,
) -> tuple[list[RedditPost], dict[str, Any]]:
    use_discovery = bool(discovery_mode) or should_use_discovery_mode(topic)
    selected_mode = analysis_mode if analysis_mode in {"general", "opportunity"} else None
    opportunity_mode = selected_mode == "opportunity" if selected_mode else should_use_opportunity_analysis(topic)
    discovery_queries = build_collection_queries(topic, use_discovery, opportunity_mode)
    per_query_limit = max(2, min(4, max(2, limit // 2 if limit > 2 else 2)))
    deduped: dict[str, RedditPost] = {}
    attempted_queries: list[str] = []

    for query in discovery_queries:
        attempted_queries.append(query)
        query_posts = search_reddit(
            query,
            subreddit=subreddit,
            limit=per_query_limit,
            sort=sort,
            time_filter=time_filter,
            comments_per_post=comments_per_post,
            top_upvoted_only=top_upvoted_only,
        )
        for post in query_posts:
            key = post.permalink or post.url
            if not key:
                continue
            if key not in deduped:
                deduped[key] = post
                continue

            existing = deduped[key]
            for matched_query in post.matched_queries:
                if matched_query not in existing.matched_queries:
                    existing.matched_queries.append(matched_query)
            merge_comments(existing, post)

    ranker = rank_discovery_posts if opportunity_mode else rank_general_posts
    posts = ranker(topic, list(deduped.values()))

    quote_snippets = collect_quote_snippets(topic, posts, target=18)
    if len(posts) < max(4, limit) or len(quote_snippets) < 10:
        for query in build_fallback_queries(topic, use_discovery, opportunity_mode):
            if query in attempted_queries:
                continue
            attempted_queries.append(query)
            query_posts = search_reddit(
                query,
                subreddit=subreddit,
                limit=per_query_limit,
                sort=sort,
                time_filter=time_filter,
                comments_per_post=comments_per_post,
                top_upvoted_only=top_upvoted_only,
            )
            for post in query_posts:
                key = post.permalink or post.url
                if not key:
                    continue
                if key not in deduped:
                    deduped[key] = post
                    continue
                existing = deduped[key]
                for matched_query in post.matched_queries:
                    if matched_query not in existing.matched_queries:
                        existing.matched_queries.append(matched_query)
                merge_comments(existing, post)
        posts = ranker(topic, list(deduped.values()))
        quote_snippets = collect_quote_snippets(topic, posts, target=18)

    capped_posts = posts[: min(max(limit * 3, 10), 24)]
    data_summary = build_data_summary(topic, capped_posts, attempted_queries, quote_snippets)
    return capped_posts, {
        "discovery_mode": use_discovery,
        "analysis_mode": selected_mode or ("opportunity" if opportunity_mode else "general"),
        "top_upvoted_only": top_upvoted_only,
        "queries": discovery_queries,
        "attempted_queries": attempted_queries,
        "data_summary": data_summary,
    }


def merge_comments(target: RedditPost, incoming: RedditPost) -> None:
    seen = {comment.body for comment in target.comments}
    for comment in incoming.comments:
        if comment.body in seen:
            continue
        target.comments.append(comment)
        seen.add(comment.body)


def rank_discovery_posts(topic: str, posts: list[RedditPost]) -> list[RedditPost]:
    browser_focused = any(word in topic.lower() for word in ("browser", "chrome", "extension"))
    ranked: list[tuple[float, RedditPost]] = []
    for post in posts:
        text = " ".join(
            [post.title, post.selftext] + [comment.body for comment in post.comments]
        ).lower()
        signals = detect_signals(text)
        has_core_pain = any(
            signals[name] > 0
            for name in ("pain", "request", "workaround", "roi", "time_loss", "money_loss", "data_loss")
        )
        if browser_focused and signals["browser"] == 0:
            continue
        if not has_core_pain:
            continue
        score = (
            len(post.matched_queries) * 2.5
            + min(post.score, 100) / 20
            + min(post.num_comments, 80) / 20
            + signals["pain"] * 1.5
            + signals["request"] * 1.2
            + signals["workaround"] * 1.3
            + signals["roi"] * 1.2
            + signals["time_loss"] * 1.5
            + signals["money_loss"] * 2.0
            + signals["data_loss"] * 2.6
            + signals["browser"] * 1.2
            - signals["weak"] * 1.8
            - signals["cosmetic"] * 2.2
        )
        ranked.append((score, post))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [post for _, post in ranked]


def rank_general_posts(topic: str, posts: list[RedditPost]) -> list[RedditPost]:
    keywords = extract_topic_keywords(topic)
    keyword_groups = build_keyword_groups(keywords)
    query_tokens = set(keywords)
    ranked: list[tuple[float, RedditPost]] = []
    for post in posts:
        text = " ".join(
            [post.title, post.selftext] + [comment.body for comment in post.comments]
        ).lower()
        signals = detect_signals(text)
        tokens = tokenize_for_matching(text)
        overlap = count_keyword_group_matches(tokens, keyword_groups)
        score = (
            len(post.matched_queries) * 2.2
            + min(post.score, 150) / 20
            + min(post.num_comments, 120) / 18
            + overlap * 2.4
            + (1.2 if post.selftext else 0)
            + signals["pain"] * 0.5
            + signals["request"] * 0.5
            + signals["workaround"] * 0.4
            - signals["weak"] * 0.6
        )
        min_overlap = 2 if len(keyword_groups) >= 2 else 1
        if query_tokens and overlap < min_overlap:
            continue
        ranked.append((score, post))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [post for _, post in ranked]


def collect_quote_snippets(topic: str, posts: list[RedditPost], target: int = 18) -> list[str]:
    query_tokens = set(extract_topic_keywords(topic))
    snippets: list[tuple[float, str]] = []
    seen = set()

    for post in posts:
        candidates = [post.title]
        candidates.extend(split_sentences(post.selftext)[:4])
        for comment in post.comments:
            candidates.extend(split_sentences(comment.body)[:2])

        for candidate in candidates:
            cleaned = clean_text(candidate)
            if len(cleaned) < 24:
                continue
            lowered = cleaned.lower()
            if any(marker in lowered for marker in META_NOISE_MARKERS):
                continue
            if cleaned in seen:
                continue
            signals = detect_signals(cleaned)
            tokens = {
                normalize_token(token)
                for token in re.findall(r"[a-z][a-z0-9'-]{2,}", lowered)
                if token not in STOP_WORDS
            }
            overlap = len(tokens & query_tokens)
            score = (
                overlap * 2
                + signals["pain"] * 1.6
                + signals["request"] * 1.3
                + signals["workaround"] * 1.3
                + signals["time_loss"] * 1.7
                + signals["money_loss"] * 1.9
                + signals["data_loss"] * 2.2
                + signals["roi"] * 1.1
                - signals["weak"] * 1.2
                - signals["cosmetic"] * 1.5
            )
            if score <= 0 and overlap == 0:
                continue
            snippets.append((score, truncate(cleaned, 220)))
            seen.add(cleaned)

    snippets.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in snippets[:target]]


def build_data_summary(topic: str, posts: list[RedditPost], attempted_queries: list[str], quotes: list[str]) -> dict[str, Any]:
    return {
        "topic": topic,
        "posts_analyzed": len(posts),
        "comments_analyzed": sum(len(post.comments) for post in posts),
        "quotes_collected": len(quotes),
        "average_score": round(sum(post.score for post in posts) / len(posts), 1) if posts else 0,
        "top_score": max((post.score for post in posts), default=0),
        "queries_attempted": attempted_queries,
        "sample_quotes": quotes[:5],
    }


def fetch_top_comments(permalink: str, comments_per_post: int) -> list[RedditComment]:
    url = (
        f"{REDDIT_BASE_URL}{permalink}.json?limit={comments_per_post}"
        f"&sort=top&raw_json=1"
    )
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2:
        return []

    comment_nodes = payload[1].get("data", {}).get("children", [])
    comments: list[RedditComment] = []
    for node in comment_nodes:
        data = node.get("data", {})
        body = clean_text(data.get("body", ""))
        if not body:
            continue
        comments.append(
            RedditComment(
                author=data.get("author", ""),
                score=int(data.get("score", 0)),
                body=body,
            )
        )
        if len(comments) >= comments_per_post:
            break
    return comments


def clean_text(value: str) -> str:
    text = value.replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", text).strip()


def extract_topic_keywords(topic: str) -> list[str]:
    keywords = []
    for token in re.findall(r"[a-z0-9][a-z0-9'-]{1,}", topic.lower()):
        if token in STOP_WORDS or token in GENERIC_TOPIC_WORDS:
            continue
        if token.isdigit() and len(token) < 4:
            continue
        normalized = normalize_token(token)
        if normalized:
            keywords.append(normalized)
    return list(dict.fromkeys(keywords))


def tokenize_for_matching(text: str) -> set[str]:
    return {
        normalize_token(token)
        for token in re.findall(r"[a-z0-9][a-z0-9'-]{1,}", text.lower())
        if token not in STOP_WORDS and token not in GENERIC_TOPIC_WORDS
    }


def build_keyword_groups(keywords: list[str]) -> list[set[str]]:
    groups: list[set[str]] = []
    for keyword in keywords:
        aliases = KEYWORD_ALIASES.get(keyword, {keyword})
        groups.append({normalize_token(alias) for alias in aliases if normalize_token(alias)})
    return groups


def count_keyword_group_matches(tokens: set[str], keyword_groups: list[set[str]]) -> int:
    return sum(1 for group in keyword_groups if tokens & group)


def normalize_token(token: str) -> str:
    value = token.lower().strip("'")
    if value.endswith("'s"):
        value = value[:-2]
    if value.endswith("ing") and len(value) > 5:
        value = value[:-3]
    if value.endswith("ers") and len(value) > 5:
        value = value[:-1]
    if value.endswith("s") and len(value) > 4:
        value = value[:-1]
    return value


def build_research_packet(
    topic: str,
    posts: list[RedditPost],
    research_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    context = research_context or {
        "discovery_mode": False,
        "analysis_mode": determine_analysis_mode(topic),
        "queries": [topic],
        "attempted_queries": [topic],
        "data_summary": build_data_summary(topic, posts, [topic], collect_quote_snippets(topic, posts, target=12)),
    }
    analysis_mode = determine_analysis_mode(topic, context)
    analysis = analyze_market_opportunities(topic, posts, context) if analysis_mode == "opportunity" else None
    general_view = build_general_research_view(topic, posts, context) if analysis_mode == "general" else None
    return {
        "topic": topic,
        "sample_size": len(posts),
        "posts": [asdict(post) for post in posts],
        "analysis": analysis,
        "general_view": general_view,
        "analysis_mode": analysis_mode,
        "research_context": context,
    }


def build_general_research_view(
    topic: str,
    posts: list[RedditPost],
    research_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    research_context = research_context or {
        "discovery_mode": False,
        "queries": [topic],
        "attempted_queries": [topic],
    }
    data_summary = research_context.get("data_summary") or build_data_summary(
        topic,
        posts,
        research_context.get("attempted_queries", research_context.get("queries", [topic])),
        collect_quote_snippets(topic, posts, target=12),
    )
    query_tokens = set(extract_topic_keywords(topic))
    filtered_keywords = [
        keyword
        for keyword in extract_keywords(posts, 14)
        if normalize_token(keyword) not in query_tokens
    ]
    top_posts = sorted(posts, key=lambda post: (post.score, post.num_comments), reverse=True)[:4]
    top_subreddits = Counter(post.subreddit for post in posts if post.subreddit).most_common(4)
    evidence_units = extract_evidence_units(topic, posts, query_tokens)
    repeated_themes = build_general_repeated_themes(topic, evidence_units, filtered_keywords)
    disagreements = build_general_caveats(posts, filtered_keywords, top_subreddits)
    return {
        "data_summary": data_summary,
        "keywords": filtered_keywords[:8],
        "quotes": collect_quote_snippets(topic, posts, target=8),
        "top_posts": top_posts,
        "top_subreddits": top_subreddits,
        "repeated_themes": repeated_themes,
        "caveats": disagreements,
        "tldr": build_general_tldr(topic, filtered_keywords, top_subreddits, posts),
        "main_findings": build_general_findings(posts, filtered_keywords),
        "source_notes": build_general_source_notes(posts, top_subreddits, research_context),
    }


def build_general_analysis_prompt(
    topic: str,
    posts: list[RedditPost],
    research_context: dict[str, Any],
) -> str:
    view = build_general_research_view(topic, posts, research_context)
    data_summary = view["data_summary"]
    lines = [
        "Goal: produce a short TL;DR summary of Reddit posts that match the user's keywords.",
        f"Topic: {topic}",
        f"Discovery mode: {'ON' if research_context.get('discovery_mode') else 'OFF'}",
        f"Top-upvoted filter: {'ON' if research_context.get('top_upvoted_only') else 'OFF'}",
        "",
        "Data collection summary:",
        f"- Posts analyzed: {data_summary.get('posts_analyzed', len(posts))}",
        f"- Comments analyzed: {data_summary.get('comments_analyzed', sum(len(post.comments) for post in posts))}",
        f"- Quotes collected: {data_summary.get('quotes_collected', 0)}",
        f"- Average upvotes: {data_summary.get('average_score', 0)}",
        f"- Top upvotes seen: {data_summary.get('top_score', 0)}",
        "- Queries attempted:",
    ]
    for query in data_summary.get(
        "queries_attempted",
        research_context.get("attempted_queries", research_context.get("queries", [topic])),
    ):
        lines.append(f"  - {query}")
    if data_summary.get("sample_quotes"):
        lines.append("- Sample quotes:")
        for quote in data_summary["sample_quotes"][:5]:
            lines.append(f'  - "{quote}"')
    if view["keywords"]:
        lines.extend(["", "Quick extracted signals:", f"- Repeated terms: {', '.join(view['keywords'][:8])}"])
    if view["top_subreddits"]:
        lines.append(
            "- Top subreddits: "
            + ", ".join(f"r/{name} ({count})" for name, count in view["top_subreddits"])
        )
    lines.extend(["", "Raw Reddit evidence:"])
    for index, post in enumerate(posts, start=1):
        lines.append(
            f"{index}. r/{post.subreddit} | score={post.score} | comments={post.num_comments}\n"
            f"Title: {post.title}\n"
            f"Post URL: {post.url}\n"
            f"Matched queries: {', '.join(post.matched_queries) or topic}"
        )
        if post.selftext:
            lines.append(f"Post text: {truncate(post.selftext, 600)}")
        for comment_index, comment in enumerate(post.comments, start=1):
            lines.append(
                f"Top comment {comment_index} (score={comment.score}): {truncate(comment.body, 350)}"
            )
        lines.append("")
    return "\n".join(lines).strip()


def build_analysis_prompt(
    topic: str,
    analysis: dict[str, Any],
    posts: list[RedditPost],
    research_context: dict[str, Any],
) -> str:
    if determine_analysis_mode(topic, research_context) == "general":
        return build_general_analysis_prompt(topic, posts, research_context)

    data_summary = research_context.get("data_summary", {})
    lines = [
        "Goal: find monetizable browser extension or lightweight SaaS opportunities from Reddit evidence.",
        f"Topic: {topic}",
        f"Discovery mode: {'ON' if research_context.get('discovery_mode') else 'OFF'}",
        "",
        "Data collection summary:",
        f"- Posts analyzed: {data_summary.get('posts_analyzed', len(posts))}",
        f"- Comments analyzed: {data_summary.get('comments_analyzed', sum(len(post.comments) for post in posts))}",
        f"- Quotes collected: {data_summary.get('quotes_collected', 0)}",
        "- Queries attempted:",
    ]
    for query in data_summary.get("queries_attempted", research_context.get("attempted_queries", research_context.get("queries", [topic]))):
        lines.append(f"  - {query}")
    if data_summary.get("sample_quotes"):
        lines.append("- Sample quotes:")
        for quote in data_summary["sample_quotes"][:5]:
            lines.append(f'  - "{quote}"')
    lines.extend([
        "",
        "Heuristic scoring framework:",
        "- Pain Severity: is this a serious annoyance or broken workflow?",
        "- Frequency: how often does the problem appear to happen?",
        "- Repeat Usage: will people come back regularly if solved?",
        "- Urgency: does the pain need immediate attention?",
        "- Willingness to Pay: do people indicate they would spend money?",
        "- ROI Potential: does it save meaningful time, money, or risk?",
        "- Extension Fit: is Chrome/browser the right product surface?",
        "- Competition Risk: is the space crowded or easy to replace?",
        "",
        "Structured opportunity candidates extracted from Reddit:",
    ])
    if research_context.get("discovery_mode"):
        lines.append("Discovery queries used:")
        for query in research_context.get("queries", []):
            lines.append(f"- {query}")
        lines.append("")
    for index, opportunity in enumerate(analysis["opportunities"], start=1):
        lines.append(
            f"{index}. Problem candidate: {opportunity['problem']}\n"
            f"Audience: {opportunity['who_has_problem']}\n"
            f"Pain type: {opportunity['pain_type']}\n"
            f"Market size: {opportunity['market_size']}\n"
            f"Market scale potential: {opportunity['market_scale_potential']}\n"
            f"Workaround exists: {opportunity['workaround_exists']}\n"
            f"Real payment likelihood: {opportunity['real_payment_likelihood']}\n"
            f"Substitute risk: {opportunity['substitute_risk']}\n"
            f"Price: ${opportunity['expected_monthly_price']}/month | Users: {opportunity['estimated_market_size_users']} | Conversion: {opportunity['realistic_conversion_rate']}% | Revenue potential: ${opportunity['estimated_monthly_revenue_potential']}/month\n"
            f"Solo product filter: {opportunity['solo_product_viability']}\n"
            f"Opportunity score: {opportunity['opportunity_score']} ({opportunity['opportunity_score_numeric']}/5)\n"
            f"Scores: pain={opportunity['pain_severity_score']}, frequency={opportunity['frequency_score']}, "
            f"repeat={opportunity['repeat_usage_score']}, urgency={opportunity['urgency_score']}, "
            f"pay={opportunity['willingness_to_pay_score']}, roi={opportunity['roi_potential_score']}, "
            f"extension_fit={opportunity['extension_fit_score']}, competition_risk={opportunity['competition_risk_score']}\n"
            f"Signals: strong={', '.join(opportunity['strong_signals']) or 'none'} | "
            f"weak={', '.join(opportunity['weak_signals']) or 'none'} | "
            f"negative={', '.join(opportunity['negative_signals']) or 'none'}\n"
            f"Recommended format: {opportunity['recommended_format']}\n"
            f"Business model: {opportunity['best_business_model']}\n"
            "Evidence:\n- "
            + "\n- ".join(opportunity["evidence_from_reddit"])
        )
        lines.append("")

    if not research_context.get("discovery_mode"):
        lines.append("Weak or misleading opportunities flagged by heuristics:")
        if analysis["weak_opportunities"]:
            for weak in analysis["weak_opportunities"]:
                lines.append(
                    f"- {weak['problem']} | score={weak['opportunity_score']} | reason={weak['why_opportunity_score']}"
                )
        else:
            lines.append("- None strongly flagged as weak by heuristics, but still challenge assumptions.")
        lines.append("")
    lines.append("Raw Reddit evidence:")
    for index, post in enumerate(posts, start=1):
        lines.append(
            f"{index}. r/{post.subreddit} | score={post.score} | comments={post.num_comments}\n"
            f"Title: {post.title}\n"
            f"Post URL: {post.url}\n"
            f"Matched queries: {', '.join(post.matched_queries) or topic}"
        )
        if post.selftext:
            lines.append(f"Post text: {truncate(post.selftext, 600)}")
        for comment_index, comment in enumerate(post.comments, start=1):
            lines.append(
                f"Top comment {comment_index} (score={comment.score}): {truncate(comment.body, 350)}"
            )
        lines.append("")
    return "\n".join(lines).strip()


def summarize_with_openai(
    topic: str,
    posts: list[RedditPost],
    model: str,
    api_key: str | None = None,
    output_language: str = "English",
    research_context: dict[str, Any] | None = None,
) -> str:
    api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    research_context = research_context or {
        "discovery_mode": False,
        "analysis_mode": determine_analysis_mode(topic),
        "queries": [topic],
    }
    analysis_mode = determine_analysis_mode(topic, research_context)
    analysis = analyze_market_opportunities(topic, posts, research_context) if analysis_mode == "opportunity" else None
    target_language = normalize_output_language(output_language)
    if analysis_mode == "general":
        general_sections = general_report_sections_for_language(target_language)
        instructions = (
            f"CRITICAL REQUIREMENT: Write the entire final report in {target_language}. "
            f"All section headers, bullets, explanations, and summaries must be in {target_language}. "
            "Do not default back to English except for product names, subreddit names, URLs, and technical identifiers.\n\n"
            "You are a sharp Reddit research analyst. Your job is to answer the user's question using only the supplied Reddit evidence. "
            "Do not turn this into a startup, monetization, or browser-extension opportunity report unless the user explicitly asked for that. "
            "The data collection phase has already been completed for you. Never say the evidence is missing unless the data summary explicitly shows that all collection attempts failed. "
            "Keep product names, subreddit names, URLs, and technical terms unchanged when needed. "
            "Be direct, readable, and specific about what Reddit users are actually saying. Default to a concise TL;DR style instead of a long report.\n\n"
            "Return markdown with these section headers exactly:\n"
            f"{general_sections}\n"
        )
    else:
        instructions = (
        f"CRITICAL REQUIREMENT: Write the entire final report in {target_language}. "
        f"All section headers, bullets, explanations, and summaries must be in {target_language}. "
        "Do not default back to English except for product names, subreddit names, URLs, and technical identifiers.\n\n"
        "You are a senior product research engineer, growth analyst, and monetization strategist. "
        "Your job is not to summarize sentiment. Your job is to rank monetizable product opportunities, "
        "especially browser extensions and lightweight SaaS ideas. Use only the supplied Reddit evidence and "
        "the extracted opportunity candidates. Do not invent facts. The system has already performed the data collection phase for you. "
        "Never complain that Reddit evidence is missing unless the data summary explicitly shows that all collection attempts failed and quotes collected are near zero. "
        "Reject weak ideas directly when they are novelty-driven, "
        "low frequency, low urgency, low willingness to pay, or a poor browser-extension fit. Distinguish between viral interest, "
        "useful interest, and monetizable interest. Prioritize high-cost problems over frequent annoyances. "
        "Scale matters: a good niche tool is not automatically a good business. Optimize for problems that can become real businesses, "
        "not just useful tools.\n\n"
        "When discovery mode is on, you must aggregate the sub-queries and output only the top monetizable opportunities. "
        "Explicitly discard novelty ideas, low urgency problems, and cosmetic preferences.\n\n"
        "Return markdown with these sections exactly when discovery mode is OFF:\n"
        "1. Data Summary\n"
        "2. TL;DR\n"
        "3. Strongest Opportunities\n"
        "4. Weak / Misleading Opportunities\n"
        "5. Key Pain Patterns\n"
        "6. Monetization Insights\n"
        "7. Product Recommendations\n"
        "8. Source Notes\n\n"
        "Return markdown with these sections exactly when discovery mode is ON:\n"
        "1. Data Summary\n"
        "2. TL;DR\n"
        "3. Discovery Queries Used\n"
        "4. Top Opportunities\n"
        "5. Key Pain Patterns\n"
        "6. Monetization Insights\n"
        "7. Product Recommendations\n"
        "8. Source Notes\n\n"
        "Inside Strongest Opportunities, rank 3 to 7 opportunities from best to worst. For each opportunity use this exact field structure:\n"
        "Problem:\nWho has this problem:\nEvidence from Reddit:\nPain Type:\nMarket Size:\nMarket Scale Potential:\nWorkaround Exists:\nReal Payment Likelihood:\nSubstitute Risk:\nExpected Monthly Price ($):\nRealistic Conversion Rate (%):\nEstimated Market Size (users):\nEstimated Monthly Revenue Potential:\nCan this realistically reach $10k/month as a solo product?:\nPain Severity:\nFrequency:\nRepeat Usage:\nUrgency:\n"
        "Willingness to Pay:\nROI Potential:\nExtension Fit:\nCompetition Risk:\nOpportunity Score:\nWhy Opportunity Score:\n"
        "Best Business Model:\nWhy people would pay:\nWhy a browser extension is a good or bad fit:\nRecommended Format:\n"
        "Suggested Product Idea:\nSuggested MVP:\nConfidence:\n\n"
        "For Discovery Queries Used, list the exact sub-queries you used. For Top Opportunities, rank only the strongest opportunities after discarding weak ones."
        "Keep the tone founder-friendly, direct, and practical. Prefer concrete judgments over vague advice. "
        "Keep product names, subreddit names, URLs, and technical terms unchanged when needed."
        )
    payload = {
        "model": model,
        "instructions": instructions,
        "input": build_analysis_prompt(topic, analysis, posts, research_context),
    }
    request = Request(
        OPENAI_BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=90, context=build_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(
            f"OpenAI request failed with HTTP {exc.code}\n{detail[:500]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach OpenAI API: {exc}") from exc

    text = extract_output_text(payload)
    if not text:
        raise RuntimeError("OpenAI returned an empty response.")
    return text.strip()


def extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    fragments: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                text = content.get("text", "")
                if text:
                    fragments.append(text)
    return "\n".join(fragment for fragment in fragments if fragment).strip()


def fallback_summary(
    topic: str,
    posts: list[RedditPost],
    research_context: dict[str, Any] | None = None,
) -> str:
    research_context = research_context or {
        "discovery_mode": False,
        "analysis_mode": determine_analysis_mode(topic),
        "queries": [topic],
    }
    if determine_analysis_mode(topic, research_context) == "general":
        return fallback_general_summary(topic, posts, research_context)

    analysis = analyze_market_opportunities(topic, posts, research_context)
    data_summary = research_context.get("data_summary") or build_data_summary(
        topic,
        posts,
        research_context.get("attempted_queries", research_context.get("queries", [topic])),
        collect_quote_snippets(topic, posts, target=12),
    )
    if not posts:
        lines = [
            "# Data Summary",
            "",
            f"- Posts analyzed: {data_summary['posts_analyzed']}",
            f"- Comments analyzed: {data_summary['comments_analyzed']}",
            f"- Quotes collected: {data_summary['quotes_collected']}",
            "- Queries attempted:",
        ]
        for query in data_summary["queries_attempted"]:
            lines.append(f"- {query}")
        lines.extend(
            [
                "",
                "# TL;DR",
                "",
                f"I ran the data-collection phase for `{topic}` and broadened queries, but Reddit still returned insufficient evidence for a trustworthy monetization analysis.",
                "",
                "# Source Notes",
                "",
                "- All collection attempts were exhausted before analysis.",
            ]
        )
        return "\n".join(lines)

    lines = [
        "# Data Summary",
        "",
        f"- Posts analyzed: {data_summary['posts_analyzed']}",
        f"- Comments analyzed: {data_summary['comments_analyzed']}",
        f"- Quotes collected: {data_summary['quotes_collected']}",
        "- Queries attempted:",
    ]
    for query in data_summary["queries_attempted"]:
        lines.append(f"- {query}")
    if data_summary["sample_quotes"]:
        lines.append("- Sample quotes:")
        for quote in data_summary["sample_quotes"]:
            lines.append(f'- "{quote}"')
    lines.extend([
        "",
        "# TL;DR",
        "",
        analysis["tl_dr"],
        "",
    ])

    if research_context.get("discovery_mode"):
        lines.extend(["# Discovery Queries Used", ""])
        for query in research_context.get("queries", []):
            lines.append(f"- {query}")
        lines.extend(["", "# Top Opportunities", ""])
    else:
        lines.extend(["# Strongest Opportunities", ""])

    if analysis["opportunities"]:
        for index, opportunity in enumerate(analysis["opportunities"][:5], start=1):
            lines.extend(
                [
                    f"## {index}. {opportunity['problem']}",
                    "",
                    f"Problem: {opportunity['problem']}",
                    f"Who has this problem: {opportunity['who_has_problem']}",
                    "Evidence from Reddit:",
                ]
            )
            for evidence in opportunity["evidence_from_reddit"]:
                lines.append(f"- {evidence}")
            lines.extend(
                [
                    f"Pain Type: {opportunity['pain_type']}",
                    f"Market Size: {opportunity['market_size']}",
                    f"Market Scale Potential: {opportunity['market_scale_potential']}",
                    f"Workaround Exists: {opportunity['workaround_exists']}",
                    f"Real Payment Likelihood: {opportunity['real_payment_likelihood']}",
                    f"Substitute Risk: {opportunity['substitute_risk']}",
                    f"Expected Monthly Price ($): {opportunity['expected_monthly_price']}",
                    f"Realistic Conversion Rate (%): {opportunity['realistic_conversion_rate']}",
                    f"Estimated Market Size (users): {opportunity['estimated_market_size_users']}",
                    f"Estimated Monthly Revenue Potential: ${opportunity['estimated_monthly_revenue_potential']}/month",
                    f"Can this realistically reach $10k/month as a solo product?: {opportunity['solo_product_viability']}",
                    f"Pain Severity: {opportunity['pain_severity']}",
                    f"Frequency: {opportunity['frequency']}",
                    f"Repeat Usage: {opportunity['repeat_usage']}",
                    f"Urgency: {opportunity['urgency']}",
                    f"Willingness to Pay: {opportunity['willingness_to_pay']}",
                    f"ROI Potential: {opportunity['roi_potential']}",
                    f"Extension Fit: {opportunity['extension_fit']}",
                    f"Competition Risk: {opportunity['competition_risk']}",
                    f"Opportunity Score: {opportunity['opportunity_score']}",
                    f"Why Opportunity Score: {opportunity['why_opportunity_score']}",
                    f"Best Business Model: {opportunity['best_business_model']}",
                    f"Why people would pay: {opportunity['why_people_would_pay']}",
                    f"Why a browser extension is a good or bad fit: {opportunity['extension_fit_reason']}",
                    f"Recommended Format: {opportunity['recommended_format']}",
                    f"Suggested Product Idea: {opportunity['suggested_product_idea']}",
                    f"Suggested MVP: {opportunity['suggested_mvp']}",
                    f"Confidence: {opportunity['confidence']}",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "No strong opportunities were detected in this sample.",
                "",
            ]
        )

    if not research_context.get("discovery_mode"):
        lines.extend(["# Weak / Misleading Opportunities", ""])
        if analysis["weak_opportunities"]:
            for weak in analysis["weak_opportunities"]:
                lines.append(f"- {weak['problem']}: {weak['why_opportunity_score']}")
        else:
            lines.append("- No clear weak opportunities were isolated, but the sample may still be too thin.")

    lines.extend(["", "# Key Pain Patterns", ""])
    for pattern in analysis["key_pain_patterns"]:
        lines.append(f"- {pattern}")

    lines.extend(["", "# Monetization Insights", ""])
    for insight in analysis["monetization_insights"]:
        lines.append(f"- {insight}")

    lines.extend(["", "# Product Recommendations", ""])
    for recommendation in analysis["product_recommendations"]:
        lines.append(f"- {recommendation}")

    lines.extend(["", "# Source Notes", ""])
    for note in analysis["source_notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines)


def fallback_general_summary(
    topic: str,
    posts: list[RedditPost],
    research_context: dict[str, Any] | None = None,
) -> str:
    research_context = research_context or {
        "discovery_mode": False,
        "queries": [topic],
        "attempted_queries": [topic],
    }
    view = build_general_research_view(topic, posts, research_context)
    data_summary = view["data_summary"]
    if not posts:
        lines = [
            "# Data Summary",
            "",
            f"- Posts analyzed: {data_summary['posts_analyzed']}",
            f"- Comments analyzed: {data_summary['comments_analyzed']}",
            f"- Quotes collected: {data_summary['quotes_collected']}",
            f"- Average upvotes: {data_summary.get('average_score', 0)}",
            f"- Top upvotes seen: {data_summary.get('top_score', 0)}",
            "- Queries attempted:",
        ]
        for query in data_summary["queries_attempted"]:
            lines.append(f"- {query}")
        lines.extend(
            [
                "",
                "# TL;DR",
                "",
                f"I searched Reddit for `{topic}` and broadened the search terms, but the collected evidence is still too thin for a trustworthy summary.",
                "",
                "# Key Points",
                "",
                "- No strong findings yet because the sample is too small.",
                "",
                "# Top Posts",
                "",
                "- No strong Reddit posts were collected.",
                "",
                "# Source Notes",
                "",
                "- Reddit evidence was insufficient after fallback queries.",
            ]
        )
        return "\n".join(lines)

    lines = [
        "# Data Summary",
        "",
        f"- Posts analyzed: {data_summary['posts_analyzed']}",
        f"- Comments analyzed: {data_summary['comments_analyzed']}",
        f"- Quotes collected: {data_summary['quotes_collected']}",
        f"- Average upvotes: {data_summary.get('average_score', 0)}",
        f"- Top upvotes seen: {data_summary.get('top_score', 0)}",
        "- Queries attempted:",
    ]
    for query in data_summary["queries_attempted"]:
        lines.append(f"- {query}")
    if data_summary["sample_quotes"]:
        lines.append("- Sample quotes:")
        for quote in data_summary["sample_quotes"]:
            lines.append(f'- "{quote}"')

    lines.extend(["", "# TL;DR", "", view["tldr"], "", "# Key Points", ""])
    for finding in view["main_findings"]:
        lines.append(f"- {finding}")

    lines.extend(["", "# Top Posts", ""])
    for post in view["top_posts"][:4]:
        lines.append(
            f"- r/{post.subreddit}: {post.title} (score {post.score}, {post.num_comments} comments)"
        )

    lines.extend(["", "# Useful Quotes", ""])
    for quote in view["quotes"][:5]:
        lines.append(f'- "{quote}"')

    lines.extend(["", "# Source Notes", ""])
    for note in view["source_notes"]:
        lines.append(f"- {note}")

    return "\n".join(lines)


def analyze_market_opportunities(
    topic: str,
    posts: list[RedditPost],
    research_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    research_context = research_context or {"discovery_mode": False, "queries": [topic]}
    query_tokens = set(extract_topic_keywords(topic))
    evidence_units = extract_evidence_units(topic, posts, query_tokens)
    clusters = cluster_evidence_units(evidence_units, query_tokens)
    opportunities = [score_cluster(topic, cluster, query_tokens) for cluster in clusters]
    opportunities.sort(
        key=lambda item: (
            item["opportunity_score_numeric"],
            pain_type_priority(item["pain_type"]),
            market_scale_priority(item["market_scale_potential"]),
            item["willingness_to_pay_score"],
            item["real_payment_likelihood_score"],
            item["roi_potential_score"],
            item["repeat_usage_score"],
            market_size_priority(item["market_size"]),
            item["extension_fit_score"],
        ),
        reverse=True,
    )

    if research_context.get("discovery_mode"):
        strong = [
            item
            for item in opportunities
            if item["opportunity_score_numeric"] >= 3.2
            and item["willingness_to_pay_score"] >= 3
            and item["roi_potential_score"] >= 3
            and item["pain_type"] not in {"ANNOYANCE", "CONVENIENCE"}
            and "novelty or lightweight praise" not in item["weak_signals"]
            and item["cosmetic_preference"] is False
            and not item["easy_to_replace"]
            and item["solo_product_viability"] != "good niche tool, weak business"
        ]
        weak = [item for item in opportunities if item not in strong]
    else:
        strong = [item for item in opportunities if item["opportunity_score_numeric"] >= 3.0]
        weak = [item for item in opportunities if item["opportunity_score_numeric"] < 3.0]
    top_subreddits = Counter(post.subreddit for post in posts if post.subreddit).most_common(4)

    monetizable_count = sum(1 for item in opportunities if item["willingness_to_pay_score"] >= 3)
    extension_ready_count = sum(1 for item in opportunities if item["extension_fit_score"] >= 4)
    tl_dr = build_tl_dr(topic, strong, weak, monetizable_count, extension_ready_count, research_context)

    return {
        "tl_dr": tl_dr,
        "opportunities": strong[:7],
        "weak_opportunities": weak[:4],
        "key_pain_patterns": build_key_pain_patterns(strong or opportunities),
        "monetization_insights": build_monetization_insights(strong or opportunities, weak),
        "product_recommendations": build_product_recommendations(strong[:5]),
        "source_notes": build_source_notes(posts, top_subreddits, research_context, len(weak)),
        "evidence_units": len(evidence_units),
    }


def extract_evidence_units(
    topic: str,
    posts: list[RedditPost],
    query_tokens: set[str],
) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    for post in posts:
        title_unit = build_evidence_unit(
            text=post.title,
            post=post,
            kind="title",
            source_score=post.score,
            query_tokens=query_tokens,
        )
        if title_unit:
            units.append(title_unit)

        for sentence in split_sentences(post.selftext)[:6]:
            unit = build_evidence_unit(
                text=sentence,
                post=post,
                kind="post",
                source_score=post.score,
                query_tokens=query_tokens,
            )
            if unit:
                units.append(unit)

        for comment in post.comments:
            if comment.author.lower() == "automoderator":
                continue
            for sentence in split_sentences(comment.body)[:3]:
                unit = build_evidence_unit(
                    text=sentence,
                    post=post,
                    kind="comment",
                    source_score=max(comment.score, 1),
                    query_tokens=query_tokens,
                )
                if unit:
                    units.append(unit)

    units.sort(key=lambda item: item["weight"], reverse=True)
    return units[:60]


def build_evidence_unit(
    *,
    text: str,
    post: RedditPost,
    kind: str,
    source_score: int,
    query_tokens: set[str],
) -> dict[str, Any] | None:
    cleaned = clean_text(text)
    if len(cleaned) < 18:
        return None
    lowered = cleaned.lower()
    if any(marker in lowered for marker in META_NOISE_MARKERS):
        return None

    tokens = {
        normalize_token(token)
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", cleaned.lower())
        if token not in STOP_WORDS
    }
    overlap = len(tokens & query_tokens)
    signals = detect_signals(cleaned)
    signal_total = sum(signals.values())
    interesting = kind == "title" or signal_total > 0 or overlap > 0
    if not interesting:
        return None

    weight = 1 + overlap * 2 + min(source_score, 100) / 25
    if kind == "title":
        weight += 2
    if signals["pain"] or signals["request"] or signals["workaround"]:
        weight += 2
    if signals["pay"] or signals["roi"]:
        weight += 1

    return {
        "text": truncate(cleaned, 220),
        "tokens": tokens,
        "signals": signals,
        "kind": kind,
        "weight": weight,
        "post_title": post.title,
        "subreddit": post.subreddit,
        "url": post.url,
        "post_score": post.score,
    }


def detect_signals(text: str) -> dict[str, int]:
    lowered = text.lower()
    return {
        "pain": count_marker_hits(lowered, PAIN_MARKERS),
        "request": count_marker_hits(lowered, REQUEST_MARKERS),
        "workaround": count_marker_hits(lowered, WORKAROUND_MARKERS),
        "pay": count_marker_hits(lowered, PAY_MARKERS),
        "roi": count_marker_hits(lowered, ROI_MARKERS),
        "time_loss": count_marker_hits(lowered, TIME_LOSS_MARKERS),
        "money_loss": count_marker_hits(lowered, MONEY_LOSS_MARKERS),
        "data_loss": count_marker_hits(lowered, DATA_LOSS_MARKERS),
        "frequency": count_marker_hits(lowered, FREQUENCY_MARKERS),
        "urgency": count_marker_hits(lowered, URGENCY_MARKERS),
        "weak": count_marker_hits(lowered, WEAK_SIGNAL_MARKERS),
        "convenience": count_marker_hits(lowered, CONVENIENCE_MARKERS),
        "negative": count_marker_hits(lowered, NEGATIVE_SIGNAL_MARKERS),
        "browser": count_marker_hits(lowered, BROWSER_MARKERS),
        "privacy": count_marker_hits(lowered, PRIVACY_MARKERS),
        "b2b": count_marker_hits(lowered, B2B_MARKERS),
        "consumer": count_marker_hits(lowered, CONSUMER_MARKERS),
        "crowded": count_marker_hits(lowered, CROWDED_CATEGORY_MARKERS),
        "cosmetic": count_marker_hits(lowered, COSMETIC_MARKERS),
    }


def count_marker_hits(text: str, markers: tuple[str, ...]) -> int:
    return sum(1 for marker in markers if marker in text)


def split_sentences(text: str) -> list[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [clean_text(part) for part in parts if clean_text(part)]


def cluster_evidence_units(
    evidence_units: list[dict[str, Any]],
    query_tokens: set[str],
) -> list[dict[str, Any]]:
    clusters: list[dict[str, Any]] = []
    for unit in evidence_units:
        best_cluster = None
        best_overlap = 0
        for cluster in clusters:
            overlap = len(unit["tokens"] & set(cluster["top_tokens"]))
            if overlap >= 2 and overlap > best_overlap:
                best_cluster = cluster
                best_overlap = overlap
        if best_cluster is None:
            best_cluster = {
                "evidence": [],
                "token_counter": Counter(),
                "signal_totals": defaultdict(int),
                "post_urls": set(),
                "subreddits": Counter(),
                "top_tokens": [],
            }
            clusters.append(best_cluster)

        best_cluster["evidence"].append(unit)
        best_cluster["token_counter"].update(
            token for token in unit["tokens"] if token not in query_tokens and token not in GENERIC_TOPIC_WORDS
        )
        for name, value in unit["signals"].items():
            best_cluster["signal_totals"][name] += value
        best_cluster["post_urls"].add(unit["url"])
        best_cluster["subreddits"].update([unit["subreddit"]])
        best_cluster["top_tokens"] = [
            token for token, _ in best_cluster["token_counter"].most_common(6)
        ]

    clusters = [
        cluster
        for cluster in clusters
        if cluster["evidence"]
        and (
            len(cluster["post_urls"]) >= 2
            or cluster["signal_totals"]["pain"]
            or cluster["signal_totals"]["request"]
            or cluster["signal_totals"]["workaround"]
        )
    ]
    clusters.sort(
        key=lambda cluster: (
            len(cluster["post_urls"]),
            cluster["signal_totals"]["pain"] + cluster["signal_totals"]["request"] + cluster["signal_totals"]["workaround"],
        ),
        reverse=True,
    )
    return clusters[:10]


def score_cluster(topic: str, cluster: dict[str, Any], query_tokens: set[str]) -> dict[str, Any]:
    signals = cluster["signal_totals"]
    evidence = sorted(cluster["evidence"], key=lambda item: item["weight"], reverse=True)[:4]
    unique_posts = len(cluster["post_urls"])
    strongest_text = evidence[0]["text"]
    top_tokens = cluster["top_tokens"][:4] or list(query_tokens)[:4] or ["workflow"]
    pain_type = infer_pain_type(signals)
    market_size = infer_market_size(cluster, signals, unique_posts)
    market_scale_potential = infer_market_scale_potential(cluster, signals, market_size, unique_posts)

    pain = clamp_score(
        1
        + min(2, signals["pain"])
        + (1 if unique_posts >= 2 else 0)
        + (1 if signals["urgency"] else 0)
        + (1 if signals["time_loss"] or signals["money_loss"] else 0)
        + (2 if signals["data_loss"] else 0)
    )
    frequency = clamp_score(1 + (1 if signals["frequency"] else 0) + (1 if signals["workaround"] else 0) + (1 if unique_posts >= 2 else 0) + (1 if signals["browser"] >= 2 else 0))
    repeat_usage = clamp_score(1 + (1 if frequency >= 3 else 0) + (1 if signals["browser"] else 0) + (1 if signals["workaround"] else 0) + (1 if unique_posts >= 2 else 0))
    urgency = clamp_score(1 + min(2, signals["urgency"]) + (1 if signals["pain"] >= 2 else 0) + (1 if "can't" in strongest_text.lower() or "blocked" in strongest_text.lower() else 0))
    willingness = clamp_score(1 + min(2, signals["pay"]) + (1 if signals["roi"] else 0) + (1 if signals["b2b"] else 0) - (1 if signals["weak"] else 0))
    roi = clamp_score(
        1
        + min(2, signals["roi"])
        + (1 if signals["workaround"] else 0)
        + (1 if signals["b2b"] else 0)
        + (1 if signals["privacy"] else 0)
        + (1 if signals["time_loss"] or signals["money_loss"] else 0)
        + (2 if signals["data_loss"] else 0)
    )
    extension_fit = clamp_score(1 + min(2, signals["browser"]) + (1 if signals["workaround"] else 0) + (1 if signals["privacy"] else 0) - (1 if signals["b2b"] and signals["browser"] == 0 else 0))
    substitute_risk_score, workaround_exists, easy_to_replace = evaluate_substitute_risk(signals, extension_fit)
    competition_risk = clamp_score(
        1
        + min(2, signals["crowded"] + signals["negative"])
        + (1 if top_tokens and top_tokens[0] in {"password", "coupon", "vpn", "grammar", "translate"} else 0)
        + (1 if easy_to_replace else 0)
    )
    real_payment_likelihood_score = derive_real_payment_likelihood(
        willingness,
        roi,
        pain_type,
        repeat_usage,
        easy_to_replace,
        signals,
    )
    expected_monthly_price = estimate_monthly_price(signals, pain_type, roi, willingness)
    realistic_conversion_rate = estimate_conversion_rate(
        real_payment_likelihood_score,
        market_scale_potential,
        easy_to_replace,
    )
    estimated_market_size_users = estimate_market_size_users(market_scale_potential, signals)
    estimated_monthly_revenue_potential = int(
        round(expected_monthly_price * estimated_market_size_users * (realistic_conversion_rate / 100))
    )
    solo_product_viability = classify_solo_product_viability(
        estimated_monthly_revenue_potential,
        market_scale_potential,
        willingness,
        roi,
        signals,
    )

    weighted = (
        pain_type_priority(pain_type) * 1.8
        + real_payment_likelihood_score * 1.7
        + roi * 1.5
        + repeat_usage * 1.2
        + market_scale_priority(market_scale_potential) * 1.2
        + market_size_priority(market_size) * 1.0
        + extension_fit * 0.9
        + pain * 0.8
        + urgency * 0.6
        + frequency * 0.3
        - competition_risk * 0.9
        - substitute_risk_score * 1.0
    ) / 7.9
    opportunity_score_numeric = weighted

    if pain_type in {"DATA LOSS", "MONEY LOSS", "TIME LOSS"} and repeat_usage >= 3:
        opportunity_score_numeric += 0.8
    elif roi >= 4:
        opportunity_score_numeric += 0.35

    if market_scale_priority(market_scale_potential) >= 3 and pain_type in {"DATA LOSS", "MONEY LOSS", "TIME LOSS"}:
        opportunity_score_numeric += 0.6

    if willingness < 3 and pain_type in {"ANNOYANCE", "CONVENIENCE"}:
        opportunity_score_numeric -= 1.0
    elif willingness < 3:
        opportunity_score_numeric -= 0.5

    if market_size == "NICHE" and real_payment_likelihood_score < 3 and roi < 4:
        opportunity_score_numeric -= 0.7
    if market_scale_potential == "MICRO" and not (signals["b2b"] and willingness >= 4 and roi >= 4):
        opportunity_score_numeric -= 0.9
    if market_scale_potential == "SMALL" and willingness == 3:
        opportunity_score_numeric -= 0.4
    if easy_to_replace:
        opportunity_score_numeric -= 0.6
    if signals["convenience"]:
        opportunity_score_numeric -= 0.35
    if solo_product_viability == "good niche tool, weak business":
        opportunity_score_numeric -= 0.7

    opportunity_score_numeric = max(1.0, min(5.0, round(opportunity_score_numeric, 1)))

    problem = describe_problem(topic, top_tokens, signals, strongest_text)
    who_has_problem = infer_audience(cluster, signals)
    best_business_model = choose_business_model(willingness, repeat_usage, signals, extension_fit)
    recommended_format = choose_product_format(extension_fit, signals, willingness)
    confidence = confidence_band(unique_posts, len(evidence), signals)

    return {
        "problem": problem,
        "who_has_problem": who_has_problem,
        "evidence_from_reddit": [
            f"{item['text']} ({item['subreddit']})" for item in evidence
        ],
        "cosmetic_preference": bool(signals["cosmetic"]),
        "easy_to_replace": easy_to_replace,
        "pain_type": pain_type,
        "market_size": market_size,
        "market_scale_potential": market_scale_potential,
        "workaround_exists": workaround_exists,
        "real_payment_likelihood_score": real_payment_likelihood_score,
        "real_payment_likelihood": three_level_band(real_payment_likelihood_score),
        "substitute_risk_score": substitute_risk_score,
        "substitute_risk": three_level_band(substitute_risk_score),
        "expected_monthly_price": expected_monthly_price,
        "realistic_conversion_rate": realistic_conversion_rate,
        "estimated_market_size_users": estimated_market_size_users,
        "estimated_monthly_revenue_potential": estimated_monthly_revenue_potential,
        "solo_product_viability": solo_product_viability,
        "pain_severity_score": pain,
        "pain_severity": three_level_band(pain),
        "frequency_score": frequency,
        "frequency": three_level_band(frequency),
        "repeat_usage_score": repeat_usage,
        "repeat_usage": three_level_band(repeat_usage),
        "urgency_score": urgency,
        "urgency": three_level_band(urgency),
        "willingness_to_pay_score": willingness,
        "willingness_to_pay": three_level_band(willingness),
        "roi_potential_score": roi,
        "roi_potential": three_level_band(roi),
        "extension_fit_score": extension_fit,
        "extension_fit": three_level_band(extension_fit),
        "competition_risk_score": competition_risk,
        "competition_risk": three_level_band(competition_risk),
        "opportunity_score_numeric": opportunity_score_numeric,
        "opportunity_score": five_level_band(opportunity_score_numeric),
        "why_opportunity_score": explain_opportunity_score(
            pain,
            frequency,
            repeat_usage,
            urgency,
            willingness,
            roi,
            extension_fit,
            competition_risk,
            pain_type,
            market_size,
            market_scale_potential,
            workaround_exists,
            real_payment_likelihood_score,
            easy_to_replace,
            estimated_monthly_revenue_potential,
            solo_product_viability,
        ),
        "best_business_model": best_business_model,
        "why_people_would_pay": explain_why_people_pay(
            signals,
            willingness,
            roi,
            pain_type,
            real_payment_likelihood_score,
            easy_to_replace,
        ),
        "extension_fit_reason": explain_extension_fit(extension_fit, signals),
        "recommended_format": recommended_format,
        "suggested_product_idea": suggest_product_idea(top_tokens, signals, recommended_format),
        "suggested_mvp": suggest_mvp(top_tokens, signals, recommended_format),
        "confidence": confidence,
        "strong_signals": label_signals(signals, positive=True),
        "weak_signals": label_signals(signals, weak=True),
        "negative_signals": label_signals(signals, negative=True),
    }


def clamp_score(value: int) -> int:
    return max(1, min(5, value))


def three_level_band(value: int) -> str:
    if value <= 2:
        return "LOW"
    if value == 3:
        return "MEDIUM"
    return "HIGH"


def five_level_band(value: float) -> str:
    if value < 1.8:
        return "VERY LOW"
    if value < 2.6:
        return "LOW"
    if value < 3.5:
        return "MEDIUM"
    if value < 4.3:
        return "HIGH"
    return "VERY HIGH"


def pain_type_priority(pain_type: str) -> int:
    mapping = {
        "DATA LOSS": 6,
        "MONEY LOSS": 5,
        "TIME LOSS": 4,
        "WORKFLOW FRICTION": 3,
        "CONVENIENCE": 2,
        "ANNOYANCE": 1,
    }
    return mapping.get(pain_type, 1)


def market_size_priority(market_size: str) -> int:
    mapping = {
        "BROAD": 3,
        "LIMITED": 2,
        "NICHE": 1,
    }
    return mapping.get(market_size, 1)


def market_scale_priority(scale: str) -> int:
    mapping = {
        "LARGE": 4,
        "MEDIUM": 3,
        "SMALL": 2,
        "MICRO": 1,
    }
    return mapping.get(scale, 1)


def infer_market_size(cluster: dict[str, Any], signals: dict[str, int], unique_posts: int) -> str:
    subreddit_count = sum(1 for name, count in cluster["subreddits"].items() if name and count > 0)
    if unique_posts >= 4 or subreddit_count >= 3:
        return "BROAD"
    if signals["b2b"] or signals["consumer"] or unique_posts >= 2 or subreddit_count >= 2:
        return "LIMITED"
    return "NICHE"


def infer_market_scale_potential(
    cluster: dict[str, Any],
    signals: dict[str, int],
    market_size: str,
    unique_posts: int,
) -> str:
    subreddit_count = sum(1 for name, count in cluster["subreddits"].items() if name and count > 0)
    if market_size == "BROAD" and (signals["browser"] or signals["consumer"] or subreddit_count >= 3):
        return "LARGE"
    if market_size == "BROAD":
        return "MEDIUM"
    if market_size == "LIMITED" and (signals["browser"] or signals["consumer"] or unique_posts >= 3):
        return "MEDIUM"
    if market_size == "LIMITED":
        return "SMALL"
    if signals["b2b"] and (signals["pay"] or signals["roi"]):
        return "SMALL"
    return "MICRO"


def evaluate_substitute_risk(signals: dict[str, int], extension_fit: int) -> tuple[int, str, bool]:
    workaround_exists = "NO"
    easy_to_replace = False
    score = 1

    if signals["workaround"] or signals["negative"]:
        workaround_exists = "YES - users already mention manual steps or alternative tools."
        score += 1
    if signals["negative"] or signals["crowded"]:
        easy_to_replace = True
        score += 2
    if extension_fit <= 2:
        easy_to_replace = True
        score += 1
    if signals["browser"] == 0 and signals["b2b"]:
        score += 1

    if workaround_exists == "NO":
        workaround_exists = "NO - the evidence does not show an easy substitute people are happy with."

    return clamp_score(score), workaround_exists, easy_to_replace


def derive_real_payment_likelihood(
    willingness: int,
    roi: int,
    pain_type: str,
    repeat_usage: int,
    easy_to_replace: bool,
    signals: dict[str, int],
) -> int:
    score = willingness
    if pain_type in {"DATA LOSS", "MONEY LOSS"}:
        score += 2
    elif pain_type == "TIME LOSS":
        score += 1
    elif pain_type in {"ANNOYANCE", "CONVENIENCE"}:
        score -= 1

    if roi >= 4:
        score += 1
    if repeat_usage >= 3:
        score += 1
    if signals["workaround"] and not easy_to_replace:
        score += 1
    if easy_to_replace:
        score -= 2
    return clamp_score(score)


def estimate_monthly_price(signals: dict[str, int], pain_type: str, roi: int, willingness: int) -> int:
    if signals["b2b"] and (pain_type in {"MONEY LOSS", "DATA LOSS"} or roi >= 4):
        return 49
    if signals["b2b"] or roi >= 4:
        return 29
    if pain_type in {"DATA LOSS", "MONEY LOSS"}:
        return 19
    if pain_type == "TIME LOSS":
        return 12
    if pain_type == "WORKFLOW FRICTION" and willingness >= 3:
        return 8
    return 5


def estimate_conversion_rate(
    real_payment_likelihood_score: int,
    market_scale_potential: str,
    easy_to_replace: bool,
) -> float:
    base = {
        "MICRO": 4.0,
        "SMALL": 2.5,
        "MEDIUM": 1.5,
        "LARGE": 0.8,
    }[market_scale_potential]
    base += (real_payment_likelihood_score - 3) * 0.5
    if easy_to_replace:
        base -= 0.8
    return round(max(0.3, min(6.0, base)), 1)


def estimate_market_size_users(market_scale_potential: str, signals: dict[str, int]) -> int:
    base = {
        "MICRO": 5_000,
        "SMALL": 50_000,
        "MEDIUM": 300_000,
        "LARGE": 2_000_000,
    }[market_scale_potential]
    if signals["b2b"] and market_scale_potential in {"MEDIUM", "LARGE"}:
        return int(base * 0.35)
    return base


def classify_solo_product_viability(
    estimated_monthly_revenue_potential: int,
    market_scale_potential: str,
    willingness: int,
    roi: int,
    signals: dict[str, int],
) -> str:
    if estimated_monthly_revenue_potential >= 10_000:
        return "yes"
    if market_scale_potential == "MICRO" and not (signals["b2b"] and willingness >= 4 and roi >= 4):
        return "good niche tool, weak business"
    if market_scale_potential == "SMALL" and willingness <= 3:
        return "limited side-project"
    return "no"


def describe_problem(
    topic: str,
    top_tokens: list[str],
    signals: dict[str, int],
    strongest_text: str,
) -> str:
    topic_phrase = discovery_topic_focus(topic)
    token_phrase = ", ".join(top_tokens[:3]) if top_tokens else topic_phrase
    if signals["privacy"]:
        return f"Users want better privacy and on-page control around {topic_phrase}."
    if signals["workaround"]:
        return f"Users rely on manual workarounds around {topic_phrase}, which suggests repetitive friction."
    if signals["roi"] or signals["b2b"]:
        return f"Users are losing time or operational efficiency around {topic_phrase}."
    if signals["request"]:
        return f"Users are explicitly asking for a tool to solve {topic_phrase}."
    if token_phrase != topic_phrase:
        return f"Users repeatedly struggle with {topic_phrase}, especially around {token_phrase}."
    return truncate(strongest_text, 110)


def discovery_topic_focus(topic: str) -> str:
    if should_use_discovery_mode(topic):
        niche = extract_discovery_niche(topic)
        if niche:
            return niche
        if any(word in topic.lower() for word in ("browser", "chrome", "extension")):
            return "browser workflows"
        return "online workflows"
    return topic.strip()


def infer_audience(cluster: dict[str, Any], signals: dict[str, int]) -> str:
    top_subreddits = [name for name, _ in cluster["subreddits"].most_common(3) if name]
    communities = ", ".join(f"r/{name}" for name in top_subreddits) or "the sampled communities"
    if signals["b2b"]:
        return f"Prosumers or operators discussing this in {communities}."
    if signals["consumer"] and not signals["b2b"]:
        return f"Consumer users discussing this in {communities}."
    return f"Reddit users dealing with this workflow in {communities}."


def choose_business_model(
    willingness: int,
    repeat_usage: int,
    signals: dict[str, int],
    extension_fit: int,
) -> str:
    if signals["b2b"] and willingness >= 3:
        return "B2B"
    if signals["privacy"] and extension_fit >= 4:
        return "one-time payment"
    if willingness >= 4 and repeat_usage >= 4:
        return "subscription"
    if extension_fit >= 4:
        return "freemium"
    if signals["roi"]:
        return "subscription"
    return "free"


def choose_product_format(extension_fit: int, signals: dict[str, int], willingness: int) -> str:
    if extension_fit >= 4:
        return "Chrome extension"
    if signals["b2b"] and willingness >= 3:
        return "lightweight SaaS"
    if signals["privacy"]:
        return "Chrome extension"
    if willingness <= 2 and extension_fit <= 2:
        return "not worth building"
    return "web app"


def explain_opportunity_score(
    pain: int,
    frequency: int,
    repeat_usage: int,
    urgency: int,
    willingness: int,
    roi: int,
    extension_fit: int,
    competition_risk: int,
    pain_type: str,
    market_size: str,
    market_scale_potential: str,
    workaround_exists: str,
    real_payment_likelihood_score: int,
    easy_to_replace: bool,
    estimated_monthly_revenue_potential: int,
    solo_product_viability: str,
) -> str:
    positives = []
    negatives = []
    if pain_type in {"DATA LOSS", "MONEY LOSS", "TIME LOSS"}:
        positives.append(f"the core pain is {pain_type.lower()}, which carries real user cost")
    elif pain >= 4:
        positives.append("the pain looks meaningful")
    if repeat_usage >= 4:
        positives.append("the workflow appears recurring enough to support retention")
    if real_payment_likelihood_score >= 4 or roi >= 4:
        positives.append("users could justify paying real money because the ROI is tangible")
    if extension_fit >= 4:
        positives.append("a browser extension fits the workflow naturally")
    if market_size in {"BROAD", "LIMITED"}:
        positives.append(f"the market size looks {market_size.lower()}")
    if market_scale_potential in {"MEDIUM", "LARGE"}:
        positives.append(f"scale potential looks {market_scale_potential.lower()}")
    if estimated_monthly_revenue_potential >= 10_000:
        positives.append("it can plausibly reach $10k/month as a solo product")
    if competition_risk >= 4:
        negatives.append("competition risk looks high")
    if willingness <= 2 and pain_type in {"ANNOYANCE", "CONVENIENCE"}:
        negatives.append("willingness to pay is weak for a low-cost problem, so the opportunity was aggressively downgraded")
    elif willingness <= 2:
        negatives.append("willingness to pay looks weak")
    if extension_fit <= 2:
        negatives.append("browser-extension fit is weak")
    if market_size == "NICHE" and real_payment_likelihood_score < 3 and roi < 4:
        negatives.append("the market looks niche without strong monetization signals")
    if market_scale_potential == "MICRO" and estimated_monthly_revenue_potential < 10_000:
        negatives.append("scale potential looks too small for a meaningful standalone business")
    if market_scale_potential == "SMALL" and real_payment_likelihood_score <= 3:
        negatives.append("this looks more like a side-project than a scalable business")
    if "YES" in workaround_exists:
        negatives.append("users already have visible workarounds")
    if easy_to_replace:
        negatives.append("built-in, free, or manual substitutes can replace it too easily")
    if frequency >= 4 and pain_type in {"ANNOYANCE", "CONVENIENCE"}:
        negatives.append("frequency alone does not overcome the low economic value of the pain")
    if solo_product_viability == "good niche tool, weak business":
        negatives.append("it looks like a good niche tool but a weak business")
    positive_text = ", ".join(positives) or "there is some evidence of real pain"
    negative_text = ", ".join(negatives)
    if negative_text:
        return f"This scores well because {positive_text}, but upside is capped because {negative_text}."
    return f"This scores well because {positive_text}."


def explain_why_people_pay(
    signals: dict[str, int],
    willingness: int,
    roi: int,
    pain_type: str,
    real_payment_likelihood_score: int,
    easy_to_replace: bool,
) -> str:
    if easy_to_replace and real_payment_likelihood_score <= 2:
        return "People are unlikely to pay because the workaround is tolerable and easy substitutes already exist."
    if willingness <= 2 and pain_type in {"ANNOYANCE", "CONVENIENCE"}:
        return "People may like the convenience, but they are unlikely to pay real money instead of tolerating the annoyance."
    if signals["roi"] or roi >= 4 or pain_type in {"DATA LOSS", "MONEY LOSS", "TIME LOSS"}:
        return "People would pay if the tool saves measurable time, reduces manual work, or protects revenue."
    if signals["privacy"]:
        return "People may pay for stronger privacy, less tracking, and less friction on every browsing session."
    return "People would pay only if the product clearly beats the current workaround on cost, speed, or reliability."


def explain_extension_fit(extension_fit: int, signals: dict[str, int]) -> str:
    if extension_fit >= 4:
        return "This is a strong extension fit because the pain happens inside websites, tabs, or repetitive browser workflows."
    if extension_fit == 3:
        return "A browser extension could help, but some value may require a backend or companion web app."
    if signals["b2b"]:
        return "This looks better as a SaaS because the pain likely spans data, teams, or back-office workflows beyond the browser."
    return "Browser-extension fit is weak because the pain is not clearly anchored to an in-browser workflow."


def suggest_product_idea(top_tokens: list[str], signals: dict[str, int], recommended_format: str) -> str:
    token_phrase = ", ".join(top_tokens[:3]) if top_tokens else "this workflow"
    if recommended_format == "not worth building":
        return "Do not build this yet. The problem needs stronger evidence of pain or repeat usage."
    if recommended_format == "Chrome extension" and signals["privacy"]:
        return f"Chrome extension that detects privacy friction around {token_phrase} and applies one-click protections in-page."
    if recommended_format == "Chrome extension":
        return f"Chrome extension that spots {token_phrase} workflows on-page and removes the manual steps with one-click actions."
    if recommended_format == "lightweight SaaS":
        return f"Lightweight SaaS that centralizes {token_phrase}, with a companion browser helper for capture and context."
    return f"Focused web app that streamlines {token_phrase} and handles the repeated task flow end-to-end."


def suggest_mvp(top_tokens: list[str], signals: dict[str, int], recommended_format: str) -> str:
    token_phrase = ", ".join(top_tokens[:2]) if top_tokens else "workflow data"
    if recommended_format == "not worth building":
        return "Validate demand first with a landing page and 10 direct interviews."
    if recommended_format == "Chrome extension":
        return f"Support one narrow site or workflow, capture {token_phrase}, and automate a single repeated action with a visible before/after time save."
    if recommended_format == "lightweight SaaS":
        return f"Handle one customer segment, store one core object around {token_phrase}, and automate one recurring workflow with basic reporting."
    return f"Offer one streamlined workflow around {token_phrase}, plus one lightweight automation or saved template."


def confidence_band(unique_posts: int, evidence_count: int, signals: dict[str, int]) -> str:
    score = unique_posts + evidence_count + min(2, signals["pain"] + signals["request"])
    if score >= 8:
        return "HIGH"
    if score >= 5:
        return "MEDIUM"
    return "LOW"


def label_signals(
    signals: dict[str, int],
    *,
    positive: bool = False,
    weak: bool = False,
    negative: bool = False,
) -> list[str]:
    labels = []
    if positive:
        if signals["request"]:
            labels.append("explicit requests")
        if signals["workaround"]:
            labels.append("manual workaround behavior")
        if signals["pay"]:
            labels.append("payment intent")
        if signals["roi"]:
            labels.append("time or money ROI")
        if signals["frequency"]:
            labels.append("high-frequency usage hints")
        if signals["privacy"]:
            labels.append("privacy/security stakes")
        if signals["time_loss"]:
            labels.append("time loss")
        if signals["money_loss"]:
            labels.append("money loss")
        if signals["data_loss"]:
            labels.append("data loss")
        if signals["convenience"]:
            labels.append("convenience-only benefit")
    if weak and signals["weak"]:
        labels.append("novelty or lightweight praise")
    if negative:
        if signals["negative"]:
            labels.append("easy substitutes mentioned")
        if signals["crowded"]:
            labels.append("crowded category")
    return labels


def build_tl_dr(
    topic: str,
    strong: list[dict[str, Any]],
    weak: list[dict[str, Any]],
    monetizable_count: int,
    extension_ready_count: int,
    research_context: dict[str, Any],
) -> str:
    if not strong:
        return (
            f"`{topic}` gets discussion, but this sample does not show strong monetizable extension opportunities yet. "
            "The visible pains look either too weak, too generic, or better solved elsewhere."
        )
    if research_context.get("discovery_mode"):
        lead = strong[0]
        return (
            f"Discovery mode found {len(strong)} viable opportunities after discarding {len(weak)} low-value angles. "
            f"The best opportunities are driven by {lead['pain_type'].lower()} in recurring workflows, and "
            f"`{topic}` looks {'monetizable' if monetizable_count else 'weakly monetizable'} overall. "
            f"Lead scale verdict: {lead['solo_product_viability']}."
        )
    lead = strong[0]
    return (
        f"`{topic}` looks {'monetizable' if monetizable_count else 'interesting but weakly monetizable'} overall. "
        f"The best opportunities center on {lead['problem'].lower()} "
        f"and {'extension-native workflows' if extension_ready_count else 'a broader SaaS shape'}. "
        f"{len(weak)} weaker angles were deprioritized because they look novelty-driven, low-retention, or easy to replace."
    )


def build_key_pain_patterns(opportunities: list[dict[str, Any]]) -> list[str]:
    patterns = []
    for item in opportunities[:4]:
        if item["solo_product_viability"] == "good niche tool, weak business":
            patterns.append(
                f"{item['problem'].rstrip('.')} is useful, but the scale looks too small for a strong standalone business."
            )
        elif item["extension_fit_score"] >= 4:
            patterns.append(
                f"Repeated browser friction appears around: {item['problem'].rstrip('.')}"
            )
        elif item["best_business_model"] == "B2B":
            patterns.append(
                f"Operational pain shows up when users try to manage this through scattered tools: {item['problem'].rstrip('.')}"
            )
        else:
            patterns.append(item["why_opportunity_score"])
    return patterns or ["The sample did not contain a clear repeated pain pattern."]


def build_monetization_insights(
    strong: list[dict[str, Any]],
    weak: list[dict[str, Any]],
) -> list[str]:
    insights = []
    if any(item["real_payment_likelihood_score"] >= 4 for item in strong):
        insights.append("The strongest opportunities are the ones where users would likely pay real money instead of relying on a workaround.")
    if any(item["roi_potential_score"] >= 4 for item in strong):
        insights.append("Users are most likely to pay when the tool saves repeated time, reduces manual ops, or protects money/privacy.")
    if any(item["extension_fit_score"] >= 4 for item in strong):
        insights.append("Extension monetization looks strongest when the pain happens directly on a website and the value is visible in-session.")
    if any(item["pain_type"] == "DATA LOSS" for item in strong):
        insights.append("Data loss or lost-information pain is the strongest monetization signal because the downside is vivid and recurring.")
    elif any(item["pain_type"] in {"TIME LOSS", "MONEY LOSS"} for item in strong):
        insights.append("Time loss and money loss both strengthen monetization because users can justify paying against a visible cost.")
    if any(item["market_size"] == "NICHE" and item["real_payment_likelihood_score"] < 3 for item in weak):
        insights.append("Niche audiences are only attractive when willingness to pay and ROI are both strong; otherwise they are weak businesses.")
    if any(item["estimated_monthly_revenue_potential"] >= 10_000 for item in strong):
        insights.append("The best candidates can plausibly clear the $10k/month solo-product bar with realistic pricing and conversion assumptions.")
    elif strong:
        insights.append("Several opportunities look useful, but scale and conversion assumptions keep them below the $10k/month solo-product bar.")
    if weak:
        insights.append("Some ideas get attention but weak monetization because the pain is low-stakes, one-off, or easily solved with existing tools.")
    if not insights:
        insights.append("Payment intent is muted in this sample, so validation should focus on interviews before building.")
    return insights


def build_product_recommendations(opportunities: list[dict[str, Any]]) -> list[str]:
    if not opportunities:
        return ["Run narrower topic searches before choosing what to build."]
    return [
        f"{item['recommended_format']}: {item['suggested_product_idea']} ({item['solo_product_viability']})"
        for item in opportunities[:4]
    ]


def infer_pain_type(signals: dict[str, int]) -> str:
    if signals["data_loss"]:
        return "DATA LOSS"
    if signals["money_loss"]:
        return "MONEY LOSS"
    if signals["time_loss"]:
        return "TIME LOSS"
    if signals["convenience"]:
        return "CONVENIENCE"
    if signals["workaround"] or signals["frequency"] or signals["browser"]:
        return "WORKFLOW FRICTION"
    return "ANNOYANCE"


def build_source_notes(
    posts: list[RedditPost],
    top_subreddits: list[tuple[str, int]],
    research_context: dict[str, Any],
    discarded_count: int,
) -> list[str]:
    notes = []
    if research_context.get("discovery_mode"):
        notes.append(
            f"Discovery mode used {len(research_context.get('queries', []))} sub-queries and discarded {discarded_count} weak or low-urgency opportunity clusters."
        )
    if top_subreddits:
        notes.append(
            "Reviewed discussions from "
            + ", ".join(f"r/{name} ({count})" for name, count in top_subreddits)
            + "."
        )
    notes.append(f"Sample size: {len(posts)} Reddit posts plus top comments.")
    if any("selfpromo" in post.subreddit.lower() for post in posts):
        notes.append("The sample may be skewed by self-promotion-heavy communities.")
    notes.append("Reddit skews toward vocal users, so pain severity and willingness to pay should be validated outside Reddit before building.")
    return notes


def build_general_tldr(
    topic: str,
    keywords: list[str],
    top_subreddits: list[tuple[str, int]],
    posts: list[RedditPost],
) -> str:
    if not posts:
        return f"I searched Reddit for `{topic}`, but the collected sample is still too thin for a reliable summary."
    theme_text = ", ".join(keywords[:4]) if keywords else "practical experiences and mixed opinions"
    if top_subreddits:
        communities = ", ".join(f"r/{name}" for name, _ in top_subreddits[:3])
        return (
            f"Top Reddit posts about `{topic}` mostly focus on {theme_text}. "
            f"The strongest signal came from {communities}, and the overall conversation is better read as a quick pattern summary than a single clear consensus."
        )
    return (
        f"Top Reddit posts about `{topic}` mostly focus on {theme_text}. "
        "The sample is useful for a quick TL;DR, but opinions are still mixed and community-specific."
    )


def build_general_findings(posts: list[RedditPost], keywords: list[str]) -> list[str]:
    findings: list[str] = []
    ranked_posts = sorted(posts, key=lambda post: (post.score, post.num_comments), reverse=True)
    for post in ranked_posts[:3]:
        findings.append(
            f"High-upvote post in r/{post.subreddit}: {post.title} (score {post.score})"
        )
    if keywords:
        findings.append(f"Repeated discussion terms include: {', '.join(keywords[:6])}.")
    return findings or ["The sample is too thin to extract strong findings yet."]


def build_general_repeated_themes(
    topic: str,
    evidence_units: list[dict[str, Any]],
    keywords: list[str],
) -> list[str]:
    themes: list[str] = []
    query_tokens = set(extract_topic_keywords(topic))
    seen_tokens: set[str] = set()
    for unit in evidence_units[:12]:
        interesting_tokens = [
            token
            for token in unit["tokens"]
            if token not in query_tokens and token not in GENERIC_TOPIC_WORDS and token not in seen_tokens
        ]
        if interesting_tokens:
            lead = ", ".join(interesting_tokens[:3])
            themes.append(f"Users repeatedly bring up {lead} when discussing this topic.")
            seen_tokens.update(interesting_tokens[:3])
        if len(themes) >= 3:
            break
    if not themes and keywords:
        themes.append(f"Repeated themes cluster around: {', '.join(keywords[:5])}.")
    return themes or ["The sample does not yet show a strong repeated theme."]


def build_general_caveats(
    posts: list[RedditPost],
    keywords: list[str],
    top_subreddits: list[tuple[str, int]],
) -> list[str]:
    caveats: list[str] = []
    if len({post.subreddit for post in posts if post.subreddit}) >= 3:
        caveats.append("Different subreddits frame the topic differently, so sentiment and advice are not perfectly consistent.")
    if any(keyword in {"issue", "problem", "broken", "alternative"} for keyword in keywords):
        caveats.append("A visible chunk of the sample is problem-driven, so the discussion may skew more negative than the average user base.")
    if not caveats and top_subreddits:
        caveats.append(
            "Most evidence comes from a handful of communities, so the takeaways reflect Reddit power users more than the entire market."
        )
    return caveats or ["Reddit is useful for patterns, but it over-represents vocal users and edge-case experiences."]


def build_general_source_notes(
    posts: list[RedditPost],
    top_subreddits: list[tuple[str, int]],
    research_context: dict[str, Any],
) -> list[str]:
    notes: list[str] = []
    if research_context.get("discovery_mode"):
        notes.append(
            f"Discovery mode expanded the topic into {len(research_context.get('queries', []))} Reddit sub-queries before aggregation."
        )
    if top_subreddits:
        notes.append(
            "Reviewed discussions from "
            + ", ".join(f"r/{name} ({count})" for name, count in top_subreddits)
            + "."
        )
    notes.append(f"Sample size: {len(posts)} Reddit posts plus top comments.")
    if research_context.get("top_upvoted_only"):
        notes.append("Results were biased toward the highest-upvoted posts, so this summary favors mainstream or highly visible takes.")
    notes.append("Reddit discussions are directional evidence, not a statistically clean sample of all users.")
    return notes


def extract_keywords(posts: list[RedditPost], limit: int) -> list[str]:
    counter: Counter[str] = Counter()
    for post in posts:
        text = " ".join(
            [post.title, post.selftext] + [comment.body for comment in post.comments]
        ).lower()
        for token in re.findall(r"[a-z][a-z0-9'-]{2,}", text):
            if token in STOP_WORDS or token.startswith("http"):
                continue
            counter[token] += 1
    return [word for word, _ in counter.most_common(limit)]


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def save_json(path: str, payload: dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def print_header(topic: str, posts: list[RedditPost]) -> None:
    print(f"\nReddit Research Agent")
    print(f"Topic: {topic}")
    print(f"Posts reviewed: {len(posts)}")
    print("-" * 72)


def read_topic_from_stdin() -> str:
    try:
        return input("What are you interested in? ").strip()
    except EOFError:
        return ""


def configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    configure_stdio()
    parser = build_parser()
    args = parser.parse_args()
    topic = (args.topic or read_topic_from_stdin()).strip()

    if not topic:
        parser.error("Please provide a topic, for example: python3 reddit_research_agent.py 'best CRM for startups'")

    try:
        posts, research_context = collect_research_posts(
            topic,
            subreddit=args.subreddit,
            limit=max(args.limit, 1),
            sort=args.sort,
            time_filter=args.time,
            comments_per_post=max(args.comments_per_post, 0),
            discovery_mode=args.discovery,
        )
        packet = build_research_packet(topic, posts, research_context)
        if args.save_json:
            save_json(args.save_json, packet)

        print_header(topic, posts)
        if args.no_ai:
            summary = fallback_summary(topic, posts, research_context)
        else:
            try:
                summary = summarize_with_openai(
                    topic,
                    posts,
                    args.model,
                    output_language=args.language,
                    research_context=research_context,
                )
            except RuntimeError as exc:
                summary = (
                    f"_AI summarization was unavailable: {exc}_\n\n"
                    f"{fallback_summary(topic, posts, research_context)}"
                )
        print(summary)
        return 0
    except Exception as exc:
        wrapped = textwrap.fill(str(exc), width=88)
        print(f"Error: {wrapped}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
