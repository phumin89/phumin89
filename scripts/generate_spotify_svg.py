from __future__ import annotations

import base64
import html
import json
import os
import random
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "assets" / "spotify.svg"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"
SPOTIFY_CURRENT_URL = "https://api.spotify.com/v1/me/player/currently-playing"
SPOTIFY_RECENT_URL = "https://api.spotify.com/v1/me/player/recently-played?limit=1"


def http_request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, data: bytes | None = None) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response_headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, response_headers, response.read()
    except urllib.error.HTTPError as error:
        response_headers = {key.lower(): value for key, value in error.headers.items()}
        return error.code, response_headers, error.read()


def fit_title(text: str) -> tuple[str, int]:
    if len(text) <= 26:
        return text, 36
    if len(text) <= 34:
        return text, 32
    if len(text) <= 46:
        return text, 28
    return text[:43].rstrip() + "...", 25


def fit_subtitle(text: str) -> tuple[str, int]:
    if len(text) <= 34:
        return text, 22
    if len(text) <= 52:
        return text, 20
    return text[:49].rstrip() + "...", 18


def pick_image_url(images: list[dict[str, object]]) -> str | None:
    if not images:
        return None
    ordered = sorted(images, key=lambda item: int(item.get("width") or 0) or 9999)
    return str(ordered[0].get("url"))


def fetch_image_data_uri(image_url: str | None) -> str | None:
    if not image_url:
        return None

    status, headers, body = http_request(image_url)
    if status != 200 or not body:
        return None

    content_type = headers.get("content-type", "image/jpeg")
    encoded = base64.b64encode(body).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> str:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
    ).encode("utf-8")

    status, _, response_body = http_request(
        SPOTIFY_TOKEN_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=body,
    )

    if status != 200:
        raise RuntimeError(f"Unable to refresh Spotify token ({status}): {response_body.decode('utf-8', errors='replace')}")

    payload = json.loads(response_body.decode("utf-8"))
    return payload["access_token"]


def spotify_get(access_token: str, url: str) -> tuple[int, dict[str, object] | None]:
    status, _, body = http_request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )
    if status == 204:
        return status, None
    if status >= 400:
        raise RuntimeError(f"Spotify API request failed ({status}) for {url}: {body.decode('utf-8', errors='replace')}")
    if not body:
        return status, None
    return status, json.loads(body.decode("utf-8"))


def load_spotify_data() -> dict[str, object] | None:
    client_id = os.getenv("SPOTIFY_CLIENT_ID", "").strip()
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "").strip()
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN", "").strip()

    if not client_id or not client_secret or not refresh_token:
        return None

    access_token = refresh_access_token(client_id, client_secret, refresh_token)
    _, me = spotify_get(access_token, SPOTIFY_ME_URL)
    current_status, current = spotify_get(access_token, SPOTIFY_CURRENT_URL)

    if current_status == 200 and current and current.get("item"):
        track = current["item"]
        return {
            "display_name": (me or {}).get("display_name") or "mi.nie",
            "title": track.get("name") or "Unknown track",
            "artists": ", ".join(artist.get("name", "") for artist in track.get("artists", []) if artist.get("name")) or "Unknown artist",
            "album": (track.get("album") or {}).get("name") or "Unknown album",
            "image_url": pick_image_url((track.get("album") or {}).get("images") or []),
            "status": "LIVE NOW",
            "status_fill": "#1DB954",
            "track_url": (track.get("external_urls") or {}).get("spotify", ""),
            "seed": track.get("id") or track.get("name") or "spotify-live",
        }

    _, recent = spotify_get(access_token, SPOTIFY_RECENT_URL)
    items = (recent or {}).get("items") or []
    if items:
        track = (items[0] or {}).get("track") or {}
        return {
            "display_name": (me or {}).get("display_name") or "mi.nie",
            "title": track.get("name") or "Recently played",
            "artists": ", ".join(artist.get("name", "") for artist in track.get("artists", []) if artist.get("name")) or "Unknown artist",
            "album": (track.get("album") or {}).get("name") or "Unknown album",
            "image_url": pick_image_url((track.get("album") or {}).get("images") or []),
            "status": "RECENTLY PLAYED",
            "status_fill": "#457B9D",
            "track_url": (track.get("external_urls") or {}).get("spotify", ""),
            "seed": track.get("id") or track.get("name") or "spotify-recent",
        }

    return {
        "display_name": (me or {}).get("display_name") or "mi.nie",
        "title": "Nothing playing right now",
        "artists": "Open Spotify and this card will wake up",
        "album": "Spotify standby",
        "image_url": None,
        "status": "STANDBY",
        "status_fill": "#9D9B95",
        "track_url": "",
        "seed": "spotify-standby",
    }


