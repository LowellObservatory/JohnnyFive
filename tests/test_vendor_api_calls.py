"""Unit tests for every vendor-facing J5 request shape.

The fakes emulate only the discovery/client protocols consumed by J5.  They
make the tests hermetic while asserting the exact method and request payload
sent to Gmail and Confluence.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import ANY

import pytest

from johnnyfive import confluence, gmail


class FakeRequest:
    """Represent a vendor SDK request with a recorded ``execute`` result."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Store the result returned from the simulated API request.

        Parameters
        ----------
        response : dict[str, Any]
            Value returned by :meth:`execute`.
        """
        self.response = response

    def execute(self) -> dict[str, Any]:
        """Return the configured API response.

        Returns
        -------
        dict[str, Any]
            Simulated vendor API response.
        """
        return self.response


class RecordingGmailService:
    """Fake Gmail discovery service that records every J5 API request."""

    def __init__(self) -> None:
        """Initialize resource selection and request records."""
        self.resource = ""
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def users(self) -> RecordingGmailService:
        """Return the Gmail users resource.

        Returns
        -------
        RecordingGmailService
            This fake resource.
        """
        return self

    def labels(self) -> RecordingGmailService:
        """Select the Gmail labels resource.

        Returns
        -------
        RecordingGmailService
            This fake resource.
        """
        self.resource = "labels"
        return self

    def messages(self) -> RecordingGmailService:
        """Select the Gmail messages resource.

        Returns
        -------
        RecordingGmailService
            This fake resource.
        """
        self.resource = "messages"
        return self

    def list(self, **kwargs: Any) -> FakeRequest:
        """Record a labels or messages list request.

        Parameters
        ----------
        **kwargs : Any
            Vendor request parameters.

        Returns
        -------
        FakeRequest
            Simulated list response.
        """
        self.calls.append((f"{self.resource}.list", kwargs))
        if self.resource == "labels":
            return FakeRequest(
                {
                    "labels": [
                        {"id": "L-REPORTS", "name": "Reports"},
                        {"id": "L-ARCHIVE", "name": "Archive"},
                    ]
                }
            )
        return FakeRequest({"messages": [{"id": "message-1"}]})

    def get(self, **kwargs: Any) -> FakeRequest:
        """Record a full-message request.

        Parameters
        ----------
        **kwargs : Any
            Vendor request parameters.

        Returns
        -------
        FakeRequest
            Simulated message response.
        """
        self.calls.append(("messages.get", kwargs))
        return FakeRequest(
            {
                "payload": {
                    "headers": [{"name": "Subject", "value": "Report"}],
                    "mimeType": "text/plain",
                    "body": {"data": "T0s"},
                }
            }
        )

    def modify(self, **kwargs: Any) -> FakeRequest:
        """Record a single-message label modification.

        Parameters
        ----------
        **kwargs : Any
            Vendor request parameters.

        Returns
        -------
        FakeRequest
            Simulated modified message response.
        """
        self.calls.append(("messages.modify", kwargs))
        return FakeRequest({"id": kwargs["id"], "labelIds": ["L-REPORTS"]})

    def batchModify(self, **kwargs: Any) -> FakeRequest:
        """Record a batch label modification.

        Parameters
        ----------
        **kwargs : Any
            Vendor request parameters.

        Returns
        -------
        FakeRequest
            Simulated empty Gmail batch response.
        """
        self.calls.append(("messages.batchModify", kwargs))
        return FakeRequest({})

    def send(self, **kwargs: Any) -> FakeRequest:
        """Record a Gmail send request.

        Parameters
        ----------
        **kwargs : Any
            Vendor request parameters.

        Returns
        -------
        FakeRequest
            Simulated sent message response.
        """
        self.calls.append(("messages.send", kwargs))
        return FakeRequest({"id": "sent-1"})


def test_gmail_wrapper_uses_every_messages_and_labels_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert Gmail list, get, modify, batch-modify, and send request shapes."""
    service = RecordingGmailService()
    monkeypatch.setattr(
        gmail, "setup_gmail", lambda interactive=False, logger=None: service
    )

    messages = gmail.GetMessages(
        label="Reports", after="2026/09/01", before="2026/10/01"
    )

    assert messages.message_list == [{"id": "message-1"}]
    assert messages.render_message("message-1") == {
        "subject": "Report",
        "sender": "",
        "date": "",
        "body": "OK",
    }
    assert messages.update_msg_labels("message-1", add_labels=["Reports"]) == {
        "id": "message-1",
        "labelIds": ["L-REPORTS"],
    }
    messages.update_messages_labels(
        ["message-1"], add_labels=["Reports"], remove_labels=["Archive"]
    )

    message = gmail.GmailMessage(
        "recipient@example.test", "Subject", "Body", fromaddr="bot@example.test"
    )
    assert message.send() == {"id": "sent-1"}

    assert service.calls == [
        ("labels.list", {"userId": "me", "fields": "labels(id,name)"}),
        (
            "messages.list",
            {
                "userId": "me",
                "q": " after:2026/09/01 before:2026/10/01",
                "maxResults": 500,
                "labelIds": ["L-REPORTS"],
            },
        ),
        ("messages.get", {"userId": "me", "id": "message-1", "format": "full"}),
        (
            "messages.modify",
            {
                "userId": "me",
                "id": "message-1",
                "body": {"addLabelIds": ["L-REPORTS"]},
            },
        ),
        (
            "messages.batchModify",
            {
                "userId": "me",
                "body": {
                    "ids": ["message-1"],
                    "addLabelIds": ["L-REPORTS"],
                    "removeLabelIds": ["L-ARCHIVE"],
                },
            },
        ),
        ("messages.send", {"userId": "me", "body": ANY}),
    ]
    assert "raw" in service.calls[-1][1]["body"]


