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

# Internal Imports


# Classes to hold useful information
class Paths:
    """ Paths

    [extended_summary]
    """
    # Main data & config directories
    config = pkg_files('JohnnyFive.config')
