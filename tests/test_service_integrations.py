"""Hermetic integration tests for J5's external-service wrappers."""

from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httplib2
import pytest

from johnnyfive import confluence, gmail, slack


class FakeSlackClient:
    """Minimal Slack client that records wrapper calls."""

    def __init__(self) -> None:
        """Initialize call recording."""
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.cursors: list[str | None] = []

    def conversations_list(self, **kwargs: Any) -> dict[str, Any]:
        """Return two pages of available channels."""
        self.cursors.append(kwargs.get("cursor"))
        if kwargs.get("cursor") == "page-2":
            return {
                "channels": [{"name": "alerts", "id": "C123"}],
                "response_metadata": {"next_cursor": ""},
            }
        return {
            "channels": [{"name": "general", "id": "C000"}],
            "response_metadata": {"next_cursor": "page-2"},
        }

    def chat_postMessage(self, **kwargs: Any) -> dict[str, Any]:
        """Record and return a message response."""
        self.calls.append(("message", kwargs))
        return {"ok": True, **kwargs}

    def files_upload_v2(self, **kwargs: Any) -> dict[str, Any]:
        """Record and return an upload response."""
        self.calls.append(("upload", kwargs))
        return {"ok": True, **kwargs}


def test_slack_channel_routes_messages_and_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve a channel and route wrapper operations to its client."""
    client = FakeSlackClient()
    monkeypatch.setattr(slack, "setup_slack", lambda: client)
    safe_calls: list[int] = []

    def safe_call(func: Any, **kwargs: Any) -> Any:
        """Record retry counts while executing the fake Slack request."""
        safe_calls.append(kwargs.pop("nretries"))
        return func(**kwargs)

    monkeypatch.setattr(slack.johnnyfive.utils, "safe_service_connect", safe_call)

    channel = slack.SlackChannel("alerts")

    assert channel.send_message("hello") == {
        "ok": True,
        "channel": "C123",
        "text": "hello",
    }
    assert channel.upload_file("report.txt", title="Report")["title"] == "Report"
    assert [name for name, _ in client.calls] == ["message", "upload"]
    assert client.cursors == [None, "page-2"]
    assert client.calls[1][1]["channel"] == "C123"
    assert "channels" not in client.calls[1][1]
    assert safe_calls == [5, 5, 1, 1]


def test_slack_channel_uses_a_conversation_id_without_a_lookup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Avoid a conversations.list request when an ID is supplied directly."""
    client = FakeSlackClient()
    monkeypatch.setattr(slack, "setup_slack", lambda: client)

    channel = slack.SlackChannel("C0123456789")

    assert channel.channel_id == "C0123456789"
    assert client.cursors == []


