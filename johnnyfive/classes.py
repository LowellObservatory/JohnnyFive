# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 25 Feb 2020
#
#  @author: rhamilton

"""One line description of module.

Further description.
"""

from __future__ import division, print_function, absolute_import


class emailSNMP:
    """Store SMTP connection and message configuration.

    Attributes
    ----------
    host : str | None
        SMTP server host name.
    port : int
        SMTP server port.
    """

    def __init__(self) -> None:
        """Initialize an SMTP configuration with safe defaults."""
        self.host = None
        self.port = 465
        self.user = None
        self.password = None
        self.fromname = None
        self.toaddr = None
        self.footer = None
        self.enabled = True
