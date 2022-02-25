""" Example for using the Gmail module

_extended_summary_
"""

from johnnyfive import gmail as j5g
from johnnyfive import utils

def main():
    """main Main Testing Driver
   """

    # Build the pieces of the message
    recipient = 'someone@domain.com'
    subject = 'This is only a test'
    body = 'This is an example of sending an attachment with ' \
           'the new GmailMessage class.\n'

    # Instantiate
    test_message = j5g.GmailMessage(recipient, subject, body)

    test_message.add_attachment(utils.Paths.images.joinpath('johnnyfive.jpg'))

    send_reciept  = test_message.send()

    print(type(send_reciept))
    print(send_reciept)


if __name__ == '__main__':
    main()
