"""
search.py — YouTube search helper using yt-dlp's built-in ytsearch extractor.
No API key required.
"""

from __future__ import annotations

from yt_dlp import YoutubeDL


def _fmt_duration(seconds) -> str:
    """Convert integer seconds to a human-readable mm:ss or h:mm:ss string."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return ""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def search_youtube(query: str, max_results: int = 10) -> list[dict]:
    """
    Search YouTube and return a list of result dicts.

    Each dict contains:
        url          - full watch URL
        title        - video title
        channel      - uploader / channel name
        duration     - duration in seconds (int)
        duration_str - human-readable duration string  e.g. "3:45"
        thumbnail    - URL of the best available thumbnail
        view_count   - integer view count (may be None)

    Args:
        query:       Search terms (same as you'd type into YouTube).
        max_results: How many results to return (default 10, max ~20).

    Returns:
        List of result dicts ordered by YouTube's default relevance ranking.
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,          # don't fetch each video page
        "skip_download": True,
        "ignoreerrors": True,
    }

    search_url = f"ytsearch{max_results}:{query}"

    results: list[dict] = []

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_url, download=False)

    if not info or "entries" not in info:
        return results

    for entry in info["entries"]:
        if entry is None:
            continue

        video_id = entry.get("id") or entry.get("url", "")
        url = (
            entry.get("url")
            if entry.get("url", "").startswith("http")
            else f"https://www.youtube.com/watch?v={video_id}"
        )

        # Pick the best thumbnail available
        thumbnail = ""
        thumbs = entry.get("thumbnails") or []
        if thumbs:
            # yt-dlp lists thumbnails from lowest to highest quality
            thumbnail = thumbs[-1].get("url", "")
        if not thumbnail:
            # Fallback: construct standard YouTube thumbnail URL
            if video_id:
                thumbnail = f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg"

        duration = entry.get("duration")

        results.append(
            {
                "url": url,
                "title": entry.get("title") or "Unknown Title",
                "channel": entry.get("uploader") or entry.get("channel") or "",
                "duration": duration,
                "duration_str": _fmt_duration(duration),
                "thumbnail": thumbnail,
                "view_count": entry.get("view_count"),
            }
        )

    return results


if __name__ == "__main__":
    # Quick smoke-test from the terminal:
    import sys

    q = " ".join(sys.argv[1:]) or "lofi hip hop"
    print(f"Searching for: {q}\n")
    for i, r in enumerate(search_youtube(q, max_results=5), 1):
        print(f"{i}. {r['title']}")
        print(f"   Channel : {r['channel']}")
        print(f"   Duration: {r['duration_str']}")
        print(f"   URL     : {r['url']}")
        print()