def test_setup_gmail_builds_the_vendor_discovery_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build Gmail v1 with loaded credentials without opening a browser."""
    credentials = SimpleNamespace(valid=True)
    built_service = object()
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    monkeypatch.setattr(gmail.pathlib.Path, "exists", lambda _: True)
    monkeypatch.setattr(
        gmail.google.oauth2.credentials.Credentials,
        "from_authorized_user_file",
        lambda *_: credentials,
    )

    def build(*args: Any, **kwargs: Any) -> object:
        """Record the Google discovery construction request."""
        calls.append((args, kwargs))
        return built_service

    monkeypatch.setattr(gmail.googleapiclient.discovery, "build", build)

    assert gmail.setup_gmail() is built_service
    assert calls == [(("gmail", "v1"), {"credentials": credentials})]


class RecordingConfluenceClient:
    """Fake Confluence REST client recording every J5 request."""

    username = "bot"
    url = "https://confluence.example/"

    def __init__(self) -> None:
        """Initialize request and mutable page state records."""
        self.calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []

    def get_page_by_title(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Record a title lookup and report a missing page.

        Parameters
        ----------
        *args : Any
            Vendor positional arguments.
        **kwargs : Any
            Vendor keyword arguments.

        Returns
        -------
        dict[str, Any]
            Empty REST v5 lookup response.
        """
        self.calls.append(("get_page_by_title", args, kwargs))
        return {"results": []}

    def create_page(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        """Record a page creation and return its content ID.

        Returns
        -------
        dict[str, str]
            REST content identity.
        """
        self.calls.append(("create_page", args, kwargs))
        return {"id": "P-1"}

    def add_comment(self, *args: Any, **kwargs: Any) -> None:
        """Record a Confluence comment request."""
        self.calls.append(("add_comment", args, kwargs))

    def set_page_label(self, *args: Any, **kwargs: Any) -> None:
        """Record a Confluence label request."""
        self.calls.append(("set_page_label", args, kwargs))

    def attach_file(self, *args: Any, **kwargs: Any) -> None:
        """Record a Confluence attachment upload request."""
        self.calls.append(("attach_file", args, kwargs))

    def get_attachments_from_content(
        self, *args: Any, **kwargs: Any
    ) -> dict[str, list[dict[str, str]]]:
        """Record an attachment listing request and return one attachment."""
        self.calls.append(("get_attachments_from_content", args, kwargs))
        return {"results": [{"id": "A-1", "title": "report.txt"}]}

    def delete_attachment(self, *args: Any, **kwargs: Any) -> None:
        """Record an attachment-content deletion request."""
        self.calls.append(("delete_attachment", args, kwargs))

    def get_page_by_id(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Record a page-content retrieval request."""
        self.calls.append(("get_page_by_id", args, kwargs))
        return {"body": {"storage": {"value": "<p>Current</p>"}}}

    def update_page(self, *args: Any, **kwargs: Any) -> None:
        """Record a page update request."""
        self.calls.append(("update_page", args, kwargs))

    def remove_page(self, *args: Any, **kwargs: Any) -> None:
        """Record a page deletion request."""
        self.calls.append(("remove_page", args, kwargs))


def test_confluence_wrapper_uses_all_supported_rest_operations() -> None:
    """Assert exact REST-client calls for every page mutation and retrieval."""
    client = RecordingConfluenceClient()
    page = confluence.ConfluencePage("OPS", "Nightly", instance=client)

    page.create("<p>Created</p>", parent_id="PARENT")
    page.add_comment("Done")
    page.add_label("nightly")
    page.attach_file(
        "report.txt", name="Report", content_type="text/plain", comment="log"
    )
    assert page.get_page_attachments() == [{"id": "A-1", "title": "report.txt"}]
    page.delete_attachment("report.txt")
    assert page.get_page_contents() == "<p>Current</p>"
    page.update_contents("<p>Updated</p>", minor_edit=True, version_comment="run")
    page.smite()

    assert client.calls == [
        ("get_page_by_title", ("OPS", "Nightly"), {"limit": 2}),
        (
            "create_page",
            ("OPS", "Nightly", "<p>Created</p>"),
            {"parent_id": "PARENT", "representation": "storage"},
        ),
        ("add_comment", ("P-1", "Done"), {}),
        ("set_page_label", ("P-1", "nightly"), {}),
        (
            "attach_file",
            ("report.txt",),
            {
                "name": "Report",
                "content_type": "text/plain",
                "page_id": "P-1",
                "comment": "log",
            },
        ),
        ("get_attachments_from_content", ("P-1",), {"start": 0, "limit": 200}),
        (
            "get_attachments_from_content",
            ("P-1",),
            {"filename": "report.txt", "limit": 2},
        ),
        ("delete_attachment", ("A-1",), {}),
        ("get_page_by_id", ("P-1",), {"expand": "body.storage"}),
        (
            "update_page",
            ("P-1", "Nightly", "<p>Updated</p>"),
            {
                "representation": "storage",
                "minor_edit": True,
                "version_comment": "run",
                "always_update": False,
            },
        ),
        ("remove_page", ("P-1",), {}),
    ]
    assert page.exists is False
    assert page.page_id is None


def test_authenticate_gmail_removes_the_old_token_and_starts_interactive_auth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise token cleanup and the interactive OAuth entry point."""
    token = tmp_path / "gmail_token.json"
    token.write_text("expired", encoding="utf-8")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(gmail.johnnyfive.utils.Paths, "gmail_token", token)
    monkeypatch.setattr(gmail, "setup_gmail", lambda **kwargs: calls.append(kwargs))

    gmail.authenticate_gmail()

    assert not token.exists()
    assert calls == [{"interactive": True}]
