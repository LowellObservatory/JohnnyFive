# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
#  Created on 7 Feb 2020
#
#  @author: rhamilton

"""One line description of module.

Further description.
"""

from __future__ import division, print_function, absolute_import

import twitter

import ligmos


def sendMessage(twit, message):
    """
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
    confFile = '../config/johnnyfive.conf'
    conf = ligmos.utils.confparsers.rawParser(confFile)

    # Quick and dirty for prototyping, will set up classes later
    twit = conf['twitterSetup']

    sendMessage(twit)
