# -*- coding: utf-8 -*-
#
#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
#  Created on 25 Feb 2020
#
#  @author: rhamilton, tbowers

"""GMail Communication module

Further description.
"""

# Built-In Libraries
from base64 import urlsafe_b64encode
from email.message import EmailMessage
from email.mime import audio, base, image, multipart, text
import mimetypes
import smtplib
import socket
import ssl
import os

# Google API
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Internal Imports
from johnnyfive import utils


# This scope is for sending email using the OAuth2 library
SCOPES = ['https://www.googleapis.com/auth/gmail.compose']


# Newer OAUTH Routines =======================================================#
def create_message(sender, to, subject, message_text):
    """create_message Create a message for an email

    Create a simple text message to be sent.  This routine does not include
    attachments.  For that, please use create_message_with_attachment().

    Parameters
    ----------
    sender : `str`
        Email address of the sender
    to : `str`
        Email address of the recipient
    subject : `str`
        The subject of the email message
    message_text : `str`
        The text of the email message

    Returns
    -------
    `dict`
        An object containing a base64url encoded email object
    """
    # Build the message as a MIMEText object
    message = text.MIMEText(message_text)
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    # 64-bit encoded message
    encoded_message = urlsafe_b64encode(message.as_bytes())
    # Return a dictionary containing the raw message
    return {'raw': encoded_message.decode()}


def create_message_with_attachment(sender, to, subject, message_text, file):
    """create_message_with_attachment Create message with attachment for email

    [extended_summary]

    Parameters
    ----------
    sender : `str`
        Email address of the sender
    to : `str`
        Email address of the recipient
    subject : `str`
        The subject of the email message
    message_text : `str`
        The text of the email message
    file : `str` or `pathlib.Path`
        The path to the file to be attached

    Returns
    -------
    `dict`
        An object containing a base64url encoded email object
    """
    # Build the container for the multipart MIME message
    message = multipart.MIMEMultipart()
    message['to'] = to
    message['from'] = sender
    message['subject'] = subject

    # Place the text into the message
    message.attach( text.MIMEText(message_text))

    # For the attachment, guess the MIME type for reading it in
    content_type, encoding = mimetypes.guess_type(file)

    # Set unknown type
    if content_type is None or encoding is not None:
        content_type = 'application/octet-stream'

    # Case out content type
    main_type, sub_type = content_type.split('/', 1)
    if main_type == 'text':
        with open(file, 'rb') as fp:
            msg = text.MIMEText(fp.read(), _subtype=sub_type)
    elif main_type == 'image':
        with open(file, 'rb') as fp:
            msg = image.MIMEImage(fp.read(), _subtype=sub_type)
    elif main_type == 'audio':
        with open(file, 'rb') as fp:
            msg = audio.MIMEAudio(fp.read(), _subtype=sub_type)
    else:
        with open(file, 'rb') as fp:
            msg = base.MIMEBase(main_type, sub_type)
            msg.set_payload(fp.read())

    # Add the attachment to the email message
    filename = os.path.basename(file)
    msg.add_header('Content-Disposition', 'attachment', filename=filename)
    message.attach(msg)

    # 64-bit encoded message
    encoded_message = urlsafe_b64encode(message.as_bytes())
    # Return a dictionary containing the raw message
    return {'raw': encoded_message.decode()}


def send_message(service, user_id, message):
    """send_message Send an email message

    [extended_summary]

    Parameters
    ----------
    service : `googleapiclient.discovery.Resource`
        Authorized Gmail API service instance
    user_id : `str`
        User's email address; the special value "me" can be used to indicate
        the authenticated user.
    message : `dict`
        An object containing a base64url encoded email object

    Returns
    -------
    `dict`
        The sent message object
    """
    # Try to send the message using the API, else print an error message
    try:
        message = (service.users().messages().send(userId=user_id, body=message)
                .execute())
        print(f"Message Id: {message['id']}")
        return message
    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


def init_gmail_api():
    """init_gmail_api Initialize the GMail API (via OAuth)

    [extended_summary]

    NOTE: The first time this is run on a machine, it will open a webpage for
          authorizing the API.  All subsequent runs will be silent.

    Returns
    -------
    `googleapiclient.discovery.Resource`
        The GMail API service object for consumption by other routines
    """
    creds = None
    if os.path.exists(token_fn := utils.Paths.config.joinpath('token.json')):
        creds = Credentials.from_authorized_user_file(token_fn, SCOPES)

    # If there are no (valid) credentials available, lauch browser to log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
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


# Old SMTP Routines ==========================================================#
# These routines are from the older username/password SMTP scheme.  They are
#  retained for completeness, but should not be used in the future.  The OAUTH
#  routines above offer a more secure interface, and Google should not randomly
#  turn them off as being "unsecure".

def sendMail(message, smtploc='localhost', port=25, user=None, passw=None):
    """
    This assumes that 'message' is an instance of EmailMessage
    """
    # Ultimate return value to know whether we need to try again later
    success = False

    try:
        # This is dumb, but since port is coming from a config file it's
        #   probably still a string at this point.  If we can't int() it,
        #   bail and scream
        port = int(port)
    except ValueError:
        print(f"FATAL ERROR: Can't interpret port {port}!")
        port = None

    print("Sending email...")
    emailExceptions = (socket.timeout, ConnectionError,
                       smtplib.SMTPAuthenticationError,
                       smtplib.SMTPConnectError,
                       smtplib.SMTPResponseException)

    if port == 25:
        try:
            with smtplib.SMTP(smtploc, port, timeout=10.) as server:
                retmsg = server.send_message(message)
            print("Email sent!")
            print("send_message returned:", retmsg)
            success = True
        except emailExceptions:
            print("Email sending failed! Bummer. Check SMTP setup!")
    elif port == 465:
        try:
            # NOTE: For this to work, you must ENABLE "Less secure app access"
            #   for Google/GMail/GSuite accounts! Otherwise you'll get
            # Return code 535
            # 5.7.8 Username and Password not accepted. Learn more at
            # 5.7.8  https://support.google.com/mail/?p=BadCredentials
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtploc, port,
                                  context=context, timeout=10.) as server:
                # Reminder: passw *MUST* be an ascii endoded string
                #   Sorry, no emoji passwords.
                server.login(user, passw)
                retmsg = server.send_message(message)
            print("Email sent!")
            success = True
        except emailExceptions as e:
            print(str(e))
            print("Email sending failed! Bummer. Check SMTP setup!")
    else:
        print("UNKNOWN SMTP METHOD! NOT SENDING ANY MAIL.")

    return success


def constructMail(subject, body, fromaddr, toaddr, fromname=None):
    """Construct SMTP message
    """
    msg = EmailMessage()
    if fromname is None:
        msg['From'] = fromaddr
    else:
        msg['From'] = f"{fromname} <{fromaddr}>"
    msg['To'] = toaddr

    # Make sure replies go to the list, not to this 'from' address
    msg.add_header('reply-to', toaddr)

    msg['Subject'] = subject
    msg.set_content(body)

    print(msg)

    return msg


# Testing Driver =============================================================#
def main():
    """main Main Testing Driver

    Will be removed before this code goes into production.
    """
    service = init_gmail_api()

    recipient = 'tbowers@lowell.edu'

    message = create_message('lig.nanni@lowell.edu', recipient,
                             'This is only a test',
                             'Test, test, test...  Please disregard.')

    sent = send_message(service, "me", message)

    print(type(service), type(message), type(sent))

if __name__ == '__main__':
    main()
