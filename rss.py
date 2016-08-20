# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.formatting import bold
from sopel.tools import SopelMemory
from sopel.module import commands, interval, NOLIMIT, require_admin
from sopel.config.types import StaticSection, ListAttribute, ValidatedAttribute
import feedparser
import hashlib
from urllib.request import urlopen


MAX_HASHES_PER_FEED = 100


class RSSSection(StaticSection):
    monitoring_channel = ListAttribute('monitoring_channel', default = '')
    feeds = ListAttribute('feeds', default = '')


def configure(config):
    config.define_section('rss', RSSSection)
    config.rss.configure_setting('monitoring_channel', 'channel in which the bot will report errors')
    config.rss.configure_setting('feeds', 'comma separated strings consisting of channel, name and url separated by spaces')


def setup(bot):
    bot = __config_define(bot)
    __config_read(bot)


def shutdown(bot):
    __config_save(bot)


@require_admin
@commands('rssadd')
def rssadd(bot, trigger):
    # check parameters
    if trigger.group(3) is None or trigger.group(4) is None or trigger.group(5) is None or not trigger.group(6) is None:
        bot.say('syntax: {}{} <channel> <name> <url>'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    channel = trigger.group(3)
    feedname = trigger.group(4)
    url = trigger.group(5)

    result = __rssadd_check_feed(bot, channel, feedname)
    if not result == 'valid':
        bot.say(result)
        return NOLIMIT

    # check that feed url is online
    try:
        with urlopen(url) as f:
            if f.status == 200:
                __addFeed(bot, channel, feedname, url)
                bot.join(channel)
    except:
        message = '[ERROR] unable to add feed "{}"'.format(url)
        __logmsg(message)
        bot.say(message)
        return NOLIMIT

    __config_save(bot)
    return NOLIMIT


@require_admin
@commands('rssdel')
def rssdel(bot, trigger):

    # check parameters
    if trigger.group(3) is None or not trigger.group(4) is None:
        bot.say('syntax: {}{} <name>'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    feedname = trigger.group(3)

    if not feedname in bot.memory['rss']['feeds']:
        bot.say('feed "{}" doesn\'t exist!'.format(feedname))
        return NOLIMIT

    __deleteFeed(bot, feedname)

    __config_save(bot)

    return NOLIMIT


@require_admin
@commands('rssget')
def rssget(bot, trigger):

    # check parameters
    if trigger.group(3) is None or (trigger.group(4) and trigger.group(4) != 'all') or trigger.group(5):
        bot.say('syntax: {}{} <name> [all]'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    # if chatty is True then the bot will post feed items to a channel
    chatty = False

    feedname = trigger.group(3)

    if feedname not in bot.memory['rss']['feeds']:
        bot.say('feed {} doesn\'t exist'.format(feedname))
        return NOLIMIT

    if (trigger.group(4) and trigger.group(4) == 'all'):
        chatty = True

    __updateFeed(bot, feedname, chatty)

    return NOLIMIT


@require_admin
@commands('rssjoin')
def rssjoin(bot, trigger):

    # check parameters
    if not trigger.group(2) is None:
        bot.say('syntax: {}{}'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    for feedname, feed in bot.memory['rss']['feeds'].items():
        bot.join(feed['channel'])

    monitoring_channel = bot.memory['rss']['monitoring_channel']

    if monitoring_channel:
        bot.join(monitoring_channel)

    return NOLIMIT


@require_admin
@commands('rsslist')
def rsslist(bot, trigger):

    # check parameters
    if not trigger.group(4) is None:
        bot.say('syntax: {}{} [<channel>]'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    channel = trigger.group(3)

    # check that channel starts with #
    if channel and not channel.startswith('#'):
        bot.say('channel "{}" must start with "#"'.format(channel))
        return NOLIMIT

    for feedname, feed in bot.memory['rss']['feeds'].items():
        if channel and channel != feed['channel']:
            continue
        bot.say('{} {} {}'.format(feed['channel'], feed['name'], feed['url']))

    return NOLIMIT


@interval(60)
def __update(bot):
    for feedname in bot.memory['rss']['feeds']:
        __updateFeed(bot, feedname, False)


# read config from disk to memory
def __config_read(bot):
    # read 'monitoring_channel' from config file
    if bot.config.rss.monitoring_channel:
        bot.memory['rss']['monitoring_channel'] = bot.config.rss.monitoring_channel[0]

    # read 'feeds' from config file
    if bot.config.rss.feeds and bot.config.rss.feeds[0]:
        for feed in bot.config.rss.feeds:

            # split feed line by spaces
            atoms = feed.split(' ')

            channel = atoms[0]
            feedname = atoms[1]
            url = atoms[2]

            # create new dict for feed properties
            bot.memory['rss']['feeds'][feedname] = { 'channel': channel, 'name': feedname, 'url': url }

            # create new RingBuffer for hashes of feed items
            bot.memory['rss']['hashes'][feedname] = RingBuffer(MAX_HASHES_PER_FEED)

            tablename = __hashTableName(feedname)
            result = __db_check_if_table_exists(bot, tablename)

            # create hash table for this feed in sqlite3 database provided by the sopel framework
            # use UNIQUE for column hash to minimize database writes by using
            # INSERT OR IGNORE (which is an abbreviation for INSERT ON CONFLICT IGNORE)
            if not result:
                sql_create_table = "CREATE TABLE '{}' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)".format(tablename)
                bot.db.execute(sql_create_table)

            # read hashes from database to memory
            sql_hashes = "SELECT * FROM '{}'".format(tablename)
            hashes = bot.db.execute(sql_hashes).fetchall()

            # each hash in hashes consists of
            # hash[0]: id
            # hash[1]: md5 hash
            for hash in hashes:
                bot.memory['rss']['hashes'][feedname].append(hash[1])


# save config from memory to disk
def __config_save(bot):
    if not bot.memory['rss']['feeds']:
        return NOLIMIT

    # save hashes from memory to database
    __saveHashesToDatabase(bot)

    # we want no more than MAX_HASHES in our database
    __removeOldHashesFromDatabase(bot)

    # save monitoring_channel to config file
    bot.config.rss.monitoring_channel = [bot.memory['rss']['monitoring_channel']]

    # flatten feeds for config file
    feeds = []
    for feedname, feed in bot.memory['rss']['feeds'].items():
        feeds.append(feed['channel'] + ' ' + feed['name'] + ' ' + feed['url'])
    bot.config.rss.feeds = [",".join(feeds)]

    # save channels to config file
    channels = bot.config.core.channels
    for feedname, feed in bot.memory['rss']['feeds'].items():
        if not feed['channel'] in channels:
            bot.config.core.channels += [feed['channel']]

    try:
        # save config file
        bot.config.save()
    except:
        message = '[ERROR] unable to save config to disk!'
        __logmsg(message)


def __addFeed(bot, channel, feedname, url):
    tablename = __hashTableName(feedname)

    # create hash table for this feed in sqlite3 database provided by the sopel framework
    # use UNIQUE for column hash to minimize database writes by using
    # INSERT OR IGNORE (which is an abbreviation for INSERT ON CONFLICT IGNORE)
    sql_create_table = "CREATE TABLE '{}' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)".format(tablename)
    bot.db.execute(sql_create_table)

    message = '[INFO] added sqlite table "{}" for feed "{}"'.format(tablename, feedname)
    __logmsg(message)

    # create new RingBuffer for hashes of feed items
    bot.memory['rss']['hashes'][feedname] = RingBuffer(MAX_HASHES_PER_FEED)

    message = '[INFO] added ring buffer for feed "{}"'.format(feedname)
    __logmsg(message)

    # create new dict for feed properties
    bot.memory['rss']['feeds'][feedname] = { 'channel': channel, 'name': feedname, 'url': url }

    message = '[INFO] added to channel "{}" rss feed "{}" with url "{}"'.format(channel, feedname, url)
    __logmsg(message)
    bot.say(message)


def __db_check_if_table_exists(bot, tablename):
    sql_check_table = "SELECT name FROM sqlite_master WHERE type='table' AND name=(?)"
    return bot.db.execute(sql_check_table, (tablename,)).fetchall()


def __deleteFeed(bot, feedname):
    channel = bot.memory['rss']['feeds'][feedname]['channel']
    url = bot.memory['rss']['feeds'][feedname]['url']
    del(bot.memory['rss']['feeds'][feedname])
    message = '[INFO] deleted in channel "{}" rss feed "{}" with url "{}"'.format(channel, feedname, url)
    __logmsg(message)
    bot.say(message)

    # create new RingBuffer for hashes of feed items
    del(bot.memory['rss']['hashes'][feedname])

    message = '[INFO] deleted ring buffer for feed "{}"'.format(feedname)
    __logmsg(message)

    tablename = __hashTableName(feedname)
    sql_drop_table = "DROP TABLE '{}'".format(tablename)
    bot.db.execute(sql_drop_table)
    message = '[INFO] dropped sqlite table "{}" of feed "{}"'.format(tablename, feedname)
    __logmsg(message)


def __hashEntry(entry):
    return hashlib.md5(entry.encode('utf-8')).hexdigest()


def __hashTableName(name):
    # we need to hash the name of the table as sqlite3 does not permit to substitute table names
    return 'rss_' + hashlib.md5(name.encode('utf-8')).hexdigest()


def __logmsg(message):
    print ('[sopel-rss] ' + message)


def __readFeed(bot, feedname):
    url = bot.memory['rss']['feeds'][feedname]['url']
    try:
        feed = feedparser.parse(url)
    except:
        message = '[ERROR] unable to read url "{}" of feed "{}"'.format(url, feedname)
        __logmsg(message)
        bot.say(message, bot.memory['rss']['monitoring_channel'])
        return NOLIMIT
    return feed


def __removeOldHashesFromDatabase(bot):
    for feedname in bot.memory['rss']['feeds']:
        tablename = __hashTableName(feedname)

        # make sure the database has no more than MAX_HASHES_PER_FEED rows
        # get the number of rows
        sql_count_hashes = "SELECT count(*) FROM '{}'".format(tablename)
        rows = bot.db.execute(sql_count_hashes).fetchall()[0][0]

        if rows > MAX_HASHES_PER_FEED:

            # calculate number of rows to delete in table hashes
            delete_rows = rows - MAX_HASHES_PER_FEED

            # prepare sqlite statement to figure out
            # the ids of those hashes which should be deleted
            sql_first_hashes = "SELECT id FROM '{}' ORDER BY '{}'.id LIMIT (?)".format(tablename, tablename)

            # loop over the hashes which should be deleted
            for row in bot.db.execute(sql_first_hashes, (str(delete_rows),)).fetchall():

                # delete old hashes from database
                sql_delete_hashes = "DELETE FROM '{}' WHERE '{}.id' = (?)".format(tablename, tablename)
                bot.db.execute(sql_delete_hashes, (str(row[0]),))


def __rssadd_check_feed(bot, channel, feedname):

    # check that feed name is unique
    if feedname in bot.memory['rss']['feeds']:
        return 'feed name "{}" is already in use, please choose a different name'.format(feedname)

    # check that channel starts with #
    if not channel.startswith('#'):
        return 'channel "{}" must start with a "#"'.format(channel)

    return 'valid'


def __saveHashesToDatabase(bot):
    for feedname in bot.memory['rss']['feeds']:
        tablename = __hashTableName(feedname)
        hashes = bot.memory['rss']['hashes'][feedname].get()

        # INSERT OR IGNORE is the short form of INSERT ON CONFLICT IGNORE
        sql_save_hashes = "INSERT OR IGNORE INTO '{}' VALUES (NULL,?)".format(tablename)

        for hash in hashes:
            try:
                bot.db.execute(sql_save_hashes, (hash,))
            except:
                # if we have concurrent feed update threads then a database lock may occur
                # this is no problem as the ring buffer will be saved during the next feed update
                pass


def __config_define(bot):

    # define new config section 'rss'
    bot.config.define_section('rss', RSSSection)
    bot.memory['rss'] = SopelMemory()

    # define string 'monitoring_channel' in memory
    bot.memory['rss']['monitoring_channel'] = ''

    # define dict 'feeds'
    bot.memory['rss']['feeds'] = dict()

    # define dict hashes
    bot.memory['rss']['hashes'] = dict()

    return bot


def __updateFeed(bot, feedname, chatty):
    feed = __readFeed(bot, feedname)
    channel = bot.memory['rss']['feeds'][feedname]['channel']

    # say new or all items
    for item in reversed(feed['entries']):
        hash = __hashEntry(feedname + item['title'] + item['link'] + item['summary'])
        new_item = not hash in bot.memory['rss']['hashes'][feedname].get()
        if chatty or new_item:
            if new_item:
                bot.memory['rss']['hashes'][feedname].append(hash)
            message = bold('[' + feedname + ']') + ' '
            message += item['title'] + ' ' + bold('→') + ' ' + item['link']
            bot.say(message, channel)

    # write config to disk after new hashes have been calculated
    __config_save(bot)


# Implementing a Ring Buffer
# https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch05s19.html
class RingBuffer:
    """ class that implements a not-yet-full buffer """
    def __init__(self,size_max):
        self.max = size_max
        self.index = 0
        self.data = []

    class __Full:
        """ class that implements a full buffer """
        def append(self, x):
            """ Append an element overwriting the oldest one. """
            self.data[self.cur] = x
            self.cur = (self.cur+1) % self.max
        def get(self):
            """ return list of elements in correct order """
            return self.data[self.cur:]+self.data[:self.cur]

    def append(self,x):
        """ append an element at the end of the buffer """
        self.data.append(x)
        if len(self.data) == self.max:
            self.cur = 0
            # Permanently change self's class from non-full to full
            self.__class__ = self.__Full

    def get(self):
        """ return a list of elements from the oldest to the newest. """
        return self.data
