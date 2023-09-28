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
from importlib import resources
import os
import shutil
import time
import warnings

# 3rd Party Libraries
import atlassian.errors
import googleapiclient.errors
import google.auth.exceptions
import httplib2
import requests
import slack_sdk.errors

# Lowell Libraries
import ligmos

# Internal Imports


# Set API Components
__all__ = ["safe_service_connect", "print_dict", "proper_print"]


# Classes to hold useful information
class Paths:
    """Paths

    [extended_summary]
    """

    # Main data & config directories
    config = resources.files("johnnyfive") / "config"
    images = resources.files("johnnyfive") / "images"
    gmail_token = config / "gmail_token.json"
    gmail_creds = config / "gmail_credentials.json"


class authTarget(ligmos.utils.classes.baseTarget):
    """Extension of LIGMOS baseTarget class

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


def install_conffiles(args=None):
    """Console Script for installing configuration files

    This function is designed to install the (secret) configuration files
    (`e.g.`, ``gmail_credentials.json`` or ``johnnyfive.conf``) into the proper
    ``config/`` directory buried wherever on the filesystem.

    Parameters
    ----------
    args : Any, optional
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
    """Read a configuration file using LIGMOS

    Having this as a separate function may be a bit of an overkill, but it
    makes it easier to keep the ligmos imports only in one place, and
    simplifies the code elsewhere.

    Parameters
    ----------
    confname : str
        Name of the table within the configuration file to parse
    conffile : str
        Name of the configuration file to parse

    Returns
    -------
    :class:`ligmos.utils.classes.baseTarget`
        An object with arrtibutes matching the keys in the associated
        configuration file.
    """
    ligconf = ligmos.utils.confparsers.rawParser(os.path.join(Paths.config, conffile))
    ligconf = ligmos.workers.confUtils.assignConf(
        ligconf[confname], authTarget, backfill=True
    )
    return ligconf


def print_dict(dd, indent=0, di=4):
    """Print a dictionary in tree format

    You know how sometimes you get these nested dictionaries, and they're a
    pain to visually parse?  This routine prints out the contents of a
    dictionary in tree format to make it easier to see which fields are
    contained in others, etc.

    NOTE: Currently, dictionary keys are limited to length 12 `str`

    Parameters
    ----------
    dd : dict
        The dictionary to print
    indent : int, optional
        The initial indentation for the tree [Default: 0]
    di: int, optional
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


def safe_service_connect(func, *args, pause=5, nretries=5, logger=None, **kwargs):
    """Safely connect to Service (includes error-catching)

    Wrapper for Service-connection functions to catch errors that might be
    kicked (``ConnectionTimeout``, for instance).

    This function performs a semi-infinite loop, pausing for ``pause`` seconds
    after each failed function call, up to a maximum of ``nretries`` retries.

    Parameters
    ----------
    func : :obj:`method`
        The Service connection method to be wrapped
    pause : :obj:`int` or :obj:`float`, optional
        The number of seconds to wait in between retries to connect.
        [Default: 5]
    nretries : int, optional
        The total number of times to retry connecting before returning None
        [Default: 10]
    logger : :obj:`logging.Logger`, optional
        The logger object for logging  [Default: None]

    Returns
    -------
    Any
        The return value of ``func`` -- or None if unable to run ``func``
    """

    # Now, for the actual function...
    for i in range(1, nretries + 1):
        # Nominal function return
        try:
            return func(*args, **kwargs)

        # This is a network error... retry
        except (
            ConnectionError,
            google.auth.exceptions.TransportError,
            httplib2.error.ServerNotFoundError,
        ) as exception:
            proper_print(
                f"Execution of `{func.__name__}` failed because of network error."
                f"\n{exception}",
                "error",
                logger,
            )

            if i < nretries:
                proper_print(
                    f"Waiting {pause} seconds before starting attempt #{i+1}/{nretries}",
                    "info",
                    logger,
                )
                time.sleep(pause)
            else:
                proper_print(
                    f"Could not connect to service after {nretries} attempts.",
                    "error",
                    logger,
                )
                break

        # This is for a Service error (premissions, etc.), no retry
        except requests.exceptions.HTTPError as exception:
            proper_print(
                f"Execution of `{func.__name__}` failed because of HTTP error."
                f"\n{type(exception).__name__}  {exception.args}",
                "error",
                logger,
            )
            proper_print("Aborting...", "except", logger)
            raise exception
            break

        # # Gmail service error, no retry and pass the exception upward
        # except googleapiclient.errors.HttpError as exception:
        #     proper_print(
        #         f"Caught Gmail HTTP error... passing up.  {type(exception).__name__}",
        #         "except",
        #         logger,
        #     )
        #     raise exception

        # Slack service error, no retry and pass the exception upward
        except slack_sdk.errors.SlackApiError as exception:
            proper_print(
                f"Caught Slack API error... passing up.  {type(exception).__name__}",
                "except",
                logger,
            )
            raise exception

        # Confluence service error, no retry and pass the excepetion upward
        except atlassian.errors.ApiError as exception:
            proper_print(
                f"Caught Atlassian API Error... passing up.  {type(exception).__name__}",
                "except",
                logger,
            )
            raise exception

        # Google RefreshError occurs when the gmail_token.json to too old
        except google.auth.exceptions.RefreshError as exception:
            proper_print(
                "Google Token Refresh Error.\n"
                f"\tDescription: {exception.args[0]}\n"
                "\tIf the reason is 'Token has been expired or revoked', then run\n"
                "\t`j5_authenticate_gmail` to refresh the token.",
                "error",
                logger,
            )
            raise exception

    # If not successful, return None
    return None


def proper_print(msg, level, logger=None):
    """Log if logger, else print to stdout

    _extended_summary_

    Parameters
    ----------
    msg : str
        The message to convey
    level : str
        The logging level.  One of [``info``,``warn``,``except``]
    logger : :obj:`logging.Logger`, optional
        The logger object for logging  [Default: None]
    """
    if level == "info":
        if logger is None:
            print(msg)
        else:
            logger.info(msg)
    elif level == "warn":
        if logger is None:
            warnings.warn(msg)
        else:
            logger.warning(msg)
    elif level == "error":
        if logger is None:
            warnings.warn(f"EXCEPTION: {msg}")
        else:
            logger.error(msg)
    elif level == "except":
        if logger is None:
            warnings.warn(f"EXCEPTION: {msg}")
        else:
            logger.exception(msg)
