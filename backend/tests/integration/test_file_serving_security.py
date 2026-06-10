"""serve_file security tests (GAP v2 T1-01 / T1-02).

States probed: anonymous download must be rejected, and served uploads must
never be renderable on the API origin (attachment + nosniff, SVG/HTML forced
to octet-stream).
"""
import io

import pytest

from app.core.deps import get_current_user
from app.main import app


async def _upload(client, name: str, content: bytes, mime: str) -> dict:
    resp = await client.post(
        "/api/v1/messaging/channels/general/upload",
        files={"file": (name, io.BytesIO(content), mime)},
    )
    assert resp.status_code == 200
    return resp.json()


@pytest.mark.asyncio
async def test_anonymous_file_download_rejected(client):
    meta = await _upload(client, "secret.txt", b"top secret", "text/plain")

    original = app.dependency_overrides.pop(get_current_user)
    try:
        resp = await client.get(meta["url"])
    finally:
        app.dependency_overrides[get_current_user] = original
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_svg_is_never_served_inline(client):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    meta = await _upload(client, "evil.svg", svg, "image/svg+xml")

    resp = await client.get(meta["url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/octet-stream")
    assert resp.headers["content-disposition"].startswith("attachment")
    assert resp.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_html_is_forced_to_attachment_octet_stream(client):
    meta = await _upload(client, "evil.html", b"<script>alert(1)</script>", "text/html")

    resp = await client.get(meta["url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/octet-stream")
    assert resp.headers["content-disposition"].startswith("attachment")


@pytest.mark.asyncio
async def test_png_keeps_type_but_still_attachment(client):
    meta = await _upload(client, "pic.png", b"\x89PNG\r\n", "image/png")

    resp = await client.get(meta["url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/png")
    assert resp.headers["content-disposition"].startswith("attachment")
    assert resp.headers["x-content-type-options"] == "nosniff"
