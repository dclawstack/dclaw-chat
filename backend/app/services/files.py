import re
import uuid
import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from fastapi import HTTPException

from app.core.ssrf import is_blocked_ip, safe_async_client

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Maximum allowed upload size (25 MiB) and streaming chunk size (1 MiB).
MAX_UPLOAD_SIZE = 25 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024

# Unfurl hardening: bound the URL itself, only fetch HTML, and never read more
# than 64 KiB of the response body (enough for <head> metadata).
MAX_UNFURL_URL_LENGTH = 2048
MAX_UNFURL_BYTES = 64 * 1024
UNFURL_HTML_TYPES = ("text/html", "application/xhtml+xml")

IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}

# Types that may be declared with their real media type when served. SVG is
# excluded: it can carry executable <script> and must never render on the API
# origin. Everything else is forced to application/octet-stream.
INLINE_SAFE_MIMES = (IMAGE_MIMES - {"image/svg+xml"}) | VIDEO_MIMES

_OG_RE = re.compile(
    r'<meta[^>]+(?:property|name)=["\'](?:og:|twitter:)?(\w+)["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>([^<]+)</title>", re.IGNORECASE)
_FAVICON_RE = re.compile(
    r'<link[^>]+rel=["\'](?:shortcut )?icon["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_URL_RE = re.compile(r'https?://[^\s"\'<>]+', re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    return _URL_RE.findall(text)


def _safe_preview_url(candidate: str, page_url: str) -> str:
    """Validate an extracted og:image/favicon URL for client-side rendering.

    Relative URLs are resolved against *page_url*. The result must be an
    absolute http(s) URL (rejects javascript:, data:, etc.) whose host is not
    an internal/blocked IP literal; otherwise return "" so the field is
    dropped from the unfurl result.
    """
    if not candidate:
        return ""
    try:
        resolved = urljoin(page_url, candidate.strip())
        parsed = urlparse(resolved)
    except ValueError:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    if is_blocked_ip(parsed.hostname):
        return ""
    return resolved


class FileService:
    async def save_upload(self, file) -> dict:
        file_id = str(uuid.uuid4())
        original = file.filename or "upload"
        safe_name = re.sub(r"[^\w.\-]", "_", original)
        mime = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

        dest_dir = UPLOAD_DIR / file_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / safe_name

        # Stream to disk in chunks, enforcing a maximum size so a large upload
        # can't exhaust memory or disk.
        size = 0
        with dest_path.open("wb") as out:
            while chunk := await file.read(UPLOAD_CHUNK_SIZE):
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    out.close()
                    dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        413,
                        f"File too large (max {MAX_UPLOAD_SIZE // (1024 * 1024)} MiB)",
                    )
                out.write(chunk)

        return {
            "type": "image" if mime in IMAGE_MIMES else ("video" if mime in VIDEO_MIMES else "file"),
            "id": file_id,
            "name": safe_name,
            "mime_type": mime,
            "size": size,
            "url": f"/api/v1/messaging/files/{file_id}/{safe_name}",
        }

    def file_path(self, file_id: str, filename: str) -> Optional[Path]:
        base = UPLOAD_DIR.resolve()
        target = (base / file_id / filename).resolve()
        # Reject any path that escapes the upload base dir (e.g. '..' traversal
        # or absolute components in file_id / filename).
        if not target.is_relative_to(base):
            return None
        return target if target.exists() else None

    def extract_text(self, file_id: str, filename: str, mime_type: str) -> str:
        """Extract readable text from an uploaded file for AI context (max 8 000 chars)."""
        path = self.file_path(file_id, filename)
        if not path:
            return ""

        try:
            if mime_type == "application/pdf" or filename.lower().endswith(".pdf"):
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                pages = [page.extract_text() or "" for page in reader.pages]
                return "\n".join(pages)[:8_000]

            if mime_type.startswith("text/") or filename.lower().endswith(
                (".txt", ".md", ".csv", ".json", ".py", ".js", ".ts", ".html", ".xml")
            ):
                return path.read_text(errors="ignore")[:8_000]
        except Exception:
            pass

        return ""

    async def unfurl(self, url: str) -> dict:
        base = {"type": "link", "url": url, "title": url, "description": "", "image": "", "favicon": ""}
        if len(url) > MAX_UNFURL_URL_LENGTH or not url.startswith(("http://", "https://")):
            return base
        try:
            # safe_async_client pins the DNS resolution (SSRF guard) and keeps
            # redirects disabled; stream so we can reject by headers before
            # reading the body, and never buffer more than MAX_UNFURL_BYTES.
            async with safe_async_client(timeout=5.0) as client:
                async with client.stream(
                    "GET", url, headers={"User-Agent": "DClaw-Unfurler/1.0"}
                ) as resp:
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    if ctype not in UNFURL_HTML_TYPES:
                        return base
                    clen = resp.headers.get("content-length", "")
                    if clen.isdigit() and int(clen) > MAX_UNFURL_BYTES:
                        return base
                    received = bytearray()
                    async for chunk in resp.aiter_bytes():
                        received += chunk
                        if len(received) >= MAX_UNFURL_BYTES:
                            break  # cap reached — abort the download
                html = bytes(received[:MAX_UNFURL_BYTES]).decode("utf-8", errors="replace")
        except Exception:
            return base

        og: dict[str, str] = {}
        for m in _OG_RE.finditer(html):
            k = m.group(1).lower()
            if k not in og:
                og[k] = m.group(2)

        title_m = _TITLE_RE.search(html)
        title = og.get("title") or (title_m.group(1).strip() if title_m else url)

        fav_m = _FAVICON_RE.search(html)
        favicon = _safe_preview_url(fav_m.group(1) if fav_m else "", url)

        return {
            "type": "link",
            "url": url,
            "title": title,
            "description": og.get("description", ""),
            "image": _safe_preview_url(og.get("image", ""), url),
            "favicon": favicon,
        }


file_service = FileService()
