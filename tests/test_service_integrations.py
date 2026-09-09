"""Hermetic integration tests for J5's external-service wrappers."""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from johnnyfive import confluence, gmail, slack


class FakeSlackClient:
    """Minimal Slack client that records wrapper calls."""

    def __init__(self) -> None:
        """Initialize call recording."""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def conversations_list(self) -> dict[str, list[dict[str, str]]]:
        """Return one available channel."""
        return {"channels": [{"name": "alerts", "id": "C123"}]}

    def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        """Record and return a message response."""
        self.calls.append(("message", kwargs))
        return {"ok": True, **kwargs}

    def files_upload(self, **kwargs: Any) -> dict[str, Any]:
        """Record and return an upload response."""
        self.calls.append(("upload", kwargs))
        return {"ok": True, **kwargs}


def test_slack_channel_routes_messages_and_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve a channel and route wrapper operations to its client."""
    client = FakeSlackClient()
    monkeypatch.setattr(slack, "setup_slack", lambda: client)

    channel = slack.SlackChannel("alerts")

    assert channel.send_message("hello") == {"ok": True, "channel": "C123", "text": "hello"}
    assert channel.upload_file("report.txt", title="Report")["title"] == "Report"
    assert [name for name, _ in client.calls] == ["message", "upload"]


class FakeConfluenceClient:
    """Minimal Confluence client that records page operations."""

    username = "bot"
    url = "https://confluence.example/"

    def __init__(self) -> None:
        """Initialize call recording."""
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.permission_queries = 0

    def get_space_permissions(self, space: str) -> list[dict[str, Any]]:
        """Grant the permissions used by this test."""
        self.permission_queries += 1
        return [
            {
                "type": permission,
                "spacePermissions": [{"userName": self.username}],
            }
            for permission in ("COMMENT", "EDITSPACE", "CREATEATTACHMENT", "REMOVEATTACHMENT", "REMOVEPAGE")
        ]

    def page_exists(self, space: str, title: str) -> bool:
        """Report that the page exists."""
        return True

    def get_page_id(self, space: str, title: str) -> str:
        """Return a deterministic page ID."""
        return "42"

    def add_comment(self, *args: Any, **kwargs: Any) -> None:
        """Record a comment call."""
        self.calls.append(("comment", args, kwargs))

    def set_page_label(self, *args: Any, **kwargs: Any) -> None:
        """Record a label call."""
        self.calls.append(("label", args, kwargs))

    def get_attachments_from_content(self, *args: Any, **kwargs: Any) -> list[str]:
        """Return a deterministic attachment list."""
        return ["attachment-1"]

    def get_page_by_id(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Return deterministic page content."""
        return {"body": {"storage": {"value": "<p>content</p>"}}}


def test_confluence_page_integrates_metadata_and_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exercise metadata, permissions, and API wrappers through one client."""
    client = FakeConfluenceClient()
    monkeypatch.setattr(confluence, "setup_confluence", lambda use_oauth=False: client)

    page = confluence.ConfluencePage("OPS", "Status")
    page.add_comment("All clear")
    page.add_label("nightly")

    assert page.page_id == "42"
    assert page.get_page_attachments() == ["attachment-1"]
    assert page.get_page_contents() == "<p>content</p>"
    assert [name for name, _, _ in client.calls] == ["comment", "label"]
    assert page.space_perms == {}
    assert client.permission_queries == 0


class FakeConfluenceServer:
    """Capture constructor arguments for the explicit v5 Server client."""

    def __init__(self, **kwargs: Any) -> None:
        """Store connection parameters without making a network request."""
        self.kwargs = kwargs


def test_setup_confluence_uses_explicit_server_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create v5 Server clients for basic and bearer-token authentication."""
    config = SimpleNamespace(
        host="https://confluence.example",
        user="bot",
        password="password",
        access_token="token",
    )
    monkeypatch.setattr(confluence, "ConfluenceServer", FakeConfluenceServer)
    monkeypatch.setattr(
        confluence.johnnyfive.utils,
        "read_config_section",
        lambda _: config,
    )

    basic_client = confluence.setup_confluence()
    oauth_client = confluence.setup_confluence(use_oauth=True)

    assert basic_client.kwargs == {
        "url": "https://confluence.example",
        "username": "bot",
        "password": "password",
    }
    assert oauth_client.kwargs["url"] == "https://confluence.example"
    assert oauth_client.kwargs["session"].headers["Authorization"] == "Bearer token"


