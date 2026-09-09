# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 7 Feb 2020
#
#  @author: rhamilton

"""One line description of module.

Further description.
"""

from __future__ import division, print_function, absolute_import

import configparser
from pathlib import Path
from typing import Mapping

import twitter


def sendMessage(twit: Mapping[str, str], message: str) -> None:
    """Post a message to Twitter using configured API credentials.

    Parameters
    ----------
    twit : Mapping[str, str]
        Twitter API credential mapping.
    message : str
        Message to post.

    Returns
    -------
    None
        The API response is printed for this prototype script.
    """
    api = twitter.Api(consumer_key=twit['apiKey'],
                      consumer_secret=twit['apiSecret'],
                      access_token_key=twit['tokenKey'],
                      access_token_secret=twit['tokenSecret'])

    message = 'Hello world!\n\nhttp://www.mygalaxies.co.uk/txynr4/'
    media = '../images/helloworld.png'

    try:
        status = api.PostUpdate(message, media=media)
    except UnicodeDecodeError:
        print("Your message could not be encoded.")
        print("Try explicitly specifying the encoding!")

    print(status)


if __name__ == "__main__":
    conf_file = Path(__file__).parents[1] / "johnnyfive" / "config" / "johnnyfive.conf"
    conf = configparser.ConfigParser()
    conf.read(conf_file)

    # Quick and dirty for prototyping, will set up classes later
    twit = conf["twitterSetup"]

    sendMessage(twit)
