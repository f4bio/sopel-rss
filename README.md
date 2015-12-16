# SOPEL RSS
New implementation of the deprecated rss module for [sopel](https://github.com/sopel-irc/sopel)

## Installation

Put *rss.py* in your *~/.sopel/modules* directory.

## Commands

### rssadd &mdash; add a feed

**Syntax:** *.rssadd \<channel\> \<name\> \<url\> \<interval\>*

*Requires:* owner or admin

Add the feed *\<url\>* to *\<channel\>* and *\<name\>* it. The feed will be read at approximately every *\<interval\>* seconds and new items will be automatically posted to *\<channel\>*. At most, the bot will update every 60 seconds.

### rssdel &mdash; delete a feed

**Syntax:** *.rssdel \<id\>|\<name\>*

*Requires:* owner or admin

Use *.rsslist* to list get the names and IDs of all feeds. Deletion by ID is per default turned off (cf. Options: *del_by_id*).

### rssdelallfeeds &mdash; delete all feeds

**Syntax:** *rssdelallfeeds*

*Requires:* owner or admin, query with bot

Delete all feeds without asking for confirmation. Be sure to keep a backup of you configuration file.

### rssget &mdash; read a feed and post new items

**Syntax:** *.rssget \<name\> [\<scope\>]*

*Requires:* owner or admin

If *scope* is omitted then the bot will post new items since the last run to the channel to which the feed has been added. During the first run no item will be posted but the ID of the last feed item will be remembered (and written to disk in the config file, cf. Options: *feeds*).

*scope* can only be *all*. In this case the bot will post the whole feed to the channel to which the feed has been added. Mainly useful for debugging.

### rsslist &mdash; list feeds

**Syntax:** *.rsslist*

*Requires:* owner or admin

## Options

The following options can be set in the configuration file. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

### feeds &mdash; feeds that should be posted to channels

**Syntax:** *feeds=\<channel1\> \<name1\> \<url1\> \<interval1\>[,\<channel2\> \<name2\> \<url2\> \<interval2\>]...*

*Default:* empty

This is the main data of the bot which will be read when the bot is started or when the owner or an admin issues the command *.reload rss* in a query with the bot.

### del_by_id &mdash; allows to delete a feed by ID

**Syntax:** *del_by_id=[True|False]*

*Default:* False

This option is dangerous because after a feed has been deleted the ID of all remaining feed (which can be determined by the command *.rsslist*) could change. Therefore, this option is disabled by default but can be enabled for faster deletion of feeds.

### TODO

The cycle time of the bot (update feeds at most every *cycle* seconds) should be configurable. 

This line decides if the update method for a feed will be called: 
 ```python
 if uptime % int(feed['interval']) < cycle
 ```
 