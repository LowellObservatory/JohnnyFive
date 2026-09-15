# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 23-Sep-2021
#
#  @author: tbowers

"""Confluence communication module

Confluence API Documentation:
        https://atlassian-python-api.readthedocs.io/index.html
"""

# Built-In Libraries
import collections.abc
import logging
import typing

# 3rd Party Libraries
from atlassian.confluence import ConfluenceServer
import requests

# Internal Imports
import johnnyfive.utils

# Set API Components
__all__ = ["ConfluencePage"]


class ConfluencePage:
    """ConfluencePage Class for a single Confluence Page

    Provides permission-aware operations for one Confluence page.

    Parameters
    ----------
    space : :obj:`str`
        The name of the Confluence space for this page
    page_title : :obj:`str`
        The page title
    instance : :class:`~atlassian.confluence.ConfluenceServer`, optional
        An existing Confluence object instance to be used instead of
        reinstantiating a new Confluence object for communication and
        authentication.  [Default: None]
    use_oauth : :obj:`bool`, optional
        Use bearer-token authentication instead of username/password. The
        existing name is retained for compatibility and accepts a Data Center
        OAuth 2.0 access token or personal access token. [Default: False]
    logger : :obj:`~logging.Logger`, optional
        The logger object for logging  [Default: None]
    """

    def __init__(
        self,
        space: str,
        page_title: str,
        instance: ConfluenceServer | None = None,
        use_oauth: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize a page wrapper and fetch its metadata.

        Parameters
        ----------
        space : str
            Confluence space key.
        page_title : str
            Page title within ``space``.
        instance : ConfluenceServer | None, optional
            Existing authenticated client.
        use_oauth : bool, optional
            Whether to create a bearer-token client.
        logger : logging.Logger | None, optional
            Logger used for service errors.
        """
        # Initialize instance variables
        self.space = space
        self.title = page_title
        self.logger = logger
        self.exists = False
        self.page_id: str | None = None
        self.attachment_url: str | None = None

        # Set up the Confluence object instance
        self.confluence = (
            setup_confluence(use_oauth=use_oauth) if instance is None else instance
        )
        self.space_perms = self._set_permdict()

        # Set the class metadata based on this page
        self._set_metadata()

    def add_comment(self, comment: str) -> None:
        """Add a comment to the Confluence page

        Sometimes it's helpful to include a comment at the bottom of the
        Confluence page.  These will be signed by Nanni.  This method adds
        such to a page.

        Parameters
        ----------
        comment : :obj:`str`
            The comment to be left on the page.
        """
        if not self._check_perm("COMMENT", "add a comment"):
            return

        johnnyfive.utils.safe_service_connect(
            self.confluence.add_comment, self.page_id, comment, logger=self.logger
        )

    def add_label(self, label: str) -> None:
        """Add a label to the Confluence page

        Sometimes it's helpful to have a label on a Confluence page for
        searching or sorting.  This method adds such to a page.

        Parameters
        ----------
        label : :obj:`str`
            The label to be added to the page
        """
        if not self._check_perm("EDITSPACE", "add a label"):
            return

        johnnyfive.utils.safe_service_connect(
            self.confluence.set_page_label, self.page_id, label, logger=self.logger
        )

    def attach_file(
        self,
        filename: str,
        name: str | None = None,
        content_type: str | None = None,
        comment: str | None = None,
    ) -> None:
        """Attach a file to this page

        Wrapper for the Confluence method attach_file() that includes the
        page ID of this object and is wrapped in utils.safe_service_connect().

        Parameters
        ----------
        filename : :obj:`str`
            Filename of the attachment
        name : :obj:`str`, optional
            Display name for this attachment [Default: None]
        content_type : :obj:`str`, optional
            MIME content type [Default: None]
        comment : :obj:`str`, optional
            Additional comment or description to be included [Default: None]
        """
        if not self._check_perm("CREATEATTACHMENT", "create an attachment"):
            return

        johnnyfive.utils.safe_service_connect(
            self.confluence.attach_file,
            filename,
            name=name,
            content_type=content_type,
            page_id=self.page_id,
            comment=comment,
            logger=self.logger,
        )

    def create(
        self,
        page_body: str,
        parent_id: str | None = None,
        representation: str = "storage",
    ) -> None:
        """Create a brand new Confluence page

        Summon from the depths of computing a new page.

        Parameters
        ----------
        page_body : :obj:`str`
            The body of the new Confluence page.
        parent_id : :obj:`str`, optional
            The parent page to place this under.  If none given, the new page
            will be created at the root of ``self.space``. [Default: None]
        representation : :obj:`str`, optional
            The Confluence body representation to use. Storage XHTML is the
            default and recommended representation. [Default: "storage"]
        """
        if not self._check_perm("EDITSPACE", "create a page"):
            return

        # Check if it exists before we try anything
        if self.exists:
            johnnyfive.utils.proper_print(
                "Can't create a page that already exists!", "info", self.logger
            )
            return

        response = johnnyfive.utils.safe_service_connect(
            self.confluence.create_page,
            self.space,
            self.title,
            page_body,
            parent_id=parent_id,
            representation=representation,
            logger=self.logger,
        )
        # A successful create response already contains the new page ID. Avoid
        # a second title lookup unless a nonstandard response omits it.
        if isinstance(response, collections.abc.Mapping) and isinstance(
            response.get("id"), str
        ):
            self._set_metadata_from_page_id(response["id"])
        else:
            self._set_metadata()

    def delete_attachment(self, filename: str) -> None:
        """Delete an attachment from this page

        Wrapper for the Confluence method delete_attachment() that includes the
        page ID of this object and is wrapped in utils.safe_service_connect().

        An attahment may be deleted using either the filename, or by passing
        ``None`` or "" to the filename and specifying the attachment_id.

        Parameters
        ----------
        filename : :obj:`str`
            Filename of the attachment to delete
        """
        if not self._check_perm("REMOVEATTACHMENT", "remove an attachment"):
            return

        attachments = johnnyfive.utils.safe_service_connect(
            self.confluence.get_attachments_from_content,
            self.page_id,
            filename=filename,
            limit=2,
            logger=self.logger,
        )
        results = (
            attachments.get("results", [])
            if isinstance(attachments, collections.abc.Mapping)
            else []
        )
        matching_attachments = [
            attachment
            for attachment in results
            if isinstance(attachment, collections.abc.Mapping)
            and attachment.get("title") == filename
        ]
        if not matching_attachments:
            johnnyfive.utils.proper_print(
                f"Attachment {filename!r} was not found on page {self.page_id}.",
                "warn",
                self.logger,
            )
            return
        if len(matching_attachments) > 1:
            raise johnnyfive.utils.J5Error(
                f"More than one current attachment is named {filename!r}."
            )

        attachment_id = matching_attachments[0].get("id")
        if not isinstance(attachment_id, str):
            raise johnnyfive.utils.J5Error(
                f"Attachment {filename!r} did not include a REST content ID."
            )
        # Supplying only an attachment content ID uses the client's REST delete
        # path, rather than its legacy json/removeattachment.action helper.
        johnnyfive.utils.safe_service_connect(
            self.confluence.delete_attachment, attachment_id, logger=self.logger
        )

    def get_page_attachments(
        self, limit: int = 200, all_pages: bool = False
    ) -> list[dict[str, typing.Any]]:
        """Retrieve the page attachments

        Return REST attachment metadata, up to ``limit`` in length. Set
        ``all_pages`` to retrieve every attachment in pages of ``limit``.

        Parameters
        ----------
        limit : :obj:`int`, optional
            Number of attachments per REST page and, unless ``all_pages`` is
            set, the maximum total to return. [Default: 200]
        all_pages : :obj:`bool`, optional
            Whether to follow REST pagination until every attachment is
            collected. [Default: False]

        Returns
        -------
        list[dict[str, Any]]
            REST attachment objects.
        """
        if limit < 1:
            raise ValueError("Attachment page limit must be positive.")

        attachments: list[dict[str, typing.Any]] = []
        start = 0
        while True:
            response = johnnyfive.utils.safe_service_connect(
                self.confluence.get_attachments_from_content,
                self.page_id,
                start=start,
                limit=limit,
                logger=self.logger,
            )
            results = (
                response.get("results", [])
                if isinstance(response, collections.abc.Mapping)
                else []
            )
            page = [item for item in results if isinstance(item, dict)]
            attachments.extend(page)
            if not all_pages or len(page) < limit:
                return attachments
            start += len(page)

    def get_page_contents(self) -> str:
        """Retrieve the page contents in HTML-ish format

        Either for curiosity or for modification, get the page contents, which
        live in the `body.storage` portion of the `get_page_by_id` response.

        Returns
        -------
        :obj:`str`
            The HTML-ish body of the confluence page.
        """
        contents = johnnyfive.utils.safe_service_connect(
            self.confluence.get_page_by_id,
            self.page_id,
            expand="body.storage",
            logger=self.logger,
        )
        # Extract the contents from the return object
        return contents["body"]["storage"]["value"]

    def smite(self) -> None:
        """smite Kill with extreme prejudice

        Remove the Confluence page and update the instance metadata to reflect
        the new state.
        """
        if not self._check_perm("REMOVEPAGE", "remove a page"):
            return

        johnnyfive.utils.safe_service_connect(
            self.confluence.remove_page, self.page_id, logger=self.logger
        )
        self._set_metadata_from_page_id(None)

    def update_contents(
        self,
        body: str,
        representation: str = "storage",
        minor_edit: bool = False,
        version_comment: str | None = None,
        always_update: bool = False,
    ) -> None:
        """Update the contents of the Confluence page

        Update the page by replacing the existing content with new.  The idea
        for this method is to be used in concert with :func:``get_page_contents``
        to obtain a page, modify it, then replace it.

        Parameters
        ----------
        body : :obj:`str`
            The new page contents to upload to Confluence.
        representation : str, optional
            Body representation supplied with ``body``. [Default: "storage"]
        minor_edit : bool, optional
            Whether Confluence should mark this as a minor edit. [Default: False]
        version_comment : str | None, optional
            Version-history comment for the update. [Default: None]
        always_update : bool, optional
            Skip the client content equality check and always create a new
            version. [Default: False]
        """
        if not self._check_perm("EDITSPACE", "update a page"):
            return

        johnnyfive.utils.safe_service_connect(
            self.confluence.update_page,
            self.page_id,
            self.title,
            body,
            representation=representation,
            minor_edit=minor_edit,
            version_comment=version_comment,
            always_update=always_update,
            logger=self.logger,
        )

    # Internal Helper Functions ==========================#
    def _check_perm(self, perm_key: str, perm_action: str) -> bool:
        """Check the premissions dictionary for a particular action

        Check the ``perm_key`` in the permissions dictionary to see whether the
        requested action is permitted.

        The wrinkle is that if the user does not have permission to see
        permissions, the perm_dict will be empty -- meaning we don't know
        if an action will be permitted.  In this case, we press forward and
        expect that `utils.safe_service_connect()` will take care of any errors
        that crop up.

        Parameters
        ----------
        perm_key : :obj:`str`
            The key in perm_dict to look for
        perm_action : :obj:`str`
            The action that is requested by the calling function.

        Returns
        -------
        :obj:`bool`
            True for perform action, False for not
        """
        perm_val = self.space_perms.get(perm_key, None)

        # If the value is explicitely False, warn as such
        if perm_val is False:
            johnnyfive.utils.proper_print(
                f"User {self.confluence.username} does not have permission "
                f"to {perm_action} in space {self.space}.",
                "warn",
                self.logger,
            )
            return False

        # If value is None, permission preflight is disabled; let the REST
        # operation itself enforce the authenticated user's permissions.
        if perm_val is None:
            return True

        return True

    def _set_metadata(self) -> None:
        """Set the various instance metadata

        Especially after a page is created or deleted, this method updates the
        various instance attributes to keep current.
        """
        response = johnnyfive.utils.safe_service_connect(
            self.confluence.get_page_by_title,
            self.space,
            self.title,
            limit=2,
            logger=self.logger,
        )
        results = (
            response.get("results", [])
            if isinstance(response, collections.abc.Mapping)
            else []
        )
        if len(results) > 1:
            raise johnnyfive.utils.J5Error(
                f"Multiple pages named {self.title!r} exist in space {self.space!r}."
            )
        page_id = (
            results[0].get("id")
            if results and isinstance(results[0], collections.abc.Mapping)
            else None
        )
        self._set_metadata_from_page_id(page_id if isinstance(page_id, str) else None)

    def _set_metadata_from_page_id(self, page_id: str | None) -> None:
        """Set page metadata from a known REST content ID.

        Parameters
        ----------
        page_id : str | None
            Page content ID returned by Confluence, or ``None`` when absent.

        Returns
        -------
        None
            Instance metadata is updated in place.
        """
        self.exists = page_id is not None
        self.page_id = page_id
        self.attachment_url = (
            None
            if self.page_id is None
            else f"{self.confluence.url}download/attachments/{self.page_id}/"
        )

    def _set_permdict(self) -> dict[str, bool]:
        """Disable permission enumeration for REST-based automation clients.

        Current Confluence REST deployments can require space-administrator
        privileges to enumerate all permissions. J5 only needs the narrower
        privileges for each page operation, so it lets those REST operations
        perform the authoritative authorization check instead.

        Returns
        -------
        dict[str, bool]
            Empty map indicating that permission preflight is disabled.
        """
        return {}


# Internal Functions =========================================================#
def setup_confluence(use_oauth: bool = False) -> ConfluenceServer:
    """Set up the Confluence class instance

    Reads in the confluence.conf configuration file, which contains the URL,
    username, password, and/or bearer-token information.

    .. note::
        Confluence Data Center supports personal access tokens from 7.9 and
        OAuth 2.0 access tokens from 7.17. Both use a bearer header.

    Parameters
    ----------
    use_oauth : :obj:`bool`, optional
        Use bearer-token authentication. The parameter name is retained for
        compatibility. [Default: False]

    Returns
    -------
    confluence : :class:`~atlassian.confluence.ConfluenceServer`
        Confluence class, initialized with credentials
    """
    # Read the setup
    setup = johnnyfive.utils.read_config_section("confluenceSetup")

    # Instantiate a Server client with an OAuth or personal bearer token
    if use_oauth:
        session = requests.Session()
        session.headers["Authorization"] = f"Bearer {setup.access_token}"
        return ConfluenceServer(url=setup.host, session=session)

    # Otherwise, return a Server client instantiated with username/password.
    return ConfluenceServer(
        url=setup.host, username=setup.user, password=setup.password
    )
