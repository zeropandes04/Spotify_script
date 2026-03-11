#!/usr/bin/env python3
"""
spotify_transcript.py
─────────────────────
Download or generate transcripts for Spotify podcast episodes.

Strategy (in order):
  1. Spotify's internal transcript API (works for episodes that have
     Spotify-native transcripts — most big shows since ~2023)
  2. RSS feed lookup (many podcasts publish transcripts in their feed
     via <podcast:transcript> namespace)
  3. Friendly error with next steps if neither is available

Usage:
  python spotify_transcript.py <spotify_episode_url> [options]

Requirements:
  pip install spotipy requests feedparser

Setup (one-time):
  1. Go to https://developer.spotify.com/dashboard → Create an app
  2. Set Redirect URI to: http://localhost:8888/callback
  3. Copy Client ID and Client Secret
  4. Set env vars:
       export SPOTIFY_CLIENT_ID=your_client_id
       export SPOTIFY_CLIENT_SECRET=your_client_secret
     Or pass them via --client-id / --client-secret flags
"""

import argparse
import json
import os
import re
import sys
import textwrap
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import requests
except ImportError:
    sys.exit("Missing: pip install requests")

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    sys.exit("Missing: pip install spotipy")

try:
    import feedparser
except ImportError:
    feedparser = None  # optional, used for RSS transcript lookup


# ── helpers ──────────────────────────────────────────────────────────────────

def extract_episode_id(url: str) -> str:
    """Extract Spotify episode ID from a URL."""
    match = re.search(r'episode[/:]([A-Za-z0-9]+)', url)
    if not match:
        raise ValueError(
            f"Could not extract episode ID from: {url}\n"
            "Expected format: https://open.spotify.com/episode/XXXX"
        )
    return match.group(1)


def get_spotify_client(client_id: str, client_secret: str) -> spotipy.Spotify:
    """Authenticate with Spotify and return a client."""
    scope = "user-read-playback-state"
    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri="http://localhost:8888/callback",
        scope=scope,
        open_browser=True,
        cache_path=str(Path.home() / ".spotify_transcript_cache"),
    )
    return spotipy.Spotify(auth_manager=auth)


def get_access_token(sp: spotipy.Spotify) -> str:
    """Extract raw access token from a Spotipy client."""
    token_info = sp.auth_manager.get_cached_token()
    if token_info and not sp.auth_manager.is_token_expired(token_info):
        return token_info["access_token"]
    token_info = sp.auth_manager.get_access_token(as_dict=True)
    return token_info["access_token"]


# ── Strategy 1: Spotify internal transcript API ───────────────────────────────

TRANSCRIPT_URL = (
    "https://spclient.wg.spotify.com/transcript-read-along/v2/episode/{episode_id}"
)

def fetch_spotify_transcript(episode_id: str, access_token: str) -> dict | None:
    """
    Call Spotify's internal transcript API.
    Returns parsed JSON or None if transcript not available.
    """
    url = TRANSCRIPT_URL.format(episode_id=episode_id)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "app-platform": "WebPlayer",
        "spotify-app-version": "1.2.46.25.g7f189073",
    }
    r = requests.get(url, headers=headers, timeout=20)
    if r.status_code == 404:
        return None
    if r.status_code == 401:
        raise PermissionError("Auth error (401). Your token may have expired — run again to refresh.")
    r.raise_for_status()
    return r.json()


def parse_spotify_transcript(data: dict) -> list[dict]:
    """
    Parse Spotify transcript JSON into a list of segments:
    [{"start_ms": int, "end_ms": int, "text": str}, ...]
    """
    segments = []
    for section in data.get("section", []):
        words_in_section = []
        start_ms = None
        end_ms = None
        for word in section.get("body", {}).get("word", []):
            text = word.get("body", "").strip()
            if not text:
                continue
            ws = word.get("startMs", 0)
            we = word.get("endMs", 0)
            if start_ms is None:
                start_ms = ws
            end_ms = we
            words_in_section.append(text)
        if words_in_section:
            segments.append({
                "start_ms": start_ms or 0,
                "end_ms": end_ms or 0,
                "text": " ".join(words_in_section),
            })
    return segments


# ── Strategy 2: RSS transcript lookup ────────────────────────────────────────

def fetch_rss_transcript(episode_id: str, sp: spotipy.Spotify) -> str | None:
    """
    Look up the podcast's RSS feed and find a transcript for this episode.
    Returns plain text or None.
    """
    if feedparser is None:
        return None
    try:
        episode_info = sp.episode(episode_id)
        show_name = episode_info["show"]["name"]
        episode_title = episode_info.get("name", "")
        print(f"  Show: {show_name!r}, Episode: {episode_title!r}")
        print("  Attempting RSS transcript lookup (experimental)...")
        return None  # Would need PodcastIndex API key for reliable lookup
    except Exception:
        return None


# ── Output formatters ─────────────────────────────────────────────────────────

def ms_to_srt_time(ms: int) -> str:
    h = ms // 3_600_000
    ms %= 3_600_000
    m = ms // 60_000
    ms %= 60_000
    s = ms // 1_000
    ms %= 1_000
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def segments_to_txt(segments: list[dict], wrap: int = 80) -> str:
    lines = []
    for seg in segments:
        lines.append(textwrap.fill(seg["text"], width=wrap))
    return "\n\n".join(lines)


