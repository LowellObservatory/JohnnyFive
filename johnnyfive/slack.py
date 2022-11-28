# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
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
import warnings

# 3rd Party Libraries
import slack_sdk

# Internal Imports
import johnnyfive.utils


# Set API Components
__all__ = ["SlackChannel"]


class SlackChannel:
    """SlackChannel Class for communicating with a Slack Channel

    _extended_summary_

    Parameters
    ----------
    channel_name : `str`
        Slack Channel into which to post
    """

    def __init__(self, channel_name):
        self.client = setup_slack()

        # Get the channel ID
        self.channel_id = self._read_channels(channel_name)

    def send_message(self, message):
        """send_message Send a (text only) message to the channel

        _extended_summary_

        Parameters
        ----------
        message : `str` or `blocks[]` array
            The message to send to the Slack channel

        Returns
        -------
        `Any`
            The response from Slack
        """
        response = None
        try:
            # Call the conversations.list method using the WebClient
            response = johnnyfive.utils.safe_service_connect(
                self.client.chat_postMessage,
                channel=self.channel_id,
                text=message
                # You could also use a blocks[] array to send richer content
            )
            # Print result, which includes information about the message (like TS)
            # print(result)
        except slack_sdk.errors.SlackApiError as error:
            warnings.warn(
                f"An error occurred within SlackChannel.send_message():\n{error}"
            )
        return response

    def upload_file(self, file, title=None):
        """upload_file Upload a file to the channel

        _extended_summary_

        Parameters
        ----------
        file : `str` or `os.PathLike`
            The (path and) filename of the file to be uploaded.
        title : `str`, optional
            The title for the file posted [Default: None]

        Returns
        -------
        `Any`
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

    def _read_channels(self, name):
        """_read_channels Return the Channel ID for the names channel

        Parameters
        ----------
        name : `str`
            The name of the channel

        Returns
        -------
        `str`
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
def setup_slack():
    """setup_slack Setup the Slack WebClient for posting

    _extended_summary_

    Returns
    -------
    client : `slack_sdk.web.client.WebClient`
        The WebClient object needed for reading and writing
    logger : `logging.Logger`
        The logging thingie
    """
    # Read the setup
    setup = johnnyfive.utils.read_ligmos_conffiles("slackSetup")

    # SlackWebClient instantiates a client that can call API methods
    # When using Bolt, you can use either `app.client` or the `client` passed to listeners.
    try:
        client = slack_sdk.WebClient(token=setup.password)
    except slack_sdk.errors.SlackApiError as error:
        warnings.warn(f"An error occurred within setup_slack():\n{error}")
        client = None

    return client
