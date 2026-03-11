#!/usr/bin/env python3
"""
app.py — Flask web frontend for spotify_transcript.py
"""

import os
import io
from flask import Flask, render_template, request, jsonify, send_file

from spotify_transcript import get_transcript, extract_episode_id

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/transcript", methods=["POST"])
def api_transcript():
    data = request.get_json(force=True)

    url           = (data.get("url") or "").strip()
    client_id     = (data.get("client_id") or os.getenv("SPOTIFY_CLIENT_ID", "")).strip()
    client_secret = (data.get("client_secret") or os.getenv("SPOTIFY_CLIENT_SECRET", "")).strip()
    fmt           = data.get("format", "txt")

    if not url:
        return jsonify({"error": "Spotify episode URL is required."}), 400
    if not client_id or not client_secret:
        return jsonify({"error": "Spotify Client ID and Client Secret are required."}), 400
    if fmt not in ("txt", "srt", "vtt", "json"):
        return jsonify({"error": "Invalid format. Choose txt, srt, vtt, or json."}), 400

    try:
        result = get_transcript(url, client_id, client_secret, fmt)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except PermissionError as e:
        return jsonify({"error": str(e)}), 401
    except LookupError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        return jsonify({"error": f"Unexpected error: {e}"}), 500


@app.route("/api/download", methods=["POST"])
def api_download():
    data = request.get_json(force=True)

    content = data.get("content", "")
    fmt     = data.get("format", "txt")
    name    = data.get("episode_id", "transcript")

    mime_map = {
        "txt":  "text/plain",
        "srt":  "text/plain",
        "vtt":  "text/vtt",
        "json": "application/json",
    }
    mime = mime_map.get(fmt, "text/plain")
    filename = f"{name}.{fmt}"

    buf = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    return send_file(
        buf,
        mimetype=mime,
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
