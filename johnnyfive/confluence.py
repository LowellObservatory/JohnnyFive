# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
#  Created on 23-Sep-2021
#
#  @author: tbowers

"""Confluence communication module

Confluence API Documentation:
        https://atlassian-python-api.readthedocs.io/index.html
"""

# Built-In Libraries
from time import sleep

# 3rd Party Libraries
from atlassian import Confluence

# Lowell Libraries
from ligmos import utils as lig_utils, workers as lig_workers

# Internal Imports
from johnnyfive import utils

def setup_confluence():
    """setup_confluence Set up the Confluence class instance

    Reads in the confluence.conf configuration file, which contains the URL,
    username, and password.  Also contained in the configuration file are
    the Confluence space and page title into which the updated table will be
    placed.

    Returns
    -------
    confluence : `atlassian.Confluence`
        Confluence class, initialized with credentials
    """
    # Read in and parse the configuration file
    setup = lig_utils.confparsers.rawParser(
                            utils.Paths.config.joinpath('confluence.conf'))
    setup = lig_workers.confUtils.assignConf(
                            setup['confluenceSetup'],
                            lig_utils.classes.baseTarget,
                            backfill=True)

    # Return
    return Confluence( url=setup.host,
                       username=setup.user,
                       password=setup.password )


def safe_confluence_connect(func, *args, pause=5, timeout=5, **kwargs):
    """safe_confluence_connect Safely connect to Confluence (error-catching)

    Wrapper for confluence-connection functions to catch errors that might be
    kicked (ConnectionTimeout, for instance).

    This function performs a semi-infinite loop, pausing for 5 seconds after
    each failed function call, up to a maximum of 5 minutes.

    Parameters
    ----------
    func : `method`
        The Confluence class method to be wrapped
    pause : `int` or `float`, optional
        The number of seconds to wait in between retries to connect.
        [Default: 5]
    timeout : `int` or `float`, optional
        The total time (in minutes) to continue retrying before returning None
        [Default: 5]

    Returns
    -------
    `Any`
        The return value of `func` -- or None if unable to run `func`
    """
    # Starting value
    i = 1

    while True:
        try:
            # Nominal function return
            return func(*args, **kwargs)
        except Exception as exception:
            # If any fail, notify, pause, and retry
            # TODO: Maybe limit the scope of `Exception` to urllib3/request?
            print(f"\nExecution of `{func.__name__}` failed because of "
                  f"{exception.__context__}\nWaiting {pause} seconds "
                  f"before starting attempt #{(i := i+1)}")
            sleep(pause)
        # Give up after `timeout` minutes...
        if i >= int(timeout*60/pause):
            break
    return None
