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

# Internal Imports
from . import utils


# Set API Components
__all__ = ['ConfluencePage']


class ConfluencePage:
    """ConfluencePage Class for a single Confluence Page

    _extended_summary_

    Parameters
    ----------
    space : `str`
        The name of the Confluence space for this page
    page_title : `str`
        The page title
    instance : ``, optional
        An existing Confluence influence, to be used in the case of many
        instances of this class used in short order [Default: None]
    """
    def __init__(self, space, page_title, instance=None):
        self.space = space
        self.title = page_title
        self.instance = setup_confluence() if not \
                            isinstance(instance, Confluence) else instance
        # Set the class metadata
        self._set_metadata()

    def add_comment(self, comment):
        """add_comment Add a comment to the Confluence page

        Sometimes it's helpful to include a comment at the bottom of the
        Confluence page.  These will be signed by Nanni.  This method adds
        such to a page.

        Parameters
        ----------
        comment : `str`
            The comment to be left on the page.
        """
        safe_confluence_connect(self.instance.add_comment,
                                self.page_id, comment)

    def add_label(self, label):
        """add_label Add a label to the Confluence page

        Sometimes it's helpful to have a label on a Confluence page for
        searching or sorting.  This method adds such to a page.

        Parameters
        ----------
        label : `str`
            The label to be added to the page
        """
        safe_confluence_connect(self.instance.set_page_label,
                                self.page_id, label)

    def attach_file(self, filename, name=None, content_type=None,
                    comment=None):
        """attach_file Attach a file to this page

        Wrapper for the Confluence method attach_file() that includes the
        page ID of this object and is wrapped in safe_confluence_connect().

        Parameters
        ----------
        filename : `str`
            Filename of the attachment
        name : `str`, optional
            Display name for this attachment [Default: None]
        content_type : `str`, optional
            MIME content type [Default: None]
        comment : `str`, optional
            Additional comment or description to be included [Default: None]
        """
        # Wrap the underlying method with safe_confluence_connect()
        safe_confluence_connect(self.instance.attach_file,
                                filename, name=name,
                                content_type=content_type,
                                page_id=self.page_id, comment=comment)

    def create(self, page_body, parent_id=None):
        """create Create a brand new Confluence page

        Summon from the depths of computing a new page.

        Parameters
        ----------
        page_body : `str`
            The body of the new Confluence page.
        parent_id : `str`, optional
            The parent page to place this under.  If none given, the new page
            will be created at the root of `self.space`. [Default: None]
        """
        # Check if it exists before we try anything
        if self.exists:
            print("Can't create a page that already exists!")
            return

        safe_confluence_connect(self.instance.create_page, self.space,
                                self.title, page_body, parent_id=parent_id,
                                representation='wiki', editor='v1')
        # Set the instance metadata (exists, page_id, etc.)
        self._set_metadata()

    def delete_attachment(self, filename):
        """delete_attachment Delete an attachment from this page

        Wrapper for the Confluence method delete_attachment() that includes the
        page ID of this object and is wrapped in safe_confluence_connect().

        Parameters
        ----------
        filename : `str`
            Filename of the attachment to delete
        """
        # Wrap the underlying method with safe_confluence_connect()
        safe_confluence_connect(self.instance.delete_attachment,
                                self.page_id, filename)

    def get_page_contents(self):
        """get_page_contents Retrieve the page contents in HTML-ish format

        Either for curiosity or for modification, get the page contents, which
        live in the `body.storage` portion of the `get_page_by_id` response.

        Returns
        -------
        `str`
            The HTML-ish body of the confluence page.
        """
        contents = safe_confluence_connect(self.instance.get_page_by_id,
                                          self.page_id,
                                          expand='body.storage')
        # Extract the contents from the return object
        return contents['body']['storage']['value']

    def smite(self):
        """smite Kill with extreme prejudice

        Remove the Confluence page and update the instance metadata to reflect
        the new state.
        """
        safe_confluence_connect(self.instance.remove_page, self.page_id)
        self._set_metadata()

    def update_contents(self, body):
        """update_contents Update the contents of the Confluence page

        Update the page by replacing the existing content with new.  The idea
        for this method is to be used in concert with `get_page_contents` to
        obtain a page, modify it, then replace it.

        Parameters
        ----------
        body : `str`
            The new page contents to upload to Confluence.

        Returns
        -------
        _type_
            _description_
        """
        safe_confluence_connect(self.instance.update_page, self.page_id,
                                self.title, body)

    def _set_metadata(self):
        """_set_metadata Set the various instance metadata

        Especially after a page is created or deleted, this method updates the
        various instance attributes to keep current.
        """
        self.exists = safe_confluence_connect(self.instance.page_exists,
                                              self.space, self.title)

        # Page-Specific Information
        self.page_id = None if not self.exists else \
            safe_confluence_connect(self.instance.get_page_id,
                                    self.space, self.title)
        self.attachment_url = None if not self.exists else \
            f"{self.instance.url}download/attachments/{self.page_id}/"


# Internal Functions =========================================================#
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
    # Read the setup
    setup = utils.read_ligmos_conffiles('confluenceSetup')

    # Return the Confluence instance
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
                  f"{exception.__context__}  or {exception}\nWaiting {pause} "
                  f"seconds before starting attempt #{(i := i+1)}")
            sleep(pause)
        # Give up after `timeout` minutes...
        if i >= int(timeout*60/pause):
            break
    return None
