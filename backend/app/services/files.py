import re
import uuid
import mimetypes
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx

from app.core.ssrf import SSRFError, assert_url_safe

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

IMAGE_MIMES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/svg+xml"}
VIDEO_MIMES = {"video/mp4", "video/webm", "video/ogg"}

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


class FileService:
    async def save_upload(self, file) -> dict:
        file_id = str(uuid.uuid4())
        original = file.filename or "upload"
        safe_name = re.sub(r"[^\w.\-]", "_", original)
        mime = file.content_type or mimetypes.guess_type(safe_name)[0] or "application/octet-stream"

        dest_dir = UPLOAD_DIR / file_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        content = await file.read()
        (dest_dir / safe_name).write_bytes(content)

        return {
            "type": "image" if mime in IMAGE_MIMES else ("video" if mime in VIDEO_MIMES else "file"),
            "id": file_id,
            "name": safe_name,
            "mime_type": mime,
            "size": len(content),
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
        try:
            assert_url_safe(url)
        except SSRFError:
            return base
        try:
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                resp = await client.get(url, headers={"User-Agent": "DClaw-Unfurler/1.0"})
                if "text/html" not in resp.headers.get("content-type", ""):
                    return base
                html = resp.text[:60_000]
        except Exception:
            return base

        og: dict[str, str] = {}
        for m in _OG_RE.finditer(html):
            k = m.group(1).lower()
            if k not in og:
                og[k] = m.group(2)

        title_m = _TITLE_RE.search(html)
        title = og.get("title") or (title_m.group(1).strip() if title_m else url)

        favicon = ""
        fav_m = _FAVICON_RE.search(html)
        if fav_m:
            fav = fav_m.group(1)
            if fav.startswith("/"):
                parsed = urlparse(url)
                fav = f"{parsed.scheme}://{parsed.netloc}{fav}"
            favicon = fav

        return {
            "type": "link",
            "url": url,
            "title": title,
            "description": og.get("description", ""),
            "image": og.get("image", ""),
            "favicon": favicon,
        }


file_service = FileService()
