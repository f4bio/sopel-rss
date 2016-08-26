# sopel-rss

New implementation of the deprecated rss module for [sopel](https://github.com/sopel-irc/sopel). This module motivated the [ansible-role-sopel-runit-debian](https://github.com/RebelCodeBase/ansible-role-sopel-runit-debian) which can be used to deploy the bot to a debian box.

## Installation

Put *rss.py* in your *~/.sopel/modules* directory.

## Usage

The rss module posts items of rss feeds to irc channels. It hashes the feed items and stores the hashes in a ring buffer in memory and in a sqlite database on disk. It uses one ring buffer and one database table per feed in order to avoid reposting old feed items.

## Commands

### rssadd &mdash; add a feed

**Syntax:** *.rssadd \<channel\> \<name\> \<url\> [\<format\>]*

*Requires:* owner or admin

Add the feed *\<url\>* to *\<channel\>* and call it *\<name\>* Optionally, a format can be specified, see section Format. The feed will be read approximately every minute and new items will be automatically posted to *\<channel\>*.

### rssdel &mdash; delete a feed

**Syntax:** *.rssdel \<id\>|\<name\>*

*Requires:* owner or admin

Use *.rsslist* to list get the names and IDs of all feeds. Deletion by ID is per default turned off (cf. Options: *del_by_id*).

### rssget &mdash; read a feed and post new items

**Syntax:** *.rssget \<name\> [all]*

*Requires:* owner or admin

If the optional argument *all* is omitted then the bot will post new items since the last run to the channel to which the feed has been added. During the first run no item will be posted but the ID of the last feed item will be remembered (and written to disk in the config file, cf. Options: *feeds*).

If *all* is present the bot will post the whole feed to the channel to which the feed has been added. Mainly useful for debugging.

### rsslist &mdash; list feeds

**Syntax:** *.rsslist [\<feed\>|\<channel\>]*

*Requires:* owner or admin

### rssjoin &mdash; join all feeds' channels

**Syntax:** *.rssjoin*

*Requires:* owner or admin

## Options

The following options can be set in the configuration file. Be aware that the bot mustn't be running when editing the configuration file. Otherwise, your edits may be overwritten!

**Syntax:** *feeds=\<channel1\> \<name1\> \<url1\> [\<format\>][,\<channel2\> \<name2\> \<url2\> [\<format\>]]...*

*Default:* empty

This is the main data of the bot which will be read when the bot is started or when the owner or an admin issues the command *.reload rss* in a query with the bot.

### Formats

A *format* string defines which feed item fields be be hashed, i.e. when two feed items will be considered equal, and which field item fields will be output by the bot. Both definitions are separated by a '+'. Each valid rss feed must have at least a title or a description field, all other item fields are optional. These fields can be configured for sopel-rss:

<table>
    <tr>
        <td>f</td>
        <td>feedname</td>
    </tr>
    <tr>
        <td>a</td>
         <td>author</td>
    </tr>
    <tr>
        <td>d</td>
        <td>description</td>
    </tr>
    <tr>
        <td>g</td>
         <td>guid</td>
    </tr>
    <tr>
        <td>l</td>
         <td>link</td>
    </tr>
    <tr>
        <td>p</td>
         <td>published</td>
    </tr>
    <tr>
        <td>s</td>
         <td>summary</td>
    </tr>
    <tr>
        <td>t</td>
         <td>title</td>
    </tr>
</table>

The feedname is a custom name specified as a parameter to *.rssadd* an not a feed item field. guid is a unique identifiert and published is the date and time of publication.

Example: *fl+tl*

The feedname and the link of the rss feed item will be used to hash the feed item. If an item of a different feed has the same link it will be posted again by the bot. The bot will post the feed item title followed by the feed item link.

Example: *flst+tal*

The feedname, link, summary and title will be used to hash the feed item. If any of these fields change in the feed the feed item will be posted again. The bot will post the title, author and link of the feed item but not the feedname.

### Unit Tests

The module is extensively tested through [py.test](http://doc.pytest.org):

`python3 -m pytest -v test/test_rss.py sopel/modules/rss.py`
