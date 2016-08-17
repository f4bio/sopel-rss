# sopel-rss

New implementation of the deprecated rss module for [sopel](https://github.com/sopel-irc/sopel). This module motivated the [ansible-role-sopel-runit-debian](https://github.com/RebelCodeBase/ansible-role-sopel-runit-debian) which can be used to deploy the bot to a debian box.

## Installation

Put *rss.py* in your *~/.sopel/modules* directory.

## Usage

The rss module posts items of rss feeds to irc channels. It hashes the feed items and stores the hashes in a ring buffer in memory and in a sqlite database on disk. It uses one ring buffer and one database table per feed in order to avoid reposting old feed items.

## Commands

### rssadd &mdash; add a feed

**Syntax:** *.rssadd \<channel\> \<name\> \<url\>*

*Requires:* owner or admin

Add the feed *\<url\>* to *\<channel\>* and *\<name\>* it. The feed will be read approximately every minute and new items will be automatically posted to *\<channel\>*.

### rssdel &mdash; delete a feed

**Syntax:** *.rssdel \<id\>|\<name\>*

*Requires:* owner or admin

Use *.rsslist* to list get the names and IDs of all feeds. Deletion by ID is per default turned off (cf. Options: *del_by_id*).

### rssget &mdash; read a feed and post new items

**Syntax:** *.rssget \<name\> [all]*

*Requires:* owner or admin

If *all* is omitted then the bot will post new items since the last run to the channel to which the feed has been added. During the first run no item will be posted but the ID of the last feed item will be remembered (and written to disk in the config file, cf. Options: *feeds*).

If *all* is present the bot will post the whole feed to the channel to which the feed has been added. Mainly useful for debugging.

### rsslist &mdash; list feeds

**Syntax:** *.rsslist*

*Requires:* owner or admin

### rssjoin &mdash; join all feeds' channels

**Syntax:** *.rssjoin*

*Requires:* owner or admin

## Options

The following options can be set in the configuration file. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

### monitoring_channel &mdash; status message channel

**Syntax:** *monitoring_channel=\<channel\>*

*Default:* empty

This should be set to a channel in which the bot posts status messages.

### feeds &mdash; feeds that should be posted to channels

**Syntax:** *feeds=\<channel1\> \<name1\> \<url1\>[,\<channel2\> \<name2\> \<url2\>]...*

*Default:* empty

This is the main data of the bot which will be read when the bot is started or when the owner or an admin issues the command *.reload rss* in a query with the bot.

### TODO

* Tests are missing
* The fields which will be hashed should be configurable.
* The output format and fields should be configurable.
