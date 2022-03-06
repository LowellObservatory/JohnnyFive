""" Example for using the Slack module

_extended_summary_
"""

import os

from johnnyfive import slack as j5s
from johnnyfive import utils

# Main Testing Driver ========================================================#
def main():
    """main Main Testing Driver
    """
    slack_object = j5s.SlackChannel('bot_test')
    slack_object.send_message('I am testing sending a message with my '
                              'shiny new SlackChannel class.')
    slack_object.upload_file(os.path.join(utils.Paths.images, 'johnnyfive.jpg'),
                             title='Self-Portrait')

    print(os.path.join(utils.Paths.images, 'johnnyfive.jpg'))

if __name__ == '__main__':
    main()
