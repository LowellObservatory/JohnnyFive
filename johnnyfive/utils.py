# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
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
import collections.abc
import configparser
import dataclasses
import importlib.resources
import logging
import pathlib
import shutil
import time
import typing
import warnings

# 3rd Party Libraries
import atlassian.errors
import google.auth.exceptions
import httplib2
import requests
import slack_sdk.errors

# Internal Imports


# Set API Components
__all__ = [
    "J5Error",
    "print_dict",
    "proper_print",
    "read_config_section",
    "safe_service_connect",
]

type ConfigValue = str | int | bool | None | list[str | bool | None]
type LogLevel = typing.Literal["info", "warn", "error", "except"]
_CONFIG_FIELD_ALIASES = {
    "api_key": "apikey",
    "api_secret": "apisecret",
    "token_key": "tokenkey",
    "token_secret": "tokensecret",
}


# Define error classes
class J5Error(Exception):
    """J5Error Class

    Base JohnnyFive error class
    """


# Classes to hold useful information
@dataclasses.dataclass
class Paths:
    """Paths

    Centralizes paths to packaged configuration and image resources.
    """

    # Main data & config directories
    config = importlib.resources.files("johnnyfive") / "config"
    images = importlib.resources.files("johnnyfive") / "images"
    gmail_token = config / "gmail_token.json"
    gmail_creds = config / "gmail_credentials.json"


@dataclasses.dataclass
class BaseTarget:
    """Configuration values shared by J5 service integrations."""

    name: ConfigValue = None
    host: ConfigValue = None
    port: ConfigValue = 22
    type: ConfigValue = None
    user: ConfigValue = None
    protocol: ConfigValue = None
    password: ConfigValue = None
    enabled: ConfigValue = False


@dataclasses.dataclass
class AuthTarget(BaseTarget):
    """Configuration target with the credentials used by JohnnyFive.

    Additional values in the configuration section are retained as attributes.
    """

    access_token: ConfigValue = None
    token: ConfigValue = None
    api_key: ConfigValue = None
    api_secret: ConfigValue = None
    token_key: ConfigValue = None
    token_secret: ConfigValue = None


def assign_conf(
    conf: configparser.SectionProxy,
    obj: type[BaseTarget],
    backfill: bool = False,
    debug: bool = False,
) -> BaseTarget:
    """Copy parsed configuration values to a target instance.

    Given an arbitrary class reference and a parsed configuration file (conf),
    assign keys from the latter into parameters in the former.

    Assumes that ALL keys in the class are present in the configuration; if
    they aren't, then they're set to ```None``` and caught/announced in the
    ```KeyError``` exception below.

    If 'backfill' is False, parameters that are in the *configuration file*
    but not in the given class are *ignored* completely.  If True,
    they're added to the given class with a warning.

    Parameters
    ----------
    conf : configparser.SectionProxy
        Configuration section to convert.
    obj : type[BaseTarget]
        Target class to instantiate.
    backfill : bool, optional
        Whether to retain keys not predefined by ``obj``.
    debug : bool, optional
        Whether to print missing predefined keys.

    Returns
    -------
    BaseTarget
        Populated configuration target.
    """
    # Make an instance of our given object/class
    classy = obj()

    consumed_keys: set[str] = set()
    for key in classy.__dict__:
        try:
            config_key = key if key in conf else _CONFIG_FIELD_ALIASES.get(key, key)
            value = conf[config_key]
            consumed_keys.add(config_key)
            setattr(classy, key, val_checks(value))
        except KeyError:
            if debug:
                print(f"Missing expected configuration key {key}")
            setattr(classy, key, None)

    if backfill:
        for orphan in set(conf.keys()) - consumed_keys:
            if debug:
                orphan_value = val_checks(conf[orphan])
                print(f"Setting orphan object key {orphan} to {orphan_value}")
            setattr(classy, orphan, val_checks(conf[orphan]))

    return classy


