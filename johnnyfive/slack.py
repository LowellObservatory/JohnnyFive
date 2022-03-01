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
import logging

# 3rd Party Libraries
from slack_sdk import WebClient as SlackWebClient
from slack_sdk.errors import SlackApiError

# Internal Imports
from . import utils


# Set API Components
__all__ = ['SlackChannel']


class SlackChannel():
    """SlackChannel _summary_

    _extended_summary_

    Parameters
    ----------
    channel_name : `str`
        Slack Channel into which to post
    """
    def __init__(self, channel_name):
        self.client, _ = setup_slack()

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
            response = self.client.chat_postMessage(
                                    channel=self.channel_id,
                                    text=message
                # You could also use a blocks[] array to send richer content
            )
            # Print result, which includes information about the message (like TS)
            #print(result)
        except SlackApiError as e:
            print(f"Error: {e}")
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
            response = self.client.files_upload(
                                   channels=self.channel_id,
                                   file=file,
                                   title=title)
        except SlackApiError as e:
            print(f"Error: {e}")
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
            for _ in (result := self.client.conversations_list()):
                if conversation_id is not None:
                    break
                for channel in result["channels"]:
                    if channel["name"] == name:
                        conversation_id = channel["id"]
                        #Print result
                        print(f"Found conversation ID: {conversation_id}")
                        break

        except SlackApiError as e:
            print(f"Error: {e}")

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
    setup = utils.read_ligmos_conffiles('slackSetup')

    # SlackWebClient instantiates a client that can call API methods
    # When using Bolt, you can use either `app.client` or the `client` passed to listeners.
    client = SlackWebClient(token=setup.password)
    logger = logging.getLogger(__name__)

    return client, logger
