""" Example for using the Gmail module

_extended_summary_
"""

from johnnyfive import gmail as j5g
from johnnyfive import utils


def main(interactive=False):
    """main Main Testing Driver
   """

    # Build the pieces of the message
    recipient = 'someone@domain.com'
    subject = 'This is only a test'
    body = 'This is an example of sending an attachment with ' \
           'the new GmailMessage class.\n'

    # Instantiate
    test_message = j5g.GmailMessage(recipient, subject, body,
                                    interactive=interactive)

    test_message.add_attachment(utils.Paths.images.joinpath('johnnyfive.jpg'))

    send_reciept  = test_message.send()

    print(type(send_reciept))
    print(send_reciept)


if __name__ == '__main__':
    # Set up the environment to import the program
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(prog='gmail_example',
                        description="Gmail J5 example")
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run this interactively to authenticate Gmail user')
    args = parser.parse_args()

    # Giddy Up!
    main(args.interactive)
