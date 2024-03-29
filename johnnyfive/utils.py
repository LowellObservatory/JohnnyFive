# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
#  Created on 14-Feb-2022
#
#  @author: tbowers

"""Utility Functions and Variables

This module is part of the JohnnyFive package, written at Lowell Observatory.

This module contains various utility routines and global variables from across
the package.
"""

# Built-In Libraries
import argparse
import os
import shutil
import time
import warnings

# 3rd Party Libraries
from googleapiclient.errors import HttpError
from google.auth.exceptions import TransportError
import httplib2
from pkg_resources import resource_filename
import requests
from slack_sdk.errors import SlackApiError

# Lowell Libraries
import ligmos

# Internal Imports


# Set API Components
__all__ = ["PermissionWarning", "print_dict", "safe_service_connect"]


class PermissionWarning(UserWarning):
    """PermissionWarning
    Subclass of UserWarning that is more specific to the case of permissions
    """


# Classes to hold useful information
class Paths:
    """Paths

    [extended_summary]
    """

    # Main data & config directories
    config = resource_filename("johnnyfive", "config")
    images = resource_filename("johnnyfive", "images")
    gmail_token = os.path.join(config, "gmail_token.json")
    gmail_creds = os.path.join(config, "gmail_credentials.json")


class authTarget(ligmos.utils.classes.baseTarget):
    """authTarget Extension of LIGMOS baseTarget

    Adds specified attributes used in JohnnyFive to silence LIGMOS's
    "Setting orphan object key" messages
    """

    def __init__(self):
        super().__init__()
        self.access_token = None
        self.apiKey = None
        self.apiSecret = None
        self.tokenKey = None
        self.tokenSecret = None


def authenticate_gmail():
    """authenticate_gmail Console Script for authenticating Gmail

    This will be a command-line script for doing the interactive authentication
    for Gmail needed to keep the tokens, etc. up to date.

    TODO: Actually implement this function!
    """
    print("Whee!  We're going to authenticate gamil!")


def install_conffiles(args=None):
    """install_conffiles Console Script for installing configuration files

    This function is designed to install the (secret) configuration files
    (e.g., gmail_credentials.json or johnnyfive.conf) into the proper
    config/ directory buried wherever on the filesystem.

    Parameters
    ----------
    args : `Any`, optional
        The arguments passed from the command line [Default: None]
    """
    # Use argparse for the Command-Line Script
    parser = argparse.ArgumentParser(description="Install (Secret) Configuration Files")
    parser.add_argument(
        "files", type=str, nargs="+", help="The configuration files to install"
    )
    parser.add_argument(
        "-d",
        "--dry_run",
        default=False,
        action="store_true",
        help="Dry run only, do not actually copy.",
    )
    res = parser.parse_args(args)

    # Now, loop through the files privided
    for file in res.files:
        # Skip things that aren't files
        if not isinstance(file, str) or not os.path.isfile(file):
            print(f"Argument {file} is not a file... skipping.")
            continue

        # Print out what's planned to do, and actually copy if specified
        print(f"Copying {file} to {Paths.config} ...")
        if not res.dry_run:
            shutil.copy2(file, Paths.config)


def read_ligmos_conffiles(confname, conffile="johnnyfive.conf"):
    """read_ligmos_conffiles Read a configuration file using LIGMOS

    Having this as a separate function may be a bit of an overkill, but it
    makes it easier to keep the ligmos imports only in one place, and
    simplifies the code elsewhere.

    Parameters
    ----------
    confname : `str`
        Name of the table within the configuration file to parse
    conffile : `str`
        Name of the configuration file to parse

    Returns
    -------
    `ligmos.utils.classes.baseTarget`
        An object with arrtibutes matching the keys in the associated
        configuration file.
    """
    ligconf = ligmos.utils.confparsers.rawParser(os.path.join(Paths.config, conffile))
    ligconf = ligmos.workers.confUtils.assignConf(
        ligconf[confname], authTarget, backfill=True
    )
    return ligconf


def print_dict(dd, indent=0, di=4):
    """print_dict Print a dictionary in tree format

    You know how sometimes you get these nested dictionaries, and they're a
    pain to visually parse?  This routine prints out the contents of a
    dictionary in tree format to make it easier to see which fields are
    contained in others, etc.

    NOTE: Currently, dictionary keys are limited to length 12 `str`

    Parameters
    ----------
    dd : `dict`
        The dictionary to print
    indent : `int`, optional
        The initial indentation for the tree [Default: 0]
    di: `int`, optional
        The incremental indentation for each layer of the tree [Default: 4]
    """
    if not isinstance(dd, dict):
        print("Input not a dictionary.")
        return

    for key, value in dd.items():
        # Recursive for nested dictionaries
        if isinstance(value, dict):
            print(f"{' '*indent}{key:12s}:")
            print_dict(value, indent + di)
        else:
            print(f"{' '*indent}{key:12s}: {value}")


def safe_service_connect(func, *args, pause=5, nretries=5, **kwargs):
    """safe_service_connect Safely connect to Service (error-catching)

    Wrapper for Service-connection functions to catch errors that might be
    kicked (ConnectionTimeout, for instance).

    This function performs a semi-infinite loop, pausing for `pause` seconds
    after each failed function call, up to a maximum of `nretries` retries.

    Parameters
    ----------
    func : `method`
        The Service connection method to be wrapped
    pause : `int` or `float`, optional
        The number of seconds to wait in between retries to connect.
        [Default: 5]
    nretries : `int`, optional
        The total number of times to retry connecting before returning None
        [Default: 10]

    Returns
    -------
    `Any`
        The return value of `func` -- or None if unable to run `func`
    """
    for i in range(1, nretries + 1):

        # Nominal function return
        try:
            return func(*args, **kwargs)

        # This is a network error... retry
        except (
            ConnectionError,
            TransportError,
            httplib2.error.ServerNotFoundError,
        ) as exception:
            print(
                f"\nWarning: Execution of `{func.__name__}` failed because of:\n{exception}"
            )
            if (i := i + 1) <= nretries:
                print(
                    f"Waiting {pause} seconds before starting attempt #{i}/{nretries}"
                )
                time.sleep(pause)
            else:
                raise ConnectionError(
                    f"Could not connect to service after {nretries} attempts."
                ) from exception

        # This is for a Service error (premissions, etc.), no retry
        except requests.exceptions.HTTPError as exception:
            print(
                f"\nWarning: Execution of `{func.__name__}` failed because of:\n{exception}"
                "\nAborting..."
            )
            break

        # Gmail service error, no retry and pass the exception upward
        except HttpError as exception:
            warnings.warn(
                f"Caught Gmail error... passing up.  {type(exception).__name__}"
            )
            raise exception

        # Slack service error, no retry and pass the exception upward
        except SlackApiError as exception:
            warnings.warn(
                f"Caught Slack error... passing up.  {type(exception).__name__}"
            )
            raise exception

    # If not successful, return None
    return None
