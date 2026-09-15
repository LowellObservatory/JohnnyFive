# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 14-Feb-2022
#
#  @author: tbowers

"""Slack communication helpers built on the current Slack Web API.

The module uses ``chat.postMessage``, cursor-paginated ``conversations.list``,
and the external-upload flow exposed by :meth:`WebClient.files_upload_v2`.
"""

# Built-In Libraries
import collections.abc
import pathlib
import re
import typing

# 3rd Party Libraries
import slack_sdk
import slack_sdk.errors
from slack_sdk.http_retry.builtin_handlers import RateLimitErrorRetryHandler
from slack_sdk.web import SlackResponse
from slack_sdk.web.client import WebClient

# Internal Imports
import johnnyfive.utils

# Set API Components
__all__ = ["SlackChannel"]

_CONVERSATION_ID_PATTERN = re.compile(r"[CDG][A-Z0-9]{8,}")
_DEFAULT_CONVERSATION_TYPES = ("public_channel", "private_channel")


class SlackChannel:
    """Communicate with one Slack conversation.

    A Slack conversation ID avoids a discovery request. Otherwise, the
    supplied name is resolved using every page returned by
    ``conversations.list``.

    Parameters
    ----------
    channel_name : str
        Slack conversation name or ID.
    conversation_types : collections.abc.Sequence[str], optional
        Conversation types searched when ``channel_name`` is a name. The
        default searches public and private channels.

    Raises
    ------
    johnnyfive.utils.J5Error
        If Slack rejects a request or the named conversation is unavailable to
        the configured bot token.
    """

    def __init__(
        self,
        channel_name: str,
        conversation_types: collections.abc.Sequence[str] = _DEFAULT_CONVERSATION_TYPES,
    ) -> None:
        """Initialize a Slack client and resolve the target conversation.

        Parameters
        ----------
        channel_name : str
            Slack conversation name or ID.
        conversation_types : collections.abc.Sequence[str], optional
            Conversation types searched for a conversation name.
        """
        self.client = setup_slack()
        self.conversation_types = tuple(conversation_types)
        self.channel_id = (
            channel_name
            if _CONVERSATION_ID_PATTERN.fullmatch(channel_name)
            else self._read_channels(channel_name)
        )

    def send_message(
        self,
        message: str,
        *,
        blocks: list[dict[str, typing.Any]] | None = None,
        thread_ts: str | None = None,
    ) -> SlackResponse:
        """Send a message to the configured conversation.

        ``message`` is always sent as the plain-text accessibility fallback
        when Block Kit ``blocks`` are supplied.

        Parameters
        ----------
        message : str
            Plain-text message or accessibility fallback for ``blocks``.
        blocks : list[dict[str, typing.Any]], optional
            Slack Block Kit blocks to include in the message.
        thread_ts : str, optional
            Parent message timestamp for a threaded reply.

        Returns
        -------
        slack_sdk.web.SlackResponse
            Slack's response describing the posted message.

        Raises
        ------
        johnnyfive.utils.J5Error
            If Slack rejects the message request.
        """
        kwargs: dict[str, typing.Any] = {"channel": self.channel_id, "text": message}
        if blocks is not None:
            kwargs["blocks"] = blocks
        if thread_ts is not None:
            kwargs["thread_ts"] = thread_ts
        return self._call(
            "send_message", self.client.chat_postMessage, retry_network=False, **kwargs
        )

    def upload_file(
        self,
        file: str | pathlib.Path,
        title: str | None = None,
        *,
        initial_comment: str | None = None,
        thread_ts: str | None = None,
    ) -> SlackResponse:
        """Upload a file using Slack's current external-upload API flow.

        Parameters
        ----------
        file : str or pathlib.Path
            Path to the file to upload.
        title : str, optional
            Title displayed for the uploaded file.
        initial_comment : str, optional
            Message posted alongside the file.
        thread_ts : str, optional
            Parent message timestamp for posting the file in a thread.

        Returns
        -------
        slack_sdk.web.SlackResponse
            Slack's response describing the completed upload.

        Raises
        ------
        johnnyfive.utils.J5Error
            If Slack rejects the upload request.
        """
        return self._call(
            "upload_file",
            self.client.files_upload_v2,
            channel=self.channel_id,
            file=file,
            title=title,
            initial_comment=initial_comment,
            thread_ts=thread_ts,
            retry_network=False,
        )

    def _read_channels(self, name: str) -> str:
        """Resolve a conversation name through cursor-paginated discovery.

        Parameters
        ----------
        name : str
            Exact Slack conversation name to resolve.

        Returns
        -------
        str
            The Slack conversation ID.

        Raises
        ------
        johnnyfive.utils.J5Error
            If no visible conversation has the requested name or Slack rejects
            the lookup.
        """
        cursor: str | None = None
        while True:
            result = self._call(
                "_read_channels",
                self.client.conversations_list,
                cursor=cursor,
                limit=200,
                types=self.conversation_types,
            )
            for channel in result.get("channels", []):
                if channel.get("name") == name and isinstance(channel.get("id"), str):
                    return channel["id"]

            metadata = result.get("response_metadata", {})
            cursor = metadata.get("next_cursor", "") if metadata else ""
            if not cursor:
                break

        raise johnnyfive.utils.J5Error(
            f"Slack conversation {name!r} was not found or is not visible to the bot."
        )

    def _call(
        self,
        operation: str,
        func: collections.abc.Callable[..., SlackResponse],
        retry_network: bool = True,
        **kwargs: typing.Any,
    ) -> SlackResponse:
        """Execute one Slack Web API request and normalize failures.

        Parameters
        ----------
        operation : str
            Name of the enclosing public or private operation.
        func : collections.abc.Callable[..., slack_sdk.web.SlackResponse]
            Slack client method to invoke.
        retry_network : bool, optional
            Whether J5 should retry a network failure. Disable this for
            non-idempotent requests. [Default: True]
        **kwargs : typing.Any
            Keyword arguments forwarded to ``func``.

        Returns
        -------
        slack_sdk.web.SlackResponse
            Successful Slack Web API response.

        Raises
        ------
        johnnyfive.utils.J5Error
            If the request is rejected by Slack.
        """
        try:
            return typing.cast(
                SlackResponse,
                johnnyfive.utils.safe_service_connect(
                    func, nretries=5 if retry_network else 1, **kwargs
                ),
            )
        except slack_sdk.errors.SlackApiError as error:
            johnnyfive.utils.proper_print(
                f"SlackChannel.{operation}() failed: {error}", "except"
            )
            raise johnnyfive.utils.J5Error(
                f"Slack request failed during {operation}."
            ) from error


# Internal Functions =========================================================#
def setup_slack() -> WebClient:
    """Create a Slack client with rate-limit-aware retries.

    The configuration's existing ``password`` field remains supported for bot
    tokens. A ``token`` field, when present, takes precedence.

    Returns
    -------
    slack_sdk.web.client.WebClient
        Configured Slack Web API client.
    """
    setup = johnnyfive.utils.read_config_section("slackSetup")
    token = getattr(setup, "token", None) or setup.password
    client = slack_sdk.WebClient(token=token)
    client.retry_handlers.append(RateLimitErrorRetryHandler(max_retry_count=2))
    return client
