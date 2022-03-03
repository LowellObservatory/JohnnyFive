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

This module primarily trades in... utility?
"""

# Built-In Libraries
from time import sleep
import warnings

# 3rd Party Libraries
from googleapiclient.errors import HttpError
from google.auth.exceptions import TransportError
import httplib2
from importlib_resources import files as pkg_files
import requests

# Lowell Libraries
from ligmos import utils as lig_utils, workers as lig_workers

# Internal Imports


class PermissionWarning(UserWarning):
    """PermissionWarning
    Subclass of UserWarning that is more specific to the case of permissions
    """


# Classes to hold useful information
class Paths:
    """ Paths

    [extended_summary]
    """
    # Main data & config directories
    config = pkg_files('JohnnyFive.config')
    images = pkg_files('JohnnyFive.images')


def custom_formatwarning(msg, *args, **kwargs):
    """custom_formatwarning Custom Warning Formatting

    Ignore everything except the message

    Parameters
    ----------
    msg : `str`
        The warning message

    Returns
    -------
    `str`
        The formatted warning string
    """
    return f"Warning: {str(msg)}\n"


def read_ligmos_conffiles(confname, conffile='johnnyfive.conf'):
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
    ligconf = lig_utils.confparsers.rawParser(Paths.config.joinpath(conffile))
    ligconf = lig_workers.confUtils.assignConf(
        ligconf[confname], lig_utils.classes.baseTarget, backfill=True
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
            print_dict(value, indent+di)
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
                sleep(pause)
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

    # If not successful, return None
    return None