def install_conffiles(args: collections.abc.Sequence[str] | None = None) -> None:
    """Console Script for installing configuration files

    This function is designed to install the (secret) configuration files
    (`e.g.`, ``gmail_credentials.json`` or ``johnnyfive.conf``) into the proper
    ``config/`` directory buried wherever on the filesystem.

    Parameters
    ----------
    args : :obj:~`typing.Any`, optional
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
        if not isinstance(file, str) or not pathlib.Path(file).is_file():
            print(f"Argument {file} is not a file... skipping.")
            continue

        # Print out what's planned to do, and actually copy if specified
        print(f"Copying {file} to {Paths.config} ...")
        if not res.dry_run:
            shutil.copy2(file, Paths.config)


def read_config_section(confname: str, conffile: str = "johnnyfive.conf") -> BaseTarget:
    """Read a JohnnyFive configuration section into an attribute object.

    Parameters
    ----------
    confname : :obj:`str`
        Name of the table within the configuration file to parse
    conffile : :obj:`str`
        Name of the configuration file to parse

    Returns
    -------
    :class:`BaseTarget`
        An object with attributes matching the keys in the associated
        configuration file.
    """
    try:
        config = raw_parser(Paths.config / conffile)
        return assign_conf(config[confname], AuthTarget, backfill=True)
    except KeyError as err:
        raise J5Error(
            f"Configuration key {confname} not present.\n"
            "Try installing configuration files via j5 utilities."
        ) from err
    except (OSError, configparser.Error) as err:
        raise J5Error(
            "Unexpected error occurred while reading in configuration file.\n"
            f"\n{type(err).__name__}  {err.args}"
        ) from err


def read_ligmos_conffiles(
    confname: str, conffile: str = "johnnyfive.conf"
) -> BaseTarget:
    """Backward-compatible alias for :func:`read_config_section`.

    JohnnyFive no longer depends on ligmos; new code should use
    :func:`read_config_section`.
    """
    return read_config_section(confname, conffile)


def print_dict(
    dd: collections.abc.Mapping[str, typing.Any], indent: int = 0, di: int = 4
) -> None:
    """Print a dictionary in tree format

    You know how sometimes you get these nested dictionaries, and they're a
    pain to visually parse?  This routine prints out the contents of a
    dictionary in tree format to make it easier to see which fields are
    contained in others, etc.

    NOTE: Currently, dictionary keys are limited to length 12 `str`

    Parameters
    ----------
    dd : :obj:`dict`
        The dictionary to print
    indent : :obj:`int`, optional
        The initial indentation for the tree [Default: 0]
    di: :obj:`int`, optional
        The incremental indentation for each layer of the tree [Default: 4]
    """
    if not isinstance(dd, collections.abc.Mapping):
        print("Input not a dictionary.")
        return

    for key, value in dd.items():
        # Recursive for nested dictionaries
        if isinstance(value, collections.abc.Mapping):
            print(f"{' '*indent}{key:12s}:")
            print_dict(value, indent + di)
        else:
            print(f"{' '*indent}{key:12s}: {value}")


def proper_print(
    msg: str, level: LogLevel, logger: logging.Logger | None = None
) -> None:
    """Log if logger, else print to stdout

    Selects a logger method or standard warning/output based on ``level``.

    Parameters
    ----------
    msg : :obj:`str`
        The message to convey
    level : {"info", "warn", "error", "except"}
        The logging level.  One of [``info``,``warn``,``except``]
    logger : :obj:`~logging.Logger`, optional
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
    else:
        raise ValueError(f"Unsupported logging level: {level!r}")


def raw_parser(confname: str | pathlib.Path) -> configparser.ConfigParser:
    """Parse an INI-style configuration file.

    Parameters
    ----------
    confname : str | pathlib.Path
        Path to the configuration file.

    Returns
    -------
    configparser.ConfigParser
        Parsed configuration, which is empty if the file cannot be opened.
    """
    config = configparser.ConfigParser()
    try:
        with open(confname, "r", encoding="utf-8") as f_obj:
            config.read_file(f_obj)
    except OSError as err:
        raise J5Error(f"Configuration file {confname} could not be read.") from err

    return config


