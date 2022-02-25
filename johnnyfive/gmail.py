# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
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
from email.mime import audio, base, image, multipart, text
import mimetypes
import os

# 3rd Party Libraries
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Internal Imports
from . import utils


# This scope is for sending email using the OAuth2 library
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']


# Set API Components
__all__ = ['GmailMessage', 'GetMessages']


class GmailMessage():
    """GmailMessage Class for a single Gmail Message

    _extended_summary_

        Parameters
    ----------
    toaddr : `str` or `list`
        The intended recipient(s) of the email message
    subject : `str`
        The subject of the email message
    message_text : `str`
        The body text of the email message (as a single string with optional
        newlines.)
    fromname : `str`, optional
        Display Name of the sender (i.e. which bot) [Default: None]
    fromaddr : `str`, optional
        Sender email address [Default: Value from [gmailSetup]]
    """
    def __init__(self, toaddr, subject, message_text, fromname=None, fromaddr=None):
        # Load default `fromaddr`` if None passed in
        if not fromaddr:
            fromaddr = utils.read_ligmos_conffiles('gmailSetup').user

        # Initialize the Gmail connection
        self.service = setup_gmail()

        # Build the container for a multipart MIME message
        self.message = multipart.MIMEMultipart()
        self.message['to'] = toaddr if isinstance(toaddr, str) else ','.join(toaddr)
        self.message['from'] = f"{fromname} <{fromaddr}>" if fromname else fromaddr
        self.message['subject'] = subject

        # Place the text into the message
        self.message.attach( text.MIMEText(message_text))

    def add_attachment(self, file):
        """add_attachment _summary_

        _extended_summary_

        Parameters
        ----------
        file : `str`
            Filename of the attachment
        """
        # For the attachment, guess the MIME type for reading it in
        content_type, encoding = mimetypes.guess_type(file)

        # Set unknown type
        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'

        # Case out the content type
        main_type, sub_type = content_type.split('/', 1)
        if main_type == 'text':
            with open(file, 'rb') as fp:
                attachment = text.MIMEText(fp.read(), _subtype=sub_type)
        elif main_type == 'image':
            with open(file, 'rb') as fp:
                attachment = image.MIMEImage(fp.read(), _subtype=sub_type)
        elif main_type == 'audio':
            with open(file, 'rb') as fp:
                attachment = audio.MIMEAudio(fp.read(), _subtype=sub_type)
        else:
            with open(file, 'rb') as fp:
                attachment = base.MIMEBase(main_type, sub_type)
                attachment.set_payload(fp.read())

        # Add the attachment to the email message
        attachment.add_header('Content-Disposition', 'attachment',
                           filename=os.path.basename(file))
        self.message.attach(attachment)

    def send(self):
        """send Send the GmailMessage

        _extended_summary_

        Returns
        -------
        `dict`
            The sent message object
        """
        # Take the message object, and 64-bit encode it properly for sending
        encoded_message = base64.urlsafe_b64encode(self.message.as_bytes())
        # The sendable message is a dictionary containing the raw decoded thing
        sendable_message = {'raw': encoded_message.decode()}

        # Go into a possibly infinite loop!
        # TODO: Make this NOT an infinite loop
        while not self.service:
            self.service = setup_gmail()

        # Try to send the message (API: users.messages.send)
        try:
            message = self.service.users().messages().send(userId="me",
                                            body=sendable_message).execute()
            #print(f"Message Id: {message['id']}")
            return message
        except HttpError as error:
            print(f"An error occurred: {error}")
            return None


