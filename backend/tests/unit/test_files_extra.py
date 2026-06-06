import io

import httpx
import pytest

from app.services.files import (
    FileService,
    extract_urls,
    IMAGE_MIMES,
    VIDEO_MIMES,
)


def test_extract_urls_finds_multiple():
    text = "see https://a.com/x and http://b.org also nope"
    urls = extract_urls(text)
    assert "https://a.com/x" in urls
    assert "http://b.org" in urls
    assert len(urls) == 2


def test_extract_urls_none():
    assert extract_urls("no links here") == []


class _FakeUpload:
    def __init__(self, filename, content_type, data):
        self.filename = filename
        self.content_type = content_type
        self._data = data

    async def read(self, size=-1):
        # Mirror starlette UploadFile.read(size=-1): full read with no/neg size,
        # otherwise return up to `size` bytes and advance (supports chunked reads).
        if size is None or size < 0:
            data, self._data = self._data, b""
            return data
        chunk, self._data = self._data[:size], self._data[size:]
        return chunk


@pytest.mark.asyncio
async def test_save_upload_image(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    svc = FileService()
    up = _FakeUpload("photo.png", "image/png", b"\x89PNG data")
    result = await svc.save_upload(up)
    assert result["type"] == "image"
    assert result["name"] == "photo.png"
    assert result["mime_type"] == "image/png"
    assert result["size"] == len(b"\x89PNG data")
    assert result["url"].endswith("/photo.png")
    # the file actually got written
    written = tmp_path / result["id"] / "photo.png"
    assert written.read_bytes() == b"\x89PNG data"


@pytest.mark.asyncio
async def test_save_upload_sanitizes_name_and_classifies_file(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    svc = FileService()
    up = _FakeUpload("my report!.pdf", "application/pdf", b"%PDF-")
    result = await svc.save_upload(up)
    assert result["type"] == "file"
    assert "!" not in result["name"]
    assert result["name"].endswith(".pdf")


@pytest.mark.asyncio
async def test_save_upload_video(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    svc = FileService()
    up = _FakeUpload("clip.mp4", "video/mp4", b"vid")
    result = await svc.save_upload(up)
    assert result["type"] == "video"


def test_file_path_missing(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    svc = FileService()
    assert svc.file_path("nope", "x.txt") is None


def test_file_path_existing(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    d = tmp_path / "fid"
    d.mkdir()
    (d / "a.txt").write_text("hi")
    svc = FileService()
    p = svc.file_path("fid", "a.txt")
    assert p is not None and p.exists()


def test_extract_text_missing_file(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    svc = FileService()
    assert svc.extract_text("nope", "a.txt", "text/plain") == ""


def test_extract_text_plain(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    d = tmp_path / "fid"
    d.mkdir()
    (d / "notes.txt").write_text("hello world contents")
    svc = FileService()
    text = svc.extract_text("fid", "notes.txt", "text/plain")
    assert "hello world" in text


def test_extract_text_by_extension(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    d = tmp_path / "fid"
    d.mkdir()
    (d / "data.json").write_text('{"k": 1}')
    svc = FileService()
    text = svc.extract_text("fid", "data.json", "application/octet-stream")
    assert '"k"' in text


def test_extract_text_unsupported_type(tmp_path, monkeypatch):
    import app.services.files as files_mod

    monkeypatch.setattr(files_mod, "UPLOAD_DIR", tmp_path)
    d = tmp_path / "fid"
    d.mkdir()
    (d / "blob.bin").write_bytes(b"\x00\x01\x02")
    svc = FileService()
    assert svc.extract_text("fid", "blob.bin", "application/octet-stream") == ""


def _patch_transport(monkeypatch, transport):
    orig_init = httpx.AsyncClient.__init__
    monkeypatch.setattr(
        httpx.AsyncClient,
        "__init__",
        lambda self, *a, **k: orig_init(self, *a, **{**k, "transport": transport}),
    )


@pytest.mark.asyncio
async def test_unfurl_parses_og_tags(monkeypatch):
    html = (
        "<html><head>"
        '<meta property="og:title" content="Cool Page">'
        '<meta property="og:description" content="A description">'
        '<meta property="og:image" content="https://img.test/p.png">'
        '<link rel="icon" href="/favicon.ico">'
        "<title>Fallback Title</title>"
        "</head></html>"
    )
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, text=html, headers={"content-type": "text/html"}
        )
    )
    _patch_transport(monkeypatch, transport)
    svc = FileService()
    result = await svc.unfurl("https://site.test/page")
    assert result["title"] == "Cool Page"
    assert result["description"] == "A description"
    assert result["image"] == "https://img.test/p.png"
    assert result["favicon"] == "https://site.test/favicon.ico"


@pytest.mark.asyncio
async def test_unfurl_non_html_returns_base(monkeypatch):
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, content=b"binary", headers={"content-type": "application/pdf"}
        )
    )
    _patch_transport(monkeypatch, transport)
    svc = FileService()
    url = "https://site.test/file.pdf"
    result = await svc.unfurl(url)
    assert result["type"] == "link"
    assert result["title"] == url
    assert result["description"] == ""


@pytest.mark.asyncio
async def test_unfurl_request_error_returns_base(monkeypatch):
    def boom(req):
        raise httpx.ConnectError("down")

    transport = httpx.MockTransport(boom)
    _patch_transport(monkeypatch, transport)
    svc = FileService()
    result = await svc.unfurl("https://dead.test")
    assert result["title"] == "https://dead.test"


@pytest.mark.asyncio
async def test_unfurl_title_fallback(monkeypatch):
    html = "<html><head><title>  Just A Title  </title></head></html>"
    transport = httpx.MockTransport(
        lambda req: httpx.Response(
            200, text=html, headers={"content-type": "text/html; charset=utf-8"}
        )
    )
    _patch_transport(monkeypatch, transport)
    svc = FileService()
    result = await svc.unfurl("https://x.test")
    assert result["title"] == "Just A Title"


def test_mime_sets_are_disjoint():
    assert not (IMAGE_MIMES & VIDEO_MIMES)
