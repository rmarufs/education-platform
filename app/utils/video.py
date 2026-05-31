from urllib.parse import parse_qs, unquote, urlparse


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def _clean_video_id(value: str | None) -> str | None:
    if not value:
        return None
    clean = unquote(value).strip()
    if not clean:
        return None
    for separator in ("?", "&", "/", "#"):
        clean = clean.partition(separator)[0]
    return clean or None


def extract_youtube_video_id(url: str | None) -> str | None:
    if not url:
        return None

    raw_url = url.strip()
    if not raw_url:
        return None

    parsed = urlparse(raw_url)
    if not parsed.netloc:
        parsed = urlparse(f"https://{raw_url}")

    host = parsed.netloc.lower()
    if host.startswith("www."):
        normalized_host = host[4:]
    else:
        normalized_host = host

    if normalized_host not in YOUTUBE_HOSTS:
        return None

    path_parts = [part for part in parsed.path.split("/") if part]

    if normalized_host == "youtu.be":
        return _clean_video_id(path_parts[0] if path_parts else None)

    if path_parts and path_parts[0] == "watch":
        values = parse_qs(parsed.query).get("v")
        return _clean_video_id(values[0] if values else None)

    if len(path_parts) >= 2 and path_parts[0] in {"embed", "shorts", "live"}:
        return _clean_video_id(path_parts[1])

    return None
