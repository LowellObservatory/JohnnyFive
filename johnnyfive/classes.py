# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
#  Created on 25 Feb 2020
#
#  @author: rhamilton

"""One line description of module.

Further description.
"""

from __future__ import division, print_function, absolute_import


class emailSNMP(object):
    def __init__(self):
        self.host = None
        self.port = 465
        self.user = None
        self.password = None
        self.fromname = None
        self.toaddr = None
        self.footer = None
        self.enabled = True
