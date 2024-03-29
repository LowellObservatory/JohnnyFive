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
import warnings

# 3rd Party Libraries
from atlassian import Confluence
import requests

# Internal Imports
from johnnyfive import utils


# Set API Components
__all__ = ["ConfluencePage"]


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

    def __init__(self, space, page_title, instance=None, use_oauth=False):
        self.space = space
        self.title = page_title
        self.instance = (
            setup_confluence(use_oauth=use_oauth)
            if not isinstance(instance, Confluence)
            else instance
        )
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
        if not self._check_perm("COMMENT", "add a comment"):
            return

        utils.safe_service_connect(self.instance.add_comment, self.page_id, comment)

    def add_label(self, label):
        """add_label Add a label to the Confluence page

        Sometimes it's helpful to have a label on a Confluence page for
        searching or sorting.  This method adds such to a page.

        Parameters
        ----------
        label : `str`
            The label to be added to the page
        """
        if not self._check_perm("EDITSPACE", "add a label"):
            return

        utils.safe_service_connect(self.instance.set_page_label, self.page_id, label)

    def attach_file(self, filename, name=None, content_type=None, comment=None):
        """attach_file Attach a file to this page

        Wrapper for the Confluence method attach_file() that includes the
        page ID of this object and is wrapped in utils.safe_service_connect().

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
        if not self._check_perm("CREATEATTACHMENT", "create an attachment"):
            return

        utils.safe_service_connect(
            self.instance.attach_file,
            filename,
            name=name,
            content_type=content_type,
            page_id=self.page_id,
            comment=comment,
        )

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
        if not self._check_perm("EDITSPACE", "create a page"):
            return

        # Check if it exists before we try anything
        if self.exists:
            print("Can't create a page that already exists!")
            return

        utils.safe_service_connect(
            self.instance.create_page,
            self.space,
            self.title,
            page_body,
            parent_id=parent_id,
            representation="wiki",
            editor="v1",
        )
        # Set the instance metadata (exists, page_id, etc.)
        self._set_metadata()

    def delete_attachment(self, filename):
        """delete_attachment Delete an attachment from this page

        Wrapper for the Confluence method delete_attachment() that includes the
        page ID of this object and is wrapped in utils.safe_service_connect().

        An attahment may be deleted using either the filename, or by passing
        `None` or "" to the filename and specifying the attachment_id.

        Parameters
        ----------
        filename : `str`
            Filename of the attachment to delete
        """
        if not self._check_perm("REMOVEATTACHMENT", "remove an attachment"):
            return

        utils.safe_service_connect(
            self.instance.delete_attachment, self.page_id, filename
        )

    def get_page_attachments(self, limit=200):
        """get_page_attachments _summary_

        Return a list of page attachment IDs, up to `limit` in length.

        Parameters
        ----------
        limit : `int`, optional
            The number of attachments to return [Default: 200]

        Returns
        -------
        `list`
            List of Confluence attachment IDs
        """
        return utils.safe_service_connect(
            self.instance.get_attachments_from_content, self.page_id, limit=limit
        )

    def get_page_contents(self):
        """get_page_contents Retrieve the page contents in HTML-ish format

        Either for curiosity or for modification, get the page contents, which
        live in the `body.storage` portion of the `get_page_by_id` response.

        Returns
        -------
        `str`
            The HTML-ish body of the confluence page.
        """
        contents = utils.safe_service_connect(
            self.instance.get_page_by_id, self.page_id, expand="body.storage"
        )
        # Extract the contents from the return object
        return contents["body"]["storage"]["value"]

    def smite(self):
        """smite Kill with extreme prejudice

        Remove the Confluence page and update the instance metadata to reflect
        the new state.
        """
        if not self._check_perm("REMOVEPAGE", "remove a page"):
            return

        utils.safe_service_connect(self.instance.remove_page, self.page_id)
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
        if not self._check_perm("EDITSPACE", "update a page"):
            return

        utils.safe_service_connect(
            self.instance.update_page, self.page_id, self.title, body
        )

    def _check_perm(self, perm_key, perm_action):
        """_check_perm Check the perm_dict for a particular action

        Check the `perm_ley` in the permissions dictionary to see whether the
        requested action is permitted.

        The wrinkle is that if the user does not have permission to see
        permissions, the perm_dict will be empty -- meaning we don't know
        if an action will be permitted.  In this case, we press forward and
        expect that `utils.safe_service_connect()` will take care of any errors
        that crop up.

        Parameters
        ----------
        perm_key : `str`
            The key in perm_dict to look for
        perm_action : `str`
            The action that is requested by the calling function.

        Returns
        -------
        `bool`
            True for perform action, False for not
        """
        perm_val = self.space_perms.get(perm_key, None)

        # If the value is explicitely False, warn as such
        if perm_val is False:
            warnings.warn(
                f"User {self.uname} does not have permission "
                f"to {perm_action} in space {self.space}.",
                utils.PermissionWarning,
            )
            return False

        # If value is None, no permission check was performed, proceed
        if perm_val is None:
            warnings.warn(
                "Permissions check is disabled... hoping for the best.",
                utils.PermissionWarning,
            )

        return True

    def _set_metadata(self):
        """_set_metadata Set the various instance metadata

        Especially after a page is created or deleted, this method updates the
        various instance attributes to keep current.
        """
        self.exists = utils.safe_service_connect(
            self.instance.page_exists, self.space, self.title
        )

        # Page-Specific Information
        self.page_id = (
            None
            if not self.exists
            else utils.safe_service_connect(
                self.instance.get_page_id, self.space, self.title
            )
        )
        self.attachment_url = (
            None
            if not self.exists
            else f"{self.instance.url}download/attachments/{self.page_id}/"
        )

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
        perms = utils.safe_service_connect(
            self.instance.get_space_permissions, self.space
        )

        # Check to see if the authenticated user can view permissions
        if not perms:
            warnings.warn(
                f"User {self.uname} needs permission to view "
                f"permissions in space {self.space}.   Contact "
                "your Confluence administrator.",
                utils.PermissionWarning,
            )

        perm_dict = {}
        for perm in perms:
            # Set this permission as false... will update to True if needed
            perm_dict[perm["type"]] = False
            for space_perm in perm["spacePermissions"]:
                if space_perm["userName"] == self.uname:
                    perm_dict[perm["type"]] = True

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
    setup = utils.read_ligmos_conffiles("confluenceSetup")

    # If we are using OAUTH, instantiate a Confluence object with it
    if use_oauth:
        s = requests.Session()
        s.headers["Authorization"] = f"Bearer {setup.access_token}"
        return Confluence(url=setup.host, session=s)

    # Else, return a Confluence object instantiated with username/password
    return Confluence(url=setup.host, username=setup.user, password=setup.password)
