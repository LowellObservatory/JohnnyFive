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

# 3rd Party Libraries
from importlib_resources import files as pkg_files

# Lowell Libraries
from ligmos import utils as lig_utils, workers as lig_workers

# Internal Imports


# Classes to hold useful information
class Paths:
    """ Paths

    [extended_summary]
    """
    # Main data & config directories
    config = pkg_files('JohnnyFive.config')


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
                            ligconf[confname],
                            lig_utils.classes.baseTarget,
                            backfill=True)
    return ligconf
