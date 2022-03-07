## Configuration Files

### Contents

This directory contains the configuration files needed to authenticate a user or users for the various services.

There are three files that must be present for normal operation, but at least two must be present at startup.

* ```johnnyfive.conf``` -- Main configuration file where Confluence and Slack credentials are stored, along with the Gmail username.  Use the ```TEMPLATE``` file as a starting point to ensure all expected fields are populated.

* ```gmail_credentials.json``` -- Gmail OAuth credentials.  Go to https://console.developers.google.com (signed in as the bot user) to create this credential.

* ```gmail_token.json``` (optional) -- This file will be automatically created the first time you attempt to use one of the Gmail classes, but if you have one from a different installation of JohnnyFive, you may copy it in.

### Install existing credential files

If you have existing credential files from a different installation of JohnnyFive, the library comes with a command-line script for installing these in the proper location.

After you have installed JohnnyFive, run:
```
$ j5_install_conf <filename>
```
where `<filename>` is the extant credential file.