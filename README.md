# Johnny Five

A friendly bot for Lowell Observatory service automation.

JohnnyFive provides small, typed wrappers for Confluence pages, Gmail messages,
and Slack conversations. It requires **Python 3.14 or newer**.

![johnnyfive](https://github.com/LowellObservatory/JohnnyFive/blob/master/johnnyfive/images/johnnyfive.jpg)

## Capabilities

- **Confluence:** Create, update, retrieve, label, comment on, attach to, and
  delete pages using the Confluence Server/Data Center REST v5 client.
- **Gmail:** Send MIME messages, retrieve paginated search results, render
  nested MIME bodies, and update labels individually or in batches.
- **Slack:** Discover conversations, post text or Block Kit messages, and
  upload files through Slack's current external-upload API flow.

JohnnyFive parses its own INI-style configuration and has no `ligmos`
dependency.

## API overview

```python
import johnnyfive

# Confluence API
page = johnnyfive.ConfluencePage(space, page_title, instance=None, use_oauth=False)

# Gmail API
message = johnnyfive.GmailMessage(toaddr, subject, message_text, fromname=None, fromaddr=None, interactive=False)
message_list = johnnyfive.GetMessages(label=None, after=None, before=None, interactive=False)

# Slack API
slack_channel = johnnyfive.SlackChannel(channel_name)

# Utility API
johnnyfive.read_config_section("gmailSetup")
johnnyfive.safe_service_connect(callable)
```

## Requirements

- Python 3.14+
- atlassian-python-api
- beautifulsoup4
- google-api-python-client
- google-auth-httplib2
- google-auth-oauthlib
- httplib2
- lxml
- requests
- slack_sdk

## Installation

Install as a standalone library from a Python 3.14+ environment:

```console
python -m pip install -e .
```

For a consuming project's `pyproject.toml`, use a Git dependency:

```toml
[project]
dependencies = [
    "JohnnyFive @ git+https://github.com/LowellObservatory/JohnnyFive.git",
]
```

## Service configuration and behavior

- Gmail uses the `gmail.modify` OAuth scope. Message searches follow Gmail
  pagination automatically; batch label changes support up to 1,000 message
  IDs per request.
- Confluence supports basic credentials by default and bearer-token
  authentication with `use_oauth=True`. The latter name is retained for
  compatibility and accepts an OAuth 2.0 access token or personal access
  token.
- Slack expects a bot token in `[slackSetup]`. The modern `token` setting is
  preferred; the historical `password` setting remains supported. Ensure the
  bot has the required Slack scopes and is a member of private conversations.
  File uploads use `files_upload_v2`, Slack's replacement for retired
  `files.upload`.

J5 applies retries only to operations that are safe to repeat. It deliberately
does not add generic network retries to Gmail sends or Slack posts/uploads,
because an ambiguous network failure can otherwise duplicate a visible action.

## Development

Install test dependencies and run the hermetic suite:

```console
python -m pip install -e ".[test]"
python -m pytest -q
```

The tests replace vendor clients with fakes, so they verify Gmail, Confluence,
and Slack request shapes without real credentials or network access.
