# Johnny Five

A friendly bot.  

This helper library currently contains classes for interacting with Confluence pages (creating, editing, attaching, etc.), interacting with Gmail (send and receive), posting to Slack (write only).

![johnnyfive](https://github.com/LowellObservatory/JohnnyFive/blob/master/johnnyfive/images/johnnyfive.jpg)

## JohnnyFive API

```
from johnnyfive import confluence as j5c
j5c.ConfluencePage(space, page_title, instance=None, use_oauth=False)

from johnnyfive import gmail as j5g
j5g.GmailMessage(toaddr, subject, message_text, fromname=None fromaddr=None, interactive=False)
j5g.GetMessages(label=None, after=None, before=None, interactive=False)

from johnnyfive import slack as j5s
j5s.SlackChannel(channel_name)
```


## Requirements

- atlassian-python-api
- beautifulsoup4
- google-api-python-client
- google-auth-httplib2
- google-auth-oauthlib
- lxml
- pyjwt
- python-twitter
- requests
- slack_sdk
- ligmos @ https://github.com/LowellObservatory/ligmos

## Installation

Installable either as a standalone library:

- In the source directory:

    ```pip install -e .```

    and look for any compilation/installation failures for the dependencies.

Or as a dependancy for other software:

- In your package's `setup.cfg` file, add:

    ```install_requires = JohnnyFive @ git+https://github.com/LowellObservatory/JohnnyFive```