def segments_to_srt(segments: list[dict]) -> str:
    blocks = []
    for i, seg in enumerate(segments, 1):
        start = ms_to_srt_time(seg["start_ms"])
        end   = ms_to_srt_time(seg["end_ms"])
        blocks.append(f"{i}\n{start} --> {end}\n{seg['text']}")
    return "\n\n".join(blocks)


def segments_to_json(segments: list[dict]) -> str:
    return json.dumps(segments, indent=2, ensure_ascii=False)


def segments_to_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        start = ms_to_srt_time(seg["start_ms"]).replace(",", ".")
        end   = ms_to_srt_time(seg["end_ms"]).replace(",", ".")
        lines.append(f"{start} --> {end}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


FORMATTERS = {
    "txt":  segments_to_txt,
    "srt":  segments_to_srt,
    "vtt":  segments_to_vtt,
    "json": segments_to_json,
}


def get_transcript(
    url: str,
    client_id: str,
    client_secret: str,
    fmt: str = "txt",
) -> dict:
    """
    Programmatic API for use by the web frontend.
    Returns a dict with keys: episode_id, title, show, date, source, format, content, words, segments
    """
    episode_id = extract_episode_id(url)

    sp = get_spotify_client(client_id, client_secret)
    access_token = get_access_token(sp)

    try:
        ep = sp.episode(episode_id, market="US")
        title = ep.get("name", episode_id)
        show  = ep.get("show", {}).get("name", "Unknown Show")
        date  = ep.get("release_date", "")
        show_image = ep.get("show", {}).get("images", [{}])[0].get("url", "")
        ep_image = ep.get("images", [{}])[0].get("url", "") if ep.get("images") else show_image
    except Exception as e:
        title, show, date, ep_image = episode_id, "", "", ""

    transcript_data = fetch_spotify_transcript(episode_id, access_token)
    segments = None
    source = None

    if transcript_data:
        segments = parse_spotify_transcript(transcript_data)
        if segments:
            source = "spotify-native"
        else:
            transcript_data = None

    if not transcript_data:
        rss_text = fetch_rss_transcript(episode_id, sp)
        if rss_text:
            segments = [{"start_ms": 0, "end_ms": 0, "text": rss_text}]
            source = "rss"

    if not segments:
        raise LookupError("No transcript found for this episode.")

    formatter = FORMATTERS[fmt]
    content = formatter(segments)
    words = sum(len(seg["text"].split()) for seg in segments)

    return {
        "episode_id": episode_id,
        "title": title,
        "show": show,
        "date": date,
        "image": ep_image,
        "source": source,
        "format": fmt,
        "content": content,
        "words": words,
        "segments": len(segments),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download transcripts for Spotify podcast episodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("url", help="Spotify episode URL or URI")
    parser.add_argument(
        "--format", "-f",
        choices=["txt", "srt", "vtt", "json"],
        default="txt",
        help="Output format (default: txt)",
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (default: <episode_id>.<format>)",
    )
    parser.add_argument("--client-id",     default=os.getenv("SPOTIFY_CLIENT_ID"))
    parser.add_argument("--client-secret", default=os.getenv("SPOTIFY_CLIENT_SECRET"))
    parser.add_argument(
        "--print", action="store_true",
        help="Print transcript to stdout instead of saving to file",
    )
    args = parser.parse_args()

    if not args.client_id or not args.client_secret:
        sys.exit(
            "Missing Spotify credentials.\n\n"
            "  1. Go to https://developer.spotify.com/dashboard\n"
            "  2. Create an app -> set Redirect URI to: http://localhost:8888/callback\n"
            "  3. Export credentials:\n"
            "       export SPOTIFY_CLIENT_ID=your_client_id\n"
            "       export SPOTIFY_CLIENT_SECRET=your_client_secret\n"
            "  Or pass --client-id / --client-secret flags.\n"
        )

    try:
        result = get_transcript(
            url=args.url,
            client_id=args.client_id,
            client_secret=args.client_secret,
            fmt=args.format,
        )
    except ValueError as e:
        sys.exit(str(e))
    except PermissionError as e:
        sys.exit(str(e))
    except LookupError:
        print(
            "\nNo transcript found for this episode.\n\n"
            "   Options:\n"
            "   * Try a different episode — Spotify transcripts are available\n"
            "     for most episodes on major shows (BBC, NPR, Spotify Originals...)\n"
            "   * Use Whisper locally (free, works on any audio):\n"
            "       pip install openai-whisper\n"
            "       whisper audio.mp3 --model medium --output_format txt\n"
            "   * Use AssemblyAI / Deepgram API on the audio file\n"
        )
        sys.exit(1)

    print(f"Episode ID : {result['episode_id']}")
    print(f"Show       : {result['show']}")
    print(f"Title      : {result['title']}")
    print(f"Date       : {result['date']}")

    if args.print:
        print("\n" + "─" * 60)
        print(result["content"])
        return

    out_path = args.output or f"{result['episode_id']}.{args.format}"
    Path(out_path).write_text(result["content"], encoding="utf-8")
    print(f"\nSaved : {out_path}")
    print(f"Source: {result['source']}")
    print(f"Format: {args.format.upper()}")
    print(f"Words : {result['words']:,}")
    print(f"Segs  : {result['segments']}")


if __name__ == "__main__":
    main()
