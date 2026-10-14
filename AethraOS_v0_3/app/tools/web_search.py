"""Small web and news lookup. No browser control."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any, Dict, List


def search_web(query: str, limit: int = 5) -> Dict[str, Any]:
    query = str(query or "").strip()
    if not query:
        return {"success": False, "verified": False, "error": "A search query is required."}
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "no_html": 1,
        "skip_disambig": 1,
    })
    try:
        with urllib.request.urlopen(url, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}
    results: List[Dict[str, str]] = []
    if data.get("AbstractText"):
        results.append({"title": data.get("Heading") or query, "text": data.get("AbstractText"), "url": data.get("AbstractURL") or ""})
    for topic in (data.get("RelatedTopics") or [])[: max(1, min(int(limit or 5), 6))]:
        if isinstance(topic, dict) and topic.get("Text"):
            results.append({"title": topic.get("Text", "")[:80], "text": topic.get("Text", ""), "url": topic.get("FirstURL") or ""})
    return {
        "success": bool(results),
        "verified": bool(results),
        "query": query,
        "results": results[:limit],
        "message": f"Found {len(results)} result(s) for {query}." if results else "No instant answer. Try a narrower query.",
    }


def news_brief(topic: str = "world", limit: int = 5) -> Dict[str, Any]:
    topic = (topic or "world").strip().lower()
    feeds = {
        "world": "https://feeds.bbci.co.uk/news/world/rss.xml",
        "tech": "https://feeds.bbci.co.uk/news/technology/rss.xml",
        "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    }
    url = feeds.get(topic, feeds["world"])
    try:
        with urllib.request.urlopen(url, timeout=12) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return {"success": False, "verified": False, "error": str(exc)}
    titles = []
    for chunk in raw.split("<title>")[2: max(3, min(int(limit or 5), 8)) + 2]:
        title = chunk.split("</title>")[0].strip()
        if title:
            titles.append(title)
    return {
        "success": bool(titles),
        "verified": bool(titles),
        "topic": topic,
        "headlines": titles,
        "message": " ".join(titles[:5]) if titles else "No headlines.",
    }