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

import ssl
import socket
import smtplib
from email.message import EmailMessage
from typing import Any


def sendMail(
    message: EmailMessage,
    smtploc: str = "localhost",
    port: int | str = 25,
    user: str | None = None,
    passw: str | None = None,
) -> bool:
    """Send an email message via an unencrypted or SSL SMTP connection.

    Parameters
    ----------
    message : EmailMessage
        Message to send.
    smtploc : str, optional
        SMTP host name.
    port : int | str, optional
        SMTP port number.
    user : str | None, optional
        User name for SSL authentication.
    passw : str | None, optional
        Password for SSL authentication.

    Returns
    -------
    bool
        Whether the message was sent successfully.
    """
    # Ultimate return value to know whether we need to try again later
    success = False

    try:
        # This is dumb, but since port is coming from a config file it's
        #   probably still a string at this point.  If we can't int() it,
        #   bail and scream
        port = int(port)
    except ValueError:
        print("FATAL ERROR: Can't interpret port %s!" % (port))
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


def constructMail(
    subject: str,
    body: str,
    fromaddr: str,
    toaddr: str,
    fromname: str | None = None,
) -> EmailMessage:
    """Construct a plain-text email message.

    Parameters
    ----------
    subject : str
        Email subject.
    body : str
        Plain-text message body.
    fromaddr : str
        Sender address.
    toaddr : str
        Recipient address.
    fromname : str | None, optional
        Sender display name.

    Returns
    -------
    EmailMessage
        Configured email message.
    """
    msg = EmailMessage()
    if fromname is None:
        msg['From'] = fromaddr
    else:
        msg['From'] = "%s <%s>" % (fromname, fromaddr)
    msg['To'] = toaddr

    # Make sure replies go to the list, not to this 'from' address
    msg.add_header('reply-to', toaddr)

    msg['Subject'] = subject
    msg.set_content(body)

    print(msg)

    return msg
