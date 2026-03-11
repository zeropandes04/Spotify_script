# Spotify Transcript Tool

Download transcripts for Spotify podcast episodes via a web UI or the CLI.

## Setup

```bash
pip install -r requirements.txt
```

Set your Spotify credentials (from [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)):

```bash
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret
```

> **Redirect URI**: when creating the Spotify app, set the Redirect URI to `http://localhost:8888/callback`.

## Web UI

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

## CLI

```bash
python spotify_transcript.py <spotify_episode_url> [options]

Options:
  --format / -f   txt | srt | vtt | json  (default: txt)
  --output / -o   output file path
  --print         print to stdout instead of saving
  --client-id     Spotify Client ID (overrides env var)
  --client-secret Spotify Client Secret (overrides env var)
```

### Examples

```bash
# Save as plain text
python spotify_transcript.py https://open.spotify.com/episode/XXXX

# Print SRT subtitles to stdout
python spotify_transcript.py https://open.spotify.com/episode/XXXX -f srt --print

# Save as JSON with custom output path
python spotify_transcript.py https://open.spotify.com/episode/XXXX -f json -o episode.json
```

## How it works

1. **Spotify native transcript API** — checks Spotify's internal read-along endpoint (works for most major shows since ~2023).
2. **RSS feed lookup** — experimental fallback for podcasts that publish transcripts in their RSS feed via the `<podcast:transcript>` namespace.
3. If neither source has a transcript, the tool explains alternatives (Whisper, AssemblyAI, etc.).
