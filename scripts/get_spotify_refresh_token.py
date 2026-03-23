from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request


AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
PROFILE_URL = "https://api.spotify.com/v1/me"
SCOPES = "user-read-currently-playing user-read-playback-state user-read-recently-played"


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


def exchange_code(client_id: str, client_secret: str, redirect_uri: str, code: str) -> dict[str, object]:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
    ).encode("utf-8")

    status, _, response = http_request(
        TOKEN_URL,
        method="POST",
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=body,
    )

    if status != 200:
        raise RuntimeError(response.decode("utf-8", errors="replace"))

    return json.loads(response.decode("utf-8"))


def get_profile(access_token: str) -> dict[str, object]:
    status, _, response = http_request(
        PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if status != 200:
        raise RuntimeError(response.decode("utf-8", errors="replace"))
    return json.loads(response.decode("utf-8"))


def main() -> int:
    client_id = input("Spotify client id: ").strip()
    client_secret = input("Spotify client secret: ").strip()
    redirect_uri = input("Redirect URI [http://127.0.0.1:8888/callback]: ").strip() or "http://127.0.0.1:8888/callback"

    authorize_query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": SCOPES,
        }
    )
    authorize_url = f"{AUTH_URL}?{authorize_query}"

    print("\n1. Open this URL in your browser and approve access:\n")
    print(authorize_url)
    print("\n2. After Spotify redirects, paste the full callback URL here.\n")

    callback_url = input("Callback URL: ").strip()
    parsed = urllib.parse.urlparse(callback_url)
    code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        print("No authorization code found in callback URL.", file=sys.stderr)
        return 1

    token_payload = exchange_code(client_id, client_secret, redirect_uri, code)
    refresh_token = token_payload.get("refresh_token")
    access_token = token_payload.get("access_token")
    if not refresh_token or not access_token:
        print("Spotify did not return a refresh token.", file=sys.stderr)
        return 1

    profile = get_profile(str(access_token))

    print("\nAdd these GitHub secrets to phumin89/phumin89:\n")
    print(f"SPOTIFY_CLIENT_ID={client_id}")
    print(f"SPOTIFY_CLIENT_SECRET={client_secret}")
    print(f"SPOTIFY_REFRESH_TOKEN={refresh_token}")
    print("\nSpotify user info:\n")
    print(f"display_name={profile.get('display_name')}")
    print(f"user_id={profile.get('id')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