def safe_service_connect(
    func: collections.abc.Callable[..., typing.Any],
    *args: typing.Any,
    pause: int | float = 5,
    nretries: int = 5,
    logger: logging.Logger | None = None,
    **kwargs: typing.Any,
) -> typing.Any:
    """Safely connect to Service (includes error-catching)

    Wrapper for Service-connection functions to catch errors that might be
    kicked (``ConnectionTimeout``, for instance).

    This function performs a semi-infinite loop, pausing for ``pause`` seconds
    after each failed function call, up to a maximum of ``nretries`` retries.

    Parameters
    ----------
    func : :obj:`~typing.Callable`
        The Service connection method to be wrapped
    pause : :obj:`int` or :obj:`float`, optional
        The number of seconds to wait in between retries to connect.
        [Default: 5]
    nretries : :obj:`int`, optional
        The total number of times to retry connecting before returning None
        [Default: 10]
    logger : :obj:`~logging.Logger`, optional
        The logger object for logging  [Default: None]

    Returns
    -------
    :obj:`~typing.Any`
        The return value of ``func`` -- or None if unable to run ``func``
    """

    if nretries < 1:
        raise ValueError("nretries must be at least 1.")
    if pause < 0:
        raise ValueError("pause must not be negative.")

    function_name = getattr(func, "__name__", func.__class__.__name__)

    # Now, for the actual function...
    for i in range(1, nretries + 1):
        # Nominal function return
        try:
            return func(*args, **kwargs)

        # This is a network error... retry
        except (
            ConnectionError,
            TimeoutError,
            google.auth.exceptions.TransportError,
            httplib2.error.ServerNotFoundError,
            requests.exceptions.ReadTimeout,
        ) as err:
            proper_print(
                f"Execution of `{function_name}` failed because of network error."
                f"\n{err}",
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
        except requests.exceptions.HTTPError as err:
            proper_print(
                f"Execution of `{function_name}` failed because of HTTP error."
                f"\n{type(err).__name__}  {err.args}",
                "error",
                logger,
            )
            proper_print("Aborting...", "except", logger)
            raise err

        # # Gmail service error, no retry and pass the exception upward
        # except googleapiclient.errors.HttpError as exception:
        #     proper_print(
        #         f"Caught Gmail HTTP error... passing up.  {type(exception).__name__}",
        #         "except",
        #         logger,
        #     )
        #     raise exception

        # Slack service error, no retry and pass the exception upward
        except slack_sdk.errors.SlackApiError as err:
            proper_print(
                f"Caught Slack API error... passing up.  {type(err).__name__}",
                "except",
                logger,
            )
            raise err

        # Confluence service error, no retry and pass the excepetion upward
        except atlassian.errors.ApiError as err:
            proper_print(
                f"Caught Atlassian API Error... passing up.  {type(err).__name__}",
                "except",
                logger,
            )
            raise err

        # Google RefreshError occurs when the gmail_token.json to too old
        except google.auth.exceptions.RefreshError as err:
            proper_print(
                "Google Token Refresh Error.\n"
                f"\tDescription: {err.args[0]}\n"
                "\tIf the reason is 'Token has been expired or revoked', then run\n"
                "\t`j5_authenticate_gmail` to refresh the token.",
                "error",
                logger,
            )
            raise err

    # If not successful, raise error
    raise J5Error("Unspecified error")


def val_checks(kval: str) -> str | bool | None | list[str | bool | None]:
    """Convert comma-separated configuration values to Python values.

    Parameters
    ----------
    kval : str
        Raw configuration value.

    Returns
    -------
    str | bool | None | list[str | bool | None]
        A scalar for one value or a list for multiple values, with literal
        ``true``, ``false``, and ``none`` converted to their Python values.
    """
    # It'll always be a string by this point, so it should always
    #   have a .split() method.  If not, someone else has mucked about
    #   with the configuration object before it got here.
    kval = kval.strip().split(",")

    # Trim off leading/trailing whitespace for each. Also make sure
    #    that it's a list, no matter what, so we can itterate over it.
    kval = [kv.strip() for kv in kval]

    # kval is now definitely a list
    allval = []
    for val in kval:
        # Some icky type checks
        if val.lower() == "none":
            nkval = None
        elif val.lower() == "false":
            nkval = False
        elif val.lower() == "true":
            nkval = True
        else:
            nkval = val
        # Put it into a list in case there's more than one
        allval.append(nkval)

    # If there's just one thing that we found, return it alone. Otherwise
    #   return the full list of stuff
    if len(allval) == 1:
        nkval = allval[0]
    else:
        nkval = allval

    return nkval