def test_setup_slack_adds_rate_limit_retry_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configure Slack retries that honor HTTP 429 Retry-After responses."""
    config = SimpleNamespace(password="xoxb-test", token=None)
    monkeypatch.setattr(slack.johnnyfive.utils, "read_config_section", lambda _: config)

    client = slack.setup_slack()

    assert client.token == "xoxb-test"
    assert any(
        isinstance(handler, slack.RateLimitErrorRetryHandler)
        for handler in client.retry_handlers
    )


class FakeConfluenceClient:
    """Minimal Confluence client that records page operations."""

    username = "bot"
    url = "https://confluence.example/"

    def __init__(self) -> None:
        """Initialize call recording."""
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self.permission_queries = 0
        self.attachment_requests: list[dict[str, Any]] = []
        self.deleted_attachment_ids: list[str] = []
        self.created_pages: list[dict[str, Any]] = []
        self.updated_pages: list[dict[str, Any]] = []
        self.removed_page_ids: list[str] = []

    def get_space_permissions(self, space: str) -> list[dict[str, Any]]:
        """Grant the permissions used by this test."""
        self.permission_queries += 1
        return [
            {
                "type": permission,
                "spacePermissions": [{"userName": self.username}],
            }
            for permission in (
                "COMMENT",
                "EDITSPACE",
                "CREATEATTACHMENT",
                "REMOVEATTACHMENT",
                "REMOVEPAGE",
            )
        ]

    def page_exists(self, space: str, title: str) -> bool:
        """Report that the page exists."""
        return True

    def get_page_id(self, space: str, title: str) -> str:
        """Return a deterministic page ID."""
        return "42"

    def get_page_by_title(
        self, space: str, title: str, **kwargs: Any
    ) -> dict[str, list[dict[str, str]]]:
        """Return the title lookup shape used by the REST v5 client."""
        assert kwargs == {"limit": 2}
        return {"results": [{"id": "42"}]}

    def add_comment(self, *args: Any, **kwargs: Any) -> None:
        """Record a comment call."""
        self.calls.append(("comment", args, kwargs))

    def set_page_label(self, *args: Any, **kwargs: Any) -> None:
        """Record a label call."""
        self.calls.append(("label", args, kwargs))

    def get_attachments_from_content(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, list[dict[str, str]]]:
        """Return deterministic paginated attachment metadata."""
        self.attachment_requests.append(kwargs)
        if kwargs.get("start") == 2:
            return {"results": [{"id": "attachment-3", "title": "third.txt"}]}
        return {
            "results": [
                {"id": "attachment-1", "title": "first.txt"},
                {"id": "attachment-2", "title": "second.txt"},
            ]
        }

    def delete_attachment(self, attachment_id: str) -> None:
        """Record a REST attachment-content deletion."""
        self.deleted_attachment_ids.append(attachment_id)

    def create_page(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        """Record a page creation and return its REST content ID."""
        self.created_pages.append({"args": args, **kwargs})
        return {"id": "43"}

    def update_page(self, *args: Any, **kwargs: Any) -> None:
        """Record a page update request."""
        self.updated_pages.append({"args": args, **kwargs})

    def remove_page(self, page_id: str) -> None:
        """Record a page deletion request."""
        self.removed_page_ids.append(page_id)

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
    assert page.get_page_attachments() == [
        {"id": "attachment-1", "title": "first.txt"},
        {"id": "attachment-2", "title": "second.txt"},
    ]
    assert page.get_page_contents() == "<p>content</p>"
    assert [name for name, _, _ in client.calls] == ["comment", "label"]
    assert page.space_perms == {}
    assert client.permission_queries == 0


def test_confluence_page_uses_rest_attachment_pagination_and_deletion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Page attachment helpers paginate metadata and delete by content ID."""
    client = FakeConfluenceClient()
    monkeypatch.setattr(confluence, "setup_confluence", lambda use_oauth=False: client)
    page = confluence.ConfluencePage("OPS", "Status")

    assert page.get_page_attachments(limit=2, all_pages=True) == [
        {"id": "attachment-1", "title": "first.txt"},
        {"id": "attachment-2", "title": "second.txt"},
        {"id": "attachment-3", "title": "third.txt"},
    ]
    page.delete_attachment("first.txt")

    assert client.deleted_attachment_ids == ["attachment-1"]
    assert client.attachment_requests[-1] == {"filename": "first.txt", "limit": 2}


def test_confluence_page_uses_storage_and_local_post_mutation_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use current REST defaults without redundant metadata requests."""
    client = FakeConfluenceClient()
    monkeypatch.setattr(confluence, "setup_confluence", lambda use_oauth=False: client)
    page = confluence.ConfluencePage("OPS", "Status")
    page._set_metadata_from_page_id(None)

    page.create("<p>Created</p>")
    page.update_contents(
        "<p>Updated</p>", minor_edit=True, version_comment="nightly", always_update=True
    )
    page.smite()

    assert page.exists is False
    assert page.page_id is None
    assert client.created_pages == [
        {
            "args": ("OPS", "Status", "<p>Created</p>"),
            "parent_id": None,
            "representation": "storage",
        }
    ]
    assert client.updated_pages == [
        {
            "args": ("43", "Status", "<p>Updated</p>"),
            "representation": "storage",
            "minor_edit": True,
            "version_comment": "nightly",
            "always_update": True,
        }
    ]
    assert client.removed_page_ids == ["43"]


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


class FakeGmailMailboxService:
    """Model paginated message, label, and batch-label Gmail resources."""

    def __init__(self) -> None:
        """Initialize fixed API responses and request records."""
        self.resource = ""
        self.label_requests: list[dict[str, Any]] = []
        self.message_requests: list[dict[str, Any]] = []
        self.batch_bodies: list[dict[str, list[str]]] = []

    def users(self) -> FakeGmailMailboxService:
        """Return the users API facade."""
        return self

    def labels(self) -> FakeGmailMailboxService:
        """Select the labels resource."""
        self.resource = "labels"
        return self

    def messages(self) -> FakeGmailMailboxService:
        """Select the messages resource."""
        self.resource = "messages"
        return self

    def list(self, **kwargs: Any) -> FakeGmailRequest:
        """Return labels or a selected page of message IDs."""
        if self.resource == "labels":
            self.label_requests.append(kwargs)
            return FakeGmailRequest({"labels": [{"id": "L1", "name": "Reports"}]})

        self.message_requests.append(kwargs)
        if kwargs.get("pageToken") == "second":
            return FakeGmailRequest({"messages": [{"id": "message-2"}]})
        return FakeGmailRequest(
            {"messages": [{"id": "message-1"}], "nextPageToken": "second"}
        )

    def batchModify(
        self, *, userId: str, body: dict[str, list[str]]
    ) -> FakeGmailRequest:
        """Record a batch label update and return Gmail's empty response."""
        assert userId == "me"
        self.batch_bodies.append(body)
        return FakeGmailRequest({})