class GetMessages():
    """GetMessages Get Gmail messages corresponding to given criteria

    _extended_summary_

    Parameters
    ----------
    label : `str`, optional
        The Gmail label of messages to find [Default: None]
    after : `str`, optional
        Date after which to search for messages. Must be in YYYY/MM/DD format.
        [Default: None]
    before : `str`, optional
        Date before which to search for messages. Must be in YYYY/MM/DD format.
        [Default: None]
    """
    def __init__(self, label=None, after=None, before=None):
       # Initialize basic stuff
        self.label_list = None

        # Initialize the Gmail connection
        self.service = setup_gmail()
        self.label_id = self._lableId_from_labelName(label)
        self.query = build_query(after_date=after, before_date=before)

        # Get the list of matching messages (API: users.messages.list)
        results = self.service.users().messages().list(userId='me',
                                    labelIds=[self.label_id], q=self.query,
                                    maxResults=500).execute()
        self.message_list = results.get('messages', [])

    def render_message(self, message_id):
        """render_message Retrieve and render a message by ID#

        Gmail mnessages are stored in a JSON-like structure that must be
        parsed out to get the tasty nougat center.

        Parameters
        ----------
        message_id : `str`
            The ['id'] field of an entry in self.message_list

        Returns
        -------
        `dict`
            Dictionary containing the subject, sender, date, and body of
            the message.
        """
        try:
            # Get the message, then start parsing (API: users.messages.get)
            results = self.service.users().messages().get(userId='me',
                                            id=message_id).execute()
            payload = results['payload']
            headers = payload['headers']

            # Look for Subject and Sender Email in the headers
            for d in headers:
                if d['name'] == 'Subject':
                    subject = d['value']
                if d['name'] == 'From':
                    sender = d['value']
                if d['name'] == 'Date':
                    date = d['value']

            # The Body of the message is in Encrypted format -- decode it.
            #  Get the data and decode it with base 64 decoder.
            data = payload['body']['data']
            data = data.replace("-","+").replace("_","/")
            decoded_data = base64.b64decode(data)

            # `decoded_data` is in lxml format; parse with BeautifulSoup
            body = BeautifulSoup(decoded_data , "lxml").body()
            body = body[0].text

        # TODO: Actually deal with this exception properly.
        except Exception as e:
            print('Gack.')
            raise e

        # Return a dictionary with the plain-text components of this message
        return dict(subject=subject, sender=sender, date=date, body=body)

    def update_msg_labels(self, message_id, add_labels=None, remove_labels=None):
        """update_msg_labels Update the labels for a message by ID#

        _extended_summary_

        Parameters
        ----------
        message_id : `str`
            The ['id'] field of an entry in self.message_list
        add_labels : `list`, optional
            The list of label IDs to add to this message [Default: None]
        remove_labels : `list`, optional
            The list of label IDs to remove from this message [Default: None]

        Returns
        -------
        `Any`
            Uh, the Message object from Gmail... probably just return nothing?
        """
        if not add_labels and not remove_labels:
            print("No labels to change.")
            return None

        # Convert Label Names to Label IDs
        add_label_ids, remove_label_ids = [], []
        if add_labels:
            for label in add_labels:
                add_label_ids.append(self._lableId_from_labelName(label))
        if remove_labels:
            for label in remove_labels:
                remove_label_ids.append(self._lableId_from_labelName(label))

        # Build the label dictionary to send to Gmail
        body = {}
        if add_label_ids:
            body['addLabelIds'] = add_label_ids
        if remove_label_ids:
            body['removeLabelIds'] = remove_label_ids

        try:
            # Modify message lables (API: users.messages.modify)
            return self.service.users().messages().modify(userId='me',
                                            id=message_id, body=body).execute()
        # TODO: Actually deal with this exception properly.
        except Exception as e:
            print('Gack.')
            raise e

    def _lableId_from_labelName(self, name):
        """_lableId_from_labelName Get the Label ID from the Label Name

        _extended_summary_

        Parameters
        ----------
        name : `str`
            Label name

        Returns
        -------
        `str`
            Label ID
        """
        # Only do this once
        if not self.label_list:
            # Get the list of labels for the "me" account (API: users.labels.list)
            results = self.service.users().labels().list(userId='me').execute()
            self.label_list = results.get('labels', [])

        # If there are no labels, return None
        if not self.label_list:
            print('Whoops, no labels found.')
            return None

        label_id = None
        # Go through the labels, and return the ID matching the name
        for label in self.label_list:
            if label['name'] == name:
                label_id = label['id']

        return label_id


# Newer OAUTH Routines =======================================================#
def setup_gmail(interactive=False):
    """setup_gmail Initialize the GMail API (via OAuth)

    [extended_summary]

    NOTE: The first time this is run on a machine, it will open a webpage for
          authorizing the API.  All subsequent runs will be silent.

    Parameters
    ----------
    interactive : `bool`, optional
        Is this session interactive?  Relates to how to deal with toke
        refresh.  [Default: False]

    Returns
    -------
    `googleapiclient.discovery.Resource`
        The GMail API service object for consumption by other routines
    """
    creds = None
    if os.path.exists(
            token_fn := utils.Paths.config.joinpath('gmail_token.json') ):
        creds = Credentials.from_authorized_user_file(token_fn, SCOPES)

    # If there are no (valid) credentials available, lauch browser to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                utils.Paths.config.joinpath('gmail_credentials.json'), SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(token_fn, 'w', encoding='utf-8') as token:
            token.write(creds.to_json())

    # Try logging into the GMail API.  If error, print error & return None
    try:
        # Call the Gmail API
        return build('gmail', 'v1', credentials=creds)
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f'An error occurred: {error}')
        return None


# Utility Functions ==========================================================#
def build_query(after_date=None, before_date=None):
    """build_query Build the query string for users.messages.list

    _extended_summary_

    Parameters
    ----------
    after_date : `str`
        Date after which to search for messages.
    before_date : `str`
        Date before which to search for messages.

    Returns
    -------
    `str`
        The appropriate query string
    """
    q = ''
    if after_date:
        q = q + f" after:{after_date}"
    if before_date:
        q = q + f" before:{before_date}"
    return q
