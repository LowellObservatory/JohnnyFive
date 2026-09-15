# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 07-Mar-2022
#
#  @author: tbowers

"""Init File"""

# Imports for signal and log handling
from pathlib import Path
from typing import IO
import warnings

__all__ = ["ConfluencePage", "GmailMessage", "GetMessages", "SlackChannel"]

# Load API into base namespace
from .confluence import *  # noqa
from .gmail import *  # noqa
from .slack import *  # noqa
from .utils import *  # noqa


def short_warning(
    message: Warning | str,
    category: type[Warning],
    filename: str,
    lineno: int,
    file: IO[str] | None = None,
    line: str | None = None,
) -> str:
    """Format a warning as a concise single line.

    Parameters
    ----------
    message : Warning | str
        Warning text or warning instance.
    category : type[Warning]
        Warning category.
    filename : str
        Source filename.
    lineno : int
        Source line number.
    file : IO[str] | None, optional
        Unused output stream accepted for the warnings hook protocol.
    line : str | None, optional
        Unused source line accepted for the warnings hook protocol.

    Returns
    -------
    str
        Formatted warning line.
    """
    del file, line
    return f" {category.__name__}: {message} ({Path(filename).name}:{lineno})\n"


warnings.formatwarning = short_warning
