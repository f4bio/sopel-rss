# SOPEL RSS
New implementation of the deprecated rss module for [sopel](https://github.com/sopel-irc/sopel)

## Commands

### rssadd &mdash; add a feed

**Syntax: .rssadd <channel> <name> <url> <interval>**

*Requires: owner or admin*

### rssdel &mdash; delete a feed

**Syntax: .rssdel <id>|<name>**

*Requires: owner or admin*

### rssdelallfeeds &mdash; delete all feeds

**Syntax: rssdelallfeeds**

*Requires: owner or admin, query with bot*

### rssget &mdash; read a feed and post new items

**Syntax: .rssget <name> [<scope>]**

*Requires: owner or admin*

### rsslist &mdash; list feeds

**Syntax: .rsslist**

*Requires: owner or admin*

## Options

The following options can be set in the configuration file. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

### feeds &mdash; feeds that should be posted to channels

**Syntax: feeds=<channel1> <name1> <url1> <interval1>[,<channel2> <name2> <url2> <interval2>]...**

*Default: empty*

This is the main data of the bot which will be read when the bot is started or when the owner or an admin issues the command **.reload rss** in a query with the bot.

### del_by_id &mdash; allows to delete a feed by ID

**Syntax: del_by_id=[True|False]*

*Default: False*

This option is dangerous because after a feed has been deleted the ID of all remaining feed (which can be determined by the command **.rsslist**) could change. Therefore, this option is disabled by default but can be enabled for faster deletion of feeds.