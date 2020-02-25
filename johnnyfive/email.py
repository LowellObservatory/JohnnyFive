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

import socket
import smtplib


def sendMail(message, smtploc='localhost', port=25, user=None, passw=None):
    """
    This assumes that the SMTP server has no authentication, and that
    message is an instance of EmailMessage.
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