def make_bars(seed: str) -> str:
    rng = random.Random(seed)
    x = 258
    base_y = 238
    bars: list[str] = []
    previous = 18
    for _ in range(66):
        height = rng.randint(10, 30)
        height = int((previous * 0.55) + (height * 0.45))
        previous = height
        y = base_y - height
        bars.append(f'<rect x="{x}" y="{y}" width="6" height="{height}" rx="3"/>')
        x += 10
    return "\n    ".join(bars)


def render_svg(data: dict[str, object] | None) -> str:
    if data is None:
        data = {
            "display_name": "mi.nie",
            "title": "waiting for the first track",
            "artists": "drop your spotify secrets and this card goes live",
            "album": "Spotify setup",
            "image_url": None,
            "status": "SETUP",
            "status_fill": "#1D3557",
            "track_url": "",
            "seed": "spotify-setup",
        }

    title, title_size = fit_title(str(data["title"]))
    artists, subtitle_size = fit_subtitle(str(data["artists"]))
    album = html.escape(str(data["album"]).upper()[:26])
    status = html.escape(str(data["status"]))
    status_fill = html.escape(str(data["status_fill"]))
    image_data_uri = fetch_image_data_uri(str(data.get("image_url") or "")) or ""
    image_markup = ""
    if image_data_uri:
        image_markup = f'<image href="{image_data_uri}" x="72" y="118" width="126" height="126" preserveAspectRatio="xMidYMid slice" clip-path="url(#album-cover)"/>'

    bars_markup = make_bars(str(data["seed"]))
    title_text = html.escape(title)
    artists_text = html.escape(artists)

    return f"""<svg width="1200" height="280" viewBox="0 0 1200 280" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc">
  <title id="title">Spotify Playing</title>
  <desc id="desc">Custom Spotify playing card for mi.nie.</desc>
  <defs>
    <filter id="shadow" x="0" y="0" width="1200" height="280" filterUnits="userSpaceOnUse" color-interpolation-filters="sRGB">
      <feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#000000" flood-opacity="0.14"/>
    </filter>
    <linearGradient id="bars" x1="258" y1="0" x2="918" y2="0" gradientUnits="userSpaceOnUse">
      <stop offset="0%" stop-color="#A7F3B0"/>
      <stop offset="100%" stop-color="#1DB954"/>
    </linearGradient>
    <clipPath id="album-cover">
      <rect x="72" y="118" width="126" height="126" rx="3"/>
    </clipPath>
  </defs>

  <g filter="url(#shadow)">
    <rect x="34" y="20" width="1132" height="220" rx="4" fill="#FBFBF9"/>
  </g>

  <g stroke="#151515" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
    <path d="M72 67C72 48.22 87.22 33 106 33C124.78 33 140 48.22 140 67"/>
    <rect x="67" y="60" width="13" height="31" rx="6.5" fill="#FBFBF9"/>
    <rect x="132" y="60" width="13" height="31" rx="6.5" fill="#FBFBF9"/>
  </g>

  <text x="166" y="68" fill="#151515" font-size="30" font-weight="700" font-family="Segoe UI, Arial, sans-serif">Spotify Playing</text>
  <line x1="72" y1="90" x2="1128" y2="90" stroke="#DDDCD6" stroke-width="1"/>

  <text x="72" y="110" fill="#A3A09A" font-size="12" font-weight="700" font-family="Segoe UI, Arial, sans-serif" letter-spacing="3">{album}</text>
  <rect x="72" y="118" width="126" height="126" rx="3" fill="#F0EFE8" stroke="#E2E0D8"/>
  {image_markup}

  <rect x="938" y="42" width="146" height="30" rx="15" fill="{status_fill}"/>
  <circle cx="960" cy="57" r="5" fill="#FBFBF9"/>
  <text x="976" y="62" fill="#FBFBF9" font-size="14" font-weight="700" font-family="Segoe UI, Arial, sans-serif">{status}</text>

  <text x="258" y="150" fill="#151515" font-size="{title_size}" font-weight="500" font-family="Segoe UI, Arial, sans-serif">{title_text}</text>
  <text x="258" y="188" fill="#9D9B95" font-size="{subtitle_size}" font-weight="400" font-family="Segoe UI, Arial, sans-serif">{artists_text}</text>

  <g fill="url(#bars)">
    {bars_markup}
  </g>
</svg>
"""


def main() -> int:
    try:
        spotify_data = load_spotify_data()
        OUTPUT_PATH.write_text(render_svg(spotify_data), encoding="utf-8")
        return 0
    except Exception as error:
        fallback = {
            "display_name": "mi.nie",
            "title": "spotify setup hit a snag",
            "artists": str(error),
            "album": "Spotify setup",
            "image_url": None,
            "status": "ERROR",
            "status_fill": "#E63946",
            "track_url": "",
            "seed": "spotify-error",
        }
        OUTPUT_PATH.write_text(render_svg(fallback), encoding="utf-8")
        print(f"spotify card fallback written: {error}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