def test_gmail_message_builds_attachment_and_sends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Construct a MIME message, attach a file, and send through the fake API."""
    service = FakeGmailService()
    attachment = tmp_path / "report.txt"
    attachment.write_text("report contents", encoding="utf-8")
    monkeypatch.setattr(
        gmail, "setup_gmail", lambda interactive=False, logger=None: service
    )
    safe_calls: list[int] = []

    def safe_call(func: Any, **kwargs: Any) -> Any:
        """Record retry counts while executing the fake Gmail request."""
        safe_calls.append(kwargs.pop("nretries"))
        return func()

    monkeypatch.setattr(gmail.johnnyfive.utils, "safe_service_connect", safe_call)

    message = gmail.GmailMessage("bot@example.test", "Report", "Body")
    message.add_attachment(attachment)

    assert message.send() == {"id": "message-1"}
    assert service.sent_body is not None
    assert "raw" in service.sent_body
    assert safe_calls == [1]


def test_render_message_traverses_nested_parts_and_prefers_plain_text() -> None:
    """Render nested multipart content without assuming the first part is text."""

    def encode(value: str) -> str:
        """Return unpadded base64url content as Gmail supplies it."""
        return (
            base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")
        )

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
                            {
                                "mimeType": "text/html",
                                "body": {"data": encode("<body>HTML report</body>")},
                            },
                            {
                                "mimeType": "text/plain",
                                "body": {"data": encode("Plain report")},
                            },
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
    assert (
        gmail.GetMessages._extract_message_body(
            {
                "mimeType": "text/html",
                "body": {"data": encode("<body>HTML only</body>")},
            }
        )
        == "HTML only"
    )
    assert (
        gmail.GetMessages._extract_message_body(
            {"mimeType": "multipart/mixed", "body": {}, "parts": []}
        )
        == ""
    )


def test_get_messages_paginates_and_skips_label_lookup_without_a_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retrieve all pages and avoid a needless labels request for no filter."""
    service = FakeGmailMailboxService()
    monkeypatch.setattr(
        gmail, "setup_gmail", lambda interactive=False, logger=None: service
    )

    messages = gmail.GetMessages()

    assert messages.message_list == [{"id": "message-1"}, {"id": "message-2"}]
    assert service.label_requests == []
    assert service.message_requests == [
        {"userId": "me", "q": "", "maxResults": 500},
        {"userId": "me", "q": "", "maxResults": 500, "pageToken": "second"},
    ]


def test_get_messages_selects_strict_listing_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use strict pagination only when the caller explicitly opts in."""
    service = FakeGmailMailboxService()
    calls: list[str] = []
    monkeypatch.setattr(
        gmail, "setup_gmail", lambda interactive=False, logger=None: service
    )
    monkeypatch.setattr(
        gmail.GetMessages,
        "_list_messages",
        lambda self: calls.append("tolerant"),
    )
    monkeypatch.setattr(
        gmail.GetMessages,
        "_list_messages_strict",
        lambda self: calls.append("strict"),
    )

    gmail.GetMessages()
    strict_messages = gmail.GetMessages(strict=True)

    assert strict_messages.strict is True
    assert calls == ["tolerant", "strict"]


def test_get_messages_resolves_labels_and_batches_label_updates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Request only label IDs and names, then batch-update matching messages."""
    service = FakeGmailMailboxService()
    monkeypatch.setattr(
        gmail, "setup_gmail", lambda interactive=False, logger=None: service
    )

    messages = gmail.GetMessages(label="Reports")
    messages.update_messages_labels(["message-1", "message-2"], add_labels=["Reports"])

    assert service.label_requests == [{"userId": "me", "fields": "labels(id,name)"}]
    assert service.message_requests[0]["labelIds"] == ["L1"]
    assert service.batch_bodies == [
        {"ids": ["message-1", "message-2"], "addLabelIds": ["L1"]}
    ]


def test_execute_gmail_request_retries_rate_limits_with_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry a transient Gmail HTTP error once with exponential backoff."""
    attempts = 0
    sleeps: list[float] = []

    def execute() -> dict[str, str]:
        """Fail once with a Gmail rate limit before succeeding."""
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            response = httplib2.Response({"status": "429"})
            content = b'{"error": {"errors": [{"reason": "rateLimitExceeded"}]}}'
            raise gmail.googleapiclient.errors.HttpError(response, content)
        return {"id": "ok"}

    monkeypatch.setattr(
        gmail.johnnyfive.utils,
        "safe_service_connect",
        lambda func, logger=None: func(),
    )
    monkeypatch.setattr(gmail.random, "uniform", lambda lower, upper: 0.0)
    monkeypatch.setattr(gmail.time, "sleep", sleeps.append)

    assert gmail._execute_gmail_request(execute) == {"id": "ok"}
    assert attempts == 2
    assert sleeps == [1.0]
