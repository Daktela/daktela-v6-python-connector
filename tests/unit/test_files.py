"""Tests for file downloads and uploads."""

import io
from pathlib import Path
from typing import Callable, List, Optional

import httpx
import pytest

from daktela import (
    DaktelaClient,
    DaktelaConfig,
    DaktelaFile,
    DaktelaNotFoundException,
    DaktelaProtocolException,
    DaktelaUploadedFile,
    DaktelaValidationException,
    RetryConfig,
)
from daktela.files import _filename_from_disposition

UPLOADED = "e1f056dc18c82ce98c15bb87b923002af8ea9f53.pdf"


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    url: str = "test.daktela.com",
) -> tuple[DaktelaClient, List[httpx.Request]]:
    requests: List[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    http_client = httpx.Client(transport=httpx.MockTransport(record))
    client = DaktelaClient(
        DaktelaConfig(url, "secret-token"),
        retry_config=RetryConfig.disabled(),
        http_client=http_client,
    )
    return client, requests


@pytest.mark.parametrize(
    ("header", "filename"),
    [
        (None, None),
        ("", None),
        ("inline", None),
        ('attachment; filename="report.pdf"', "report.pdf"),
        ('attachment; size=3; filename="a.txt"', "a.txt"),
        (
            "attachment; filename=\"zlutoucky.pdf\"; "
            "filename*=UTF-8''%C5%BElu%C5%A5ou%C4%8Dk%C3%BD.pdf",
            "žluťoučký.pdf",
        ),
    ],
)
def test_filename_from_disposition(header: Optional[str], filename: Optional[str]) -> None:
    assert _filename_from_disposition(header) == filename


def test_daktela_file(tmp_path: Path) -> None:
    file = DaktelaFile(b"SECRET-BYTES", "a.txt", "text/plain")
    assert file.size == 12
    assert file.status_code == 200
    assert "SECRET-BYTES" not in repr(file)
    target = file.save(tmp_path / "a.txt")
    assert target.read_bytes() == b"SECRET-BYTES"


def test_uploaded_file_as_dict() -> None:
    assert DaktelaUploadedFile(UPLOADED, "test.pdf").as_dict() == {
        "name": UPLOADED,
        "title": "test.pdf",
    }


def test_download_recording() -> None:
    client, requests = make_client(
        lambda request: httpx.Response(
            200,
            content=b"ID3audio",
            headers={
                "Content-Type": "audio/mpeg",
                "Content-Disposition": 'attachment; filename="activity_1.mp3"',
            },
        ),
        url="https://example.com/daktela/",
    )

    recording = client.download_recording("activity_1")

    request = requests[0]
    assert str(request.url) == "https://example.com/daktela/file/recording/activity_1?download=true"
    assert request.headers["X-AUTH-TOKEN"] == "secret-token"
    assert request.headers["Accept"] == "*/*"
    assert recording.content == b"ID3audio"
    assert recording.filename == "activity_1.mp3"
    assert recording.content_type == "audio/mpeg"


def test_download_recording_with_extra_parameters() -> None:
    client, requests = make_client(lambda request: httpx.Response(206, content=b"part"))
    recording = client.download_recording("activity 1", {"download": "false"})
    assert requests[0].url.raw_path == b"/file/recording/activity%201?download=false"
    assert recording.status_code == 206
    assert recording.filename is None
    assert recording.content_type is None


@pytest.mark.parametrize("name", ["", "..", "a/b"])
def test_download_recording_rejects_unsafe_names(name: str) -> None:
    client, requests = make_client(lambda request: httpx.Response(200))
    with pytest.raises(ValueError, match="activity_name"):
        client.download_recording(name)
    assert requests == []


def test_missing_recording_raises_not_found() -> None:
    client, _ = make_client(lambda request: httpx.Response(404))
    with pytest.raises(DaktelaNotFoundException):
        client.download_recording("activity_1")


def test_download_file() -> None:
    client, requests = make_client(
        lambda request: httpx.Response(
            200, content=b"%PDF", headers={"Content-Type": "application/pdf"}
        )
    )

    file = client.download_file(
        "activitiesEmail", "170", icon_hash="report.pdf", query_params={"thumbnail": 1}
    )

    params = requests[0].url.params
    assert requests[0].url.path == "/file/download.php"
    assert dict(params) == {
        "mapper": "activitiesEmail",
        "name": "170",
        "download": "1",
        "iconHash": "report.pdf",
        "fullsize": "1",
        "thumbnail": "1",
    }
    assert file.content == b"%PDF"


def test_download_file_resized() -> None:
    client, requests = make_client(lambda request: httpx.Response(200, content=b"img"))
    client.download_file("templates", "7", fullsize=False)
    assert dict(requests[0].url.params) == {"mapper": "templates", "name": "7", "download": "1"}


@pytest.mark.parametrize(("mapper", "name", "message"), [("", "1", "mapper"), ("m", "", "name")])
def test_download_file_requires_mapper_and_name(mapper: str, name: str, message: str) -> None:
    client, _ = make_client(lambda request: httpx.Response(200))
    with pytest.raises(ValueError, match=message):
        client.download_file(mapper, name)


@pytest.mark.parametrize(
    ("content", "filename", "content_type", "expected_type"),
    [
        (b"%PDF-1.7", "report.pdf", None, "application/pdf"),
        (io.BytesIO(b"%PDF-1.7"), "report.pdf", None, "application/pdf"),
        (b"data", "data.unknownext", None, "application/octet-stream"),
        (b"data", "data.bin", "application/x-custom", "application/x-custom"),
    ],
)
def test_upload_file(
    content: object, filename: str, content_type: Optional[str], expected_type: str
) -> None:
    client, requests = make_client(lambda request: httpx.Response(200, json=UPLOADED))

    uploaded = client.upload_file(content, filename, content_type=content_type)  # type: ignore[arg-type]

    request = requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://test.daktela.com/file/upload.php?type=save"
    assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert request.headers["X-AUTH-TOKEN"] == "secret-token"
    body = request.content
    assert f'name="files"; filename="{filename}"'.encode() in body
    assert f"Content-Type: {expected_type}".encode() in body
    assert uploaded == DaktelaUploadedFile(UPLOADED, filename)


@pytest.mark.parametrize(
    ("response", "exception", "message"),
    [
        (
            httpx.Response(400, json="Uploading of this file type is blocked"),
            DaktelaValidationException,
            "Uploading of this file type is blocked",
        ),
        (
            httpx.Response(200, json="Max. allowed file size is 20 MB."),
            DaktelaValidationException,
            "Max. allowed file size is 20 MB.",
        ),
        (
            httpx.Response(200, json={"unexpected": 1}),
            DaktelaValidationException,
            '{"unexpected": 1}',
        ),
        (httpx.Response(200, json=""), DaktelaValidationException, '""'),
        (httpx.Response(200, text="<html>"), DaktelaProtocolException, "not valid JSON"),
    ],
)
def test_upload_errors(response: httpx.Response, exception: type[Exception], message: str) -> None:
    client, _ = make_client(lambda request: response)
    with pytest.raises(exception) as raised:
        client.upload_file(b"<?php", "shell.php")
    assert message in str(raised.value)


def test_upload_is_not_resent_after_a_server_error() -> None:
    requests: List[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(503)

    client = DaktelaClient(
        DaktelaConfig("test.daktela.com", "secret-token"),
        retry_config=RetryConfig(max_retries=3, initial_delay=0),
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(Exception):
        client.upload_file(b"data", "a.txt")
    assert len(requests) == 1


def test_upload_requires_a_filename() -> None:
    client, _ = make_client(lambda request: httpx.Response(200, json=UPLOADED))
    with pytest.raises(ValueError, match="filename"):
        client.upload_file(b"data", "")


@pytest.mark.parametrize(
    ("filename", "safe"),
    [
        (None, None),
        ("report.pdf", "report.pdf"),
        ("../../etc/passwd", "passwd"),
        ("/etc/cron.d/job", "job"),
        ("C:\\Windows\\system.ini", "system.ini"),
        ("..", None),
        (".bashrc", "bashrc"),
        ("bad\x00name\n.txt", "badname.txt"),
        ("dir/", None),
        ("C:evil.txt", "C_evil.txt"),
        ("report.pdf:hidden", "report.pdf_hidden"),
        ('a<b>"c|d?e*.txt', "a_b__c_d_e_.txt"),
        ("report.pdf. . ", "report.pdf"),
        (" . ", None),
        ("NUL", "_NUL"),
        ("con.txt", "_con.txt"),
        ("Com1 .tar.gz", "_Com1 .tar.gz"),
        ("LPT¹.log", "_LPT¹.log"),
        ("console.txt", "console.txt"),
        ("COM10", "COM10"),
    ],
)
def test_safe_filename(filename: Optional[str], safe: Optional[str]) -> None:
    assert DaktelaFile(b"", filename).safe_filename == safe


def test_upload_error_with_status_200_is_redacted() -> None:
    client, _ = make_client(
        lambda request: httpx.Response(200, json="Rejected request with token secret-token")
    )
    with pytest.raises(DaktelaValidationException) as raised:
        client.upload_file(b"data", "a.txt")
    assert str(raised.value) == "[200] Rejected request with token ***"
    assert raised.value.errors == ["Rejected request with token ***"]
