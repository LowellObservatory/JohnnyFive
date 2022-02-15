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
"""

# Built-In Libraries
import logging
import os
from time import sleep

# 3rd Party Libraries
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Lowell Libraries
from ligmos import utils as lig_utils, workers as lig_workers

# Internal Imports
from johnnyfive import utils


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
    # Read in and parse the configuration file (LIGMOS)
    setup = lig_utils.confparsers.rawParser(
                            utils.Paths.config.joinpath('slack.conf'))
    setup = lig_workers.confUtils.assignConf(
                            setup['slackSetup'],
                            lig_utils.classes.baseTarget,
                            backfill=True)

    # WebClient instantiates a client that can call API methods
    # When using Bolt, you can use either `app.client` or the `client` passed to listeners.
    client = WebClient(token=setup.password)
    logger = logging.getLogger(__name__)

    return client, logger


def read_channels(client, logger):
    """read_channels Read the Channels in this Slack Workspace

    _extended_summary_

    Parameters
    ----------
    client : `slack_sdk.web.client.WebClient`
        The WebClient object needed for reading and writing
    logger : `logging.Logger`
        The logging thingie

    Returns
    -------
    `str`
        The conversation ID matching the channel of interest
    """
    # Set up some things
    channel_name = "bot_test"
    conversation_id = None

    # Try something
    try:
        # Call the conversations.list method using the WebClient
        for response in (result := client.conversations_list()):
            if conversation_id is not None:
                break
            for channel in result["channels"]:
                if channel["name"] == channel_name:
                    conversation_id = channel["id"]
                    #Print result
                    print(f"Found conversation ID: {conversation_id}")
                    break

    except SlackApiError as e:
        print(f"Error: {e}")

    # Return the conversation ID
    return conversation_id


def send_message(client, logger, conversation_id):

    # ID of channel you want to post message to
    channel_id = conversation_id

    try:
        # Call the conversations.list method using the WebClient
        result = client.chat_postMessage(
            channel=channel_id,
            text="Now, I'm just cleaning up the code."
            # You could also use a blocks[] array to send richer content
        )
        # Print result, which includes information about the message (like TS)
        #print(result)

    except SlackApiError as e:
        print(f"Error: {e}")


def upload_file():
    """upload_file Upload a file to the conversation

    _extended_summary_
    """
    slack_token = os.environ["SLACK_BOT_TOKEN"]
    client = WebClient(token=slack_token)

    response = client.files_upload(
                            channels="C3UKJTQAC",
                            file="files.pdf",
                            title="Test upload"
                        )


# Main Testing Driver ========================================================#
def main():
    client, logger = setup_slack()
    print(type(client), type(logger))
    conversation_id = read_channels(client, logger)
    print(type(conversation_id))
    send_message(client, logger, conversation_id)


if __name__ == '__main__':
    main()