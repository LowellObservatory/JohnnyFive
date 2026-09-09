# -*- coding: utf-8 -*-
#
# SPDX-License-Identifier: MPL-2.0
#
#  Created on 15 Feb 2022
#
#  @author: tbowers

"""Gmail Communication module

Further description.

Gmail API Documentation:
        https://developers.google.com/gmail/api/reference/rest/v1/
"""

# Built-In Libraries
import base64
import email.mime.audio
import email.mime.base
import email.mime.image
import email.mime.multipart
import email.mime.text
import json
import logging
import mimetypes
import os
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

# 3rd Party Libraries
from bs4 import BeautifulSoup
import googleapiclient.discovery
import googleapiclient.errors
import google_auth_oauthlib.flow
import google.auth.exceptions
import google.auth.transport.requests
import google.oauth2.credentials

# Internal Imports
import johnnyfive.utils


# This scope is for sending email using the OAuth2 library
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


# Set API Components
__all__ = ["GmailMessage", "GetMessages"]


class GmailMessage:
    """Class for a single Gmail Message

    Builds MIME messages and sends them through an authenticated Gmail service.

    Parameters
    ----------
    toaddr : :obj:`str` or :obj:`list`
        The intended recipient(s) of the email message
    subject : :obj:`str`
        The subject of the email message
    message_text : :obj:`str`
        The body text of the email message (as a single string with optional
        newlines.)
    fromname : :obj:`str`, optional
        Display Name of the sender (i.e. which bot) [Default: None]
    fromaddr : :obj:`str`, optional
        Sender email address [Default: Value from [gmailSetup]]
    interactive : :obj:`bool`, optional
        Whether to run this in interactive mode  (Default: False)
    logger : :obj:`~logging.Logger`, optional
        The logger object for logging  [Default: None]
    """

    def __init__(
        self,
        toaddr: str | list[str],
        subject: str,
        message_text: str,
        fromname: str | None = None,
        fromaddr: str | None = None,
        interactive: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        """Build a Gmail MIME message and initialize its API service.

        Parameters
        ----------
        toaddr : str | list[str]
            Recipient address or addresses.
        subject : str
            Email subject.
        message_text : str
            Plain-text body.
        fromname : str | None, optional
            Sender display name.
        fromaddr : str | None, optional
            Sender address; defaults to the J5 configuration value.
        interactive : bool, optional
            Whether OAuth authorization may open a browser.
        logger : logging.Logger | None, optional
            Logger used for service errors.
        """
        # Set the logger, if passed
        self.logger = logger

        # Load default `fromaddr`` if None passed in
        if not fromaddr:
            fromaddr = johnnyfive.utils.read_config_section("gmailSetup").user

        # Initialize the Gmail connection
        self.service = setup_gmail(interactive=interactive, logger=self.logger)

        # Build the container for a multipart MIME message
        self.message = email.mime.multipart.MIMEMultipart()
        self.message["to"] = toaddr if isinstance(toaddr, str) else ",".join(toaddr)
        self.message["from"] = f"{fromname} <{fromaddr}>" if fromname else fromaddr
        self.message["subject"] = subject

        # Place the text into the message
        self.message.attach(email.mime.text.MIMEText(message_text))

    def add_attachment(self, file: str | Path) -> None:
        """Add an attachment to the GMAIL message

        The attachment MIME type is inferred from its filename.

        Parameters
        ----------
        file : :obj:`str`
            Filename of the attachment
        """
        # For the attachment, guess the MIME type for reading it in
        content_type, encoding = mimetypes.guess_type(file)

        # Set unknown type
        if content_type is None or encoding is not None:
            content_type = "application/octet-stream"

        # Case out the content type
        main_type, sub_type = content_type.split("/", 1)
        if main_type == "text":
            with open(file, encoding="utf-8") as f_obj:
                attachment = email.mime.text.MIMEText(f_obj.read(), _subtype=sub_type)
        elif main_type == "image":
            with open(file, "rb") as f_obj:
                attachment = email.mime.image.MIMEImage(f_obj.read(), _subtype=sub_type)
        elif main_type == "audio":
            with open(file, "rb") as f_obj:
                attachment = email.mime.audio.MIMEAudio(f_obj.read(), _subtype=sub_type)
        else:
            with open(file, "rb") as f_obj:
                attachment = email.mime.base.MIMEBase(main_type, sub_type)
                attachment.set_payload(f_obj.read())

        # Add the attachment to the email message
        attachment.add_header(
            "Content-Disposition", "attachment", filename=os.path.basename(file)
        )
        self.message.attach(attachment)

    def send(self) -> dict[str, Any]:
        """Send the GmailMessage

        Encodes the MIME message and sends it through Gmail's API.

        Returns
        -------
        :obj:`dict`
            The sent message object
        """
        # Take the message object, and 64-bit encode it properly for sending
        encoded_message = base64.urlsafe_b64encode(self.message.as_bytes())
        # The sendable message is a dictionary containing the raw decoded thing
        sendable_message = {"raw": encoded_message.decode()}

        # If Gmail `Resource` was not returned earlier, try again
        if not self.service:
            self.service = setup_gmail(logger=self.logger)

        # Try to send the message (API: users.messages.send)
        try:
            return johnnyfive.utils.safe_service_connect(
                self.service.users()
                .messages()
                .send(userId="me", body=sendable_message)
                .execute,
                logger=self.logger,
            )
        except (googleapiclient.errors.HttpError, ConnectionError) as error:
            johnnyfive.utils.proper_print(
                f"An error occurred within GmailMessage.send(): {error}",
                "except",
                self.logger,
            )
            raise johnnyfive.utils.J5Error from error


class GetMessages:
    """Get Gmail messages corresponding to given criteria

    Queries Gmail messages and exposes helpers for rendering and relabeling them.

    Parameters
    ----------
    label : :obj:`str`, optional
        The Gmail label of messages to find [Default: None]
    after : :obj:`str`, optional
        Date after which to search for messages. Must be in YYYY/MM/DD format.
        (Default: None)
    before : :obj:`str`, optional
        Date before which to search for messages. Must be in YYYY/MM/DD format.
        (Default: None)
    interactive : :obj:`bool`, optional
        Whether to run this in interactive mode  (Default: False)
    logger : :obj:`logging.Logger`, optional
        The logger object for logging  [Default: None]
    """

    def __init__(
        self,
        label: str | None = None,
        after: str | None = None,
        before: str | None = None,
        interactive: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        """Connect to Gmail and collect messages matching search criteria.

        Parameters
        ----------
        label : str | None, optional
            Gmail label name used to filter messages.
        after : str | None, optional
            Inclusive lower date bound in ``YYYY/MM/DD`` form.
        before : str | None, optional
            Exclusive upper date bound in ``YYYY/MM/DD`` form.
        interactive : bool, optional
            Whether OAuth authorization may open a browser.
        logger : logging.Logger | None, optional
            Logger used for service errors.
        """
        # Initialize basic stuff
        self.label_list = None
        self.message_list = []
        self.logger = logger

        # Initialize the Gmail connection
        self.service = setup_gmail(interactive=interactive, logger=self.logger)

        # If we cannot connect to GMail, return here with an empty message_list
        if self.service is None:
            johnnyfive.utils.proper_print(
                "Cannot connect to GMail!", "error", self.logger
            )
            return

        self.label_id = self._label_id_from_name(label)
        self.query = self.build_query(after_date=after, before_date=before)

        # Get the list of matching messages (API: users.messages.list)
        if self.label_id:
            try:
                results = johnnyfive.utils.safe_service_connect(
                    self.service.users()
                    .messages()
                    .list(
                        userId="me",
                        labelIds=[self.label_id],
                        q=self.query,
                        maxResults=500,
                    )
                    .execute,
                    logger=self.logger,
                )
                self.message_list = results.get("messages", [])
            except (googleapiclient.errors.HttpError, ConnectionError) as error:
                johnnyfive.utils.proper_print(
                    f"An error occurred within GetMessages.__init__(): {error}",
                    "except",
                    self.logger,
                )

    def render_message(self, message_id: str) -> dict[str, str]:
        """Retrieve and render a message by ID#

        Gmail mnessages are stored in a JSON-like structure that must be
        parsed out to get the tasty nougat center.

        Parameters
        ----------
        message_id : :obj:`str`
            The ``['id']`` field of an entry in self.message_list

        Returns
        -------
        :obj:`dict`
            Dictionary containing the subject, sender, date, and body of
            the message.
        """
        payload: Mapping[str, Any] | None = None
        try:
            # Get the message, then start parsing (API: users.messages.get)
            results = johnnyfive.utils.safe_service_connect(
                self.service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute,
                logger=self.logger,
            )
            payload = results.get("payload", {})

        # If exception, print message and return empty values
        except (googleapiclient.errors.HttpError, ConnectionError) as error:
            johnnyfive.utils.proper_print(
                f"An error occurred within GetMessages.render_message(): {error}",
                "except",
                self.logger,
            )
        # Return empty dictionary if unsuccessful in connecting
        if not payload:
            return {"subject": "", "sender": "", "date": "", "body": ""}

        headers = {
            str(header.get("name", "")).lower(): str(header.get("value", ""))
            for header in payload.get("headers", [])
            if isinstance(header, Mapping)
        }

        # Return a dictionary with the plain-text components of this message
        return {
            "subject": headers.get("subject", ""),
            "sender": headers.get("from", ""),
            "date": headers.get("date", ""),
            "body": self._extract_message_body(payload),
        }

    @staticmethod
    def _iter_message_parts(part: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
        """Yield a MIME part and all of its nested child parts.

        Parameters
        ----------
        part : Mapping[str, Any]
            Gmail ``MessagePart`` object to traverse.

        Yields
        ------
        Mapping[str, Any]
            Each MIME part in depth-first order.
        """
        yield part
        for child in part.get("parts", []):
            if isinstance(child, Mapping):
                yield from GetMessages._iter_message_parts(child)

    @classmethod
    def _extract_message_body(cls, payload: Mapping[str, Any]) -> str:
        """Extract readable inline text from a Gmail MIME payload.

        Plain text is preferred when both ``text/plain`` and ``text/html``
        alternatives are present. Container and attachment parts without
        inline ``body.data`` are ignored.

        Parameters
        ----------
        payload : Mapping[str, Any]
            Top-level Gmail ``MessagePart`` payload.

        Returns
        -------
        str
            Decoded message text, or an empty string when no readable inline
            text part exists.
        """
        parts = list(cls._iter_message_parts(payload))
        for mime_type in ("text/plain", "text/html"):
            for part in parts:
                if part.get("mimeType", "").lower() != mime_type:
                    continue
                body = part.get("body", {})
                data = body.get("data") if isinstance(body, Mapping) else None
                if not isinstance(data, str) or not data:
                    continue

                padded_data = data + "=" * (-len(data) % 4)
                decoded = base64.urlsafe_b64decode(padded_data).decode(
                    "utf-8", errors="replace"
                )
                if mime_type == "text/plain":
                    return decoded
                return BeautifulSoup(decoded, "lxml").get_text(separator="\n", strip=True)

        return ""

    def update_msg_labels(
        self,
        message_id: str,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update the labels for a message by ID#

        Label names are resolved to Gmail label IDs before the update.

        Parameters
        ----------
        message_id : :obj:`str`
            The ``['id']`` field of an entry in self.message_list
        add_labels : :obj:`list`, optional
            The list of label IDs to add to this message [Default: None]
        remove_labels : :obj:`list`, optional
            The list of label IDs to remove from this message [Default: None]

        """
        if not add_labels and not remove_labels:
            johnnyfive.utils.proper_print("No labels to change.", "info", self.logger)

        # Convert Label Names to Label IDs
        add_label_ids, remove_label_ids = [], []
        if add_labels:
            for label in add_labels:
                add_label_ids.append(self._label_id_from_name(label))
        if remove_labels:
            for label in remove_labels:
                remove_label_ids.append(self._label_id_from_name(label))

        # Build the label dictionary to send to Gmail
        body = {}
        if add_label_ids:
            body["addLabelIds"] = add_label_ids
        if remove_label_ids:
            body["removeLabelIds"] = remove_label_ids

        try:
            # Modify message lables (API: users.messages.modify)
            return johnnyfive.utils.safe_service_connect(
                self.service.users()
                .messages()
                .modify(userId="me", id=message_id, body=body)
                .execute,
                logger=self.logger,
            )
        # If exception, print message
        except (googleapiclient.errors.HttpError, ConnectionError) as error:
            johnnyfive.utils.proper_print(
                f"An error occurred within GetMessages.update_msg_labels(): {error}",
                "except",
                self.logger,
            )
        # If unsuccessful in connecting, raise
        raise johnnyfive.utils.J5Error("Unsuccessful connection")

    def _label_id_from_name(self, name: str | None) -> str | None:
        """Get the Label ID from the Label Name

        The label list is retrieved once and cached for the instance.

        Parameters
        ----------
        name : :obj:`str`
            Label name

        Returns
        -------
        :obj:`str`
            Label ID
        """
        if not self.service:
            return None

        # Only do this once
        if not self.label_list:
            # Get the list of labels for the "me" account (API: users.labels.list)
            try:
                results = johnnyfive.utils.safe_service_connect(
                    self.service.users().labels().list(userId="me").execute,
                    logger=self.logger,
                )
                self.label_list = results.get("labels", [])
            except (googleapiclient.errors.HttpError, ConnectionError) as error:
                johnnyfive.utils.proper_print(
                    f"An error occurred within GetMessages._labelId_from_labelName(): {error}",
                    "except",
                    self.logger,
                )
                self.label_list = []

        # If there are no labels, return None
        if not self.label_list:
            johnnyfive.utils.proper_print(
                "Whoops, no labels found.", "warn", self.logger
            )
            return None

        label_id = None
        # Go through the labels, and return the ID matching the name
        for label in self.label_list:
            if label["name"] == name:
                label_id = label["id"]

        return label_id

    @staticmethod
    def build_query(
        after_date: str | None = None, before_date: str | None = None
    ) -> str:
        """build_query Build the query string for users.messages.list

        Date filters are formatted for Gmail's message-list query syntax.

        Parameters
        ----------
        after_date : :obj:`str`
            Date after which to search for messages.
        before_date : :obj:`str`
            Date before which to search for messages.

        Returns
        -------
        :obj:`str`
            The appropriate query string
        """
        query = ""
        if after_date:
            query = query + f" after:{after_date}"
        if before_date:
            query = query + f" before:{before_date}"
        return query


# Newer OAUTH Routines =======================================================#
def setup_gmail(
    interactive: bool = False, logger: logging.Logger | None = None
) -> googleapiclient.discovery.Resource:
    """Initialize the GMail API (via OAuth)

    Creates or refreshes the OAuth credentials used by the Gmail API.

    NOTE: The first time this is run on a machine, it will open a webpage for
          authorizing the API.  All subsequent runs will be silent.

    Parameters
    ----------
    interactive : :obj:`bool`, optional
        Is this session interactive?  Relates to how to deal with toke
        refresh.  [Default: False]
    logger : :obj:`~logging.Logger`, optional
        The logger object for logging  (Default: None)

    Returns
    -------
    :obj:`~googleapiclient.discovery.Resource`
        The GMail API service object for consumption by other routines
    """
    # Read in the credential token
    creds = None
    if os.path.exists(token_fn := johnnyfive.utils.Paths.gmail_token):
        try:
            creds = google.oauth2.credentials.Credentials.from_authorized_user_file(
                token_fn, SCOPES
            )
        except json.decoder.JSONDecodeError as err:
            raise johnnyfive.utils.J5Error(
                f"Cannot parse Gmail token in {token_fn}"
            ) from err

    # If there are no (valid) credentials available...
    if not creds or not creds.valid:
        # If just expired, refresh and move on
        if creds and creds.expired and creds.refresh_token:
            try:
                johnnyfive.utils.safe_service_connect(
                    creds.refresh,
                    google.auth.transport.requests.Request(),
                    logger=logger,
                )
            except (googleapiclient.errors.HttpError, ConnectionError) as err:
                johnnyfive.utils.proper_print(
                    f"An error occurred within setup_gmail(): {err}", "warn", logger
                )
            except google.auth.exceptions.RefreshError as err:
                raise johnnyfive.utils.J5Error(
                    f"{type(err).__name__} {err}\n"
                    "https://stackoverflow.com/questions/10576386/invalid-grant-trying-to-get-oauth-token-from-google\n"
                    "Try running j5_authenticate_gmail"
                ) from err

        # If running in `interactive`, lauch browser to log in
        elif interactive:
            johnnyfive.utils.proper_print("If interactive...", "info", logger)
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                johnnyfive.utils.Paths.gmail_creds, SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Otherwise, raise an exception and specify to run interactively
        else:
            errmsg = (
                "No Gmail credentials found.  You may need to run:\n"
                "\t`j5_install_conf`\n"
                "\tor to authenticate user, run (NOT in a container):\n"
                "\t`j5_authenticate_gmail`"
            )
            johnnyfive.utils.proper_print(
                errmsg,
                "error",
                logger,
            )
            raise johnnyfive.utils.J5Error(errmsg)

        # Save the credentials for the next run
        with open(token_fn, "w", encoding="utf-8") as token:
            token.write(creds.to_json())

    # Try building the GMail API service.  If error, print error & raise
    try:
        # Call the Gmail API
        johnnyfive.utils.proper_print("Calling the GMAIL API...", "info", logger)
        return googleapiclient.discovery.build("gmail", "v1", credentials=creds)
    except (
        googleapiclient.errors.HttpError,
        googleapiclient.errors.UnknownApiNameOrVersion,
    ) as err:
        # TODO(developer) - Handle errors from gmail API.
        johnnyfive.utils.proper_print(
            f"An error occurred within setup_gmail():\n{err}", "except", logger
        )
        raise johnnyfive.utils.J5Error from err


def authenticate_gmail(logger: logging.Logger | None = None) -> None:
    """Console Script for authenticating Gmail

    This is the command-line script for doing the interactive authentication
    for Gmail needed to keep the tokens, etc. up to date.  When/If there is
    a ``RefreshError`` kicked by one of the classes in this module, this script
    needs to be run on the command line `interactively` to remove the existing
    token and re-authenticate the user via a web browser.

    Console script::

        j5_authenticate_gmail

    Parameters
    ----------
    logger : :obj:`~logging.Logger`, optional
        The logger object for logging  (Default: None)
    """
    johnnyfive.utils.proper_print("Authenticate GMail...", "info", logger)
    # Remove the existing GMAIL TOKEN file, if extant...
    johnnyfive.utils.Paths.gmail_token.unlink(missing_ok=True)
    # Run setup
    setup_gmail(interactive=True)
