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
        self.uname = self.instance.username
        self.space_perms = self._set_permdict()

        # Set the class metadata based on this page
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
        if not self.space_perms['COMMENT']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  f" to comment in space {self.space}.")

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
        if not self.space_perms['EDITSPACE']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  f" to add a label in space {self.space}.")

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
        if not self.space_perms['CREATEATTACHMENT']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  " to create an attachment in space "
                                  f"{self.space}.")

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
        if not self.space_perms['EDITSPACE']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  f" to create a page in space {self.space}.")

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
        if not self.space_perms['REMOVEATTACHMENT']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  " to remove an attachment in space "
                                  f"{self.space}.")

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
        if not self.space_perms['REMOVEPAGE']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  f" to remove a page in space {self.space}.")

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
        if not self.space_perms['EDITSPACE']:
            raise PermissionError(f"User {self.uname} does not have permission"
                                  f" to update a page in space {self.space}.")

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

    def _set_permdict(self):
        """_set_permdict Create a dictionary of permissions

        This method creates a dictionary of permissions for this user in this
        space.  Each item in the dictionary is boolean based on the results of
        the method confluence.get_space_permissions().

        Returns
        -------
        `dict`
            The dictionary of permissions (boolean)
        """
        perms = safe_confluence_connect(self.instance.get_space_permissions,
                                        self.space)

        perm_dict = {}
        for perm in perms:
            # Set this permission as false... will update to True if needed
            perm_dict[perm['type']] = False
            for space_perm in perm['spacePermissions']:
                if space_perm['userName'] == self.uname:
                    perm_dict[perm['type']] = True

        return perm_dict


# Internal Functions =========================================================#
def setup_confluence(use_oauth=False):
    """setup_confluence Set up the Confluence class instance

    Reads in the confluence.conf configuration file, which contains the URL,
    username, and password (and/or OAUTH info).

    NOTE: For Confluence install version >= 7.9, can use OAUTH for
          authentication instead of username/password.

    Parameters
    ----------
    use_oauth : `bool`, optional
        Use the OAUTH authentication scheme?  [Default: False]

    Returns
    -------
    confluence : `atlassian.Confluence`
        Confluence class, initialized with credentials
    """
    # Read the setup
    setup = utils.read_ligmos_conffiles('confluenceSetup')

    # If we are using OAUTH, instantiate a Confluence object with it
    if use_oauth:
        oauth_dict = {'access_token': setup.access_token,
                      'access_token_secret': setup.access_token_secret,
                      'consumer_key': setup.consumer_key,
                      'key_cert': setup.key_cert}
        return Confluence(url=setup.host, oauth=oauth_dict)

    # Else, return a Confluence object instantiated with username/password
    return Confluence( url=setup.host,
                       username=setup.user,
                       password=setup.password )


def safe_confluence_connect(func, *args, pause=5, nretries=20, **kwargs):
    """safe_confluence_connect Safely connect to Confluence (error-catching)

    Wrapper for confluence-connection functions to catch errors that might be
    kicked (ConnectionTimeout, for instance).

    This function performs a semi-infinite loop, pausing for `5` seconds after
    each failed function call, up to a maximum of `20` retries.

    Parameters
    ----------
    func : `method`
        The Confluence class method to be wrapped
    pause : `int` or `float`, optional
        The number of seconds to wait in between retries to connect.
        [Default: 5]
    nretries : `int`, optional
        The total number of times to retry connecting before returning None
        [Default: 20]

    Returns
    -------
    `Any`
        The return value of `func` -- or None if unable to run `func`
    """
    for i in range(1,nretries+1):
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
    # Give up after `nretries`...
    return None
