# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 14-Feb-2022
#
#  @author: tbowers

"""Slack communication module

Slack API Documentation:
        https://slack.dev/python-slack-sdk/

TODO: Properly deal with possible error states (try/except blocks)

"""

# Built-In Libraries
import pathlib
from typing import Any
import warnings

# 3rd Party Libraries
import slack_sdk
import slack_sdk.errors

# Internal Imports
import johnnyfive.utils


# Set API Components
__all__ = ["SlackChannel"]


class SlackChannel:
    """SlackChannel Class for communicating with a Slack Channel

    Resolves a channel name and provides message and file operations.

    Parameters
    ----------
    channel_name : :obj:`str`
        Slack Channel into which to post
    """

    def __init__(self, channel_name: str) -> None:
        """Initialize a channel client.

        Parameters
        ----------
        channel_name : str
            Human-readable Slack channel name.
        """
        self.client = setup_slack()

        # Get the channel ID
        self.channel_id = self._read_channels(channel_name)

    def send_message(self, message: str) -> Any:
        """Send a (text only) message to the channel

        The Slack API response is returned unchanged.

        Parameters
        ----------
        message : :obj:`str` or `blocks[]` array
            The message to send to the Slack channel

        Returns
        -------
        :obj:`~typing.Any`
            The response from Slack
        """
        response = None
        try:
            # Call the conversations.list method using the WebClient
            response = johnnyfive.utils.safe_service_connect(
                self.client.chat_postMessage,
                channel=self.channel_id,
                text=message,
                # You could also use a blocks[] array to send richer content
            )
            # Print result, which includes information about the message (like TS)
            # print(result)
        except slack_sdk.errors.SlackApiError as error:
            warnings.warn(
                f"An error occurred within SlackChannel.send_message():\n{error}"
            )
        return response

    def upload_file(self, file: str | pathlib.Path, title: str | None = None) -> Any:
        """Upload a file to the channel

        The Slack API response is returned unchanged.

        Parameters
        ----------
        file : :obj:`str` or :obj:`~pathlib.Path`
            The (path and) filename of the file to be uploaded.
        title : :obj:`str`, optional
            The title for the file posted  (Default: None)

        Returns
        -------
        :obj:`~typing.Any`
            The response from Slack
        """
        response = None
        try:
            response = johnnyfive.utils.safe_service_connect(
                self.client.files_upload,
                channels=self.channel_id,
                file=file,
                title=title,
            )
        except slack_sdk.errors.SlackApiError as error:
            warnings.warn(
                f"An error occurred within SlackChannel.upload_file():\n{error}"
            )
        return response

    def _read_channels(self, name: str) -> str | None:
        """Return the Channel ID for the names channel

        Parameters
        ----------
        name : :obj:`str`
            The name of the channel

        Returns
        -------
        :obj:`str`
            The desired Channel ID
        """
        conversation_id = None

        try:
            # Call the conversations.list() method using the WebClient
            result = johnnyfive.utils.safe_service_connect(
                self.client.conversations_list
            )
            for _ in result:
                if conversation_id is not None:
                    break
                for channel in result["channels"]:
                    if channel["name"] == name:
                        conversation_id = channel["id"]
                        break

        except slack_sdk.errors.SlackApiError as error:
            warnings.warn(
                f"An error occurred within SlackChannel._read_channels():\n{error}"
            )

        # Return the conversation ID
        return conversation_id


# Internal Functions =========================================================#
def setup_slack() -> slack_sdk.web.client.WebClient | None:
    """Setup the Slack WebClient for posting

    Reads the configured token and creates a client for Slack API calls.

    Returns
    -------
    client : :obj:`~slack_sdk.web.client.WebClient`
        The WebClient object needed for reading and writing
    """
    # Read the setup
    setup = johnnyfive.utils.read_config_section("slackSetup")

    # SlackWebClient instantiates a client that can call API methods
    # When using Bolt, you can use either `app.client` or the `client` passed to listeners.
    try:
        client = slack_sdk.WebClient(token=setup.password)
    except slack_sdk.errors.SlackApiError as error:
        warnings.warn(f"An error occurred within setup_slack():\n{error}")
        client = None

    return client