class FakeGmailRequest:
    """Fake request object with Gmail's execute protocol."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Store the response returned by ``execute``."""
        self.response = response

    def execute(self) -> dict[str, Any]:
        """Return the configured API response."""
        return self.response


class FakeGmailService:
    """Minimal Gmail service used to exercise message construction and sending."""

    def __init__(self) -> None:
        """Initialize a sent-message record."""
        self.sent_body: dict[str, str] | None = None

    def users(self) -> FakeGmailService:
        """Return the users API facade."""
        return self

    def messages(self) -> FakeGmailService:
        """Return the messages API facade."""
        return self

    def send(self, *, userId: str, body: dict[str, str]) -> FakeGmailRequest:
        """Record a send request and return its response."""
        assert userId == "me"
        self.sent_body = body
        return FakeGmailRequest({"id": "message-1"})


class FakeGmailReadService:
    """Minimal Gmail service that returns a predefined full message payload."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Store the API response and requested message format."""
        self.response = response
        self.request_format: str | None = None

    def users(self) -> FakeGmailReadService:
        """Return the users API facade."""
        return self

    def messages(self) -> FakeGmailReadService:
        """Return the messages API facade."""
        return self

    def get(self, *, userId: str, id: str, format: str) -> FakeGmailRequest:
        """Record the requested format and return the configured message."""
        assert userId == "me"
        assert id == "message-2"
        self.request_format = format
        return FakeGmailRequest(self.response)


def test_gmail_message_builds_attachment_and_sends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Construct a MIME message, attach a file, and send through the fake API."""
    service = FakeGmailService()
    attachment = tmp_path / "report.txt"
    attachment.write_text("report contents", encoding="utf-8")
    monkeypatch.setattr(gmail, "setup_gmail", lambda interactive=False, logger=None: service)

    message = gmail.GmailMessage("bot@example.test", "Report", "Body")
    message.add_attachment(attachment)

    assert message.send() == {"id": "message-1"}
    assert service.sent_body is not None
    assert "raw" in service.sent_body


def test_render_message_traverses_nested_parts_and_prefers_plain_text() -> None:
    """Render nested multipart content without assuming the first part is text."""
    def encode(value: str) -> str:
        """Return unpadded base64url content as Gmail supplies it."""
        return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")

    service = FakeGmailReadService(
        {
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Nightly report"},
                    {"name": "From", "value": "bot@example.test"},
                    {"name": "Date", "value": "Mon, 8 Sep 2026 19:31:45 -0700"},
                ],
                "mimeType": "multipart/mixed",
                "body": {},
                "parts": [
                    {
                        "mimeType": "multipart/alternative",
                        "body": {},
                        "parts": [
                            {"mimeType": "text/html", "body": {"data": encode("<body>HTML report</body>")}},
                            {"mimeType": "text/plain", "body": {"data": encode("Plain report")}},
                        ],
                    }
                ],
            }
        }
    )
    messages = object.__new__(gmail.GetMessages)
    messages.service = service
    messages.logger = None

    assert messages.render_message("message-2") == {
        "subject": "Nightly report",
        "sender": "bot@example.test",
        "date": "Mon, 8 Sep 2026 19:31:45 -0700",
        "body": "Plain report",
    }
    assert service.request_format == "full"
    assert gmail.GetMessages._extract_message_body(
        {"mimeType": "text/html", "body": {"data": encode("<body>HTML only</body>")}}
    ) == "HTML only"
    assert gmail.GetMessages._extract_message_body(
        {"mimeType": "multipart/mixed", "body": {}, "parts": []}
    ) == ""
