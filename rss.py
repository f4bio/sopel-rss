# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.formatting import bold
from sopel.config.types import StaticSection, ListAttribute, ValidatedAttribute
from sopel.logger import get_logger
from sopel.module import commands, interval, NOLIMIT, require_admin
from sopel.tools import SopelMemory
import feedparser
import hashlib


LOGGER = get_logger(__name__)
MAX_HASHES_PER_FEED = 100
UPDATE_INTERVAL = 60 # seconds

class RSSSection(StaticSection):
    feeds = ListAttribute('feeds', default = '')


def configure(config):
    config.define_section('rss', RSSSection)
    config.rss.configure_setting('feeds', 'comma separated strings consisting of channel, name and url separated by spaces')


def setup(bot):
    bot = __configDefine(bot)
    __configRead(bot)


def shutdown(bot):
    __configSave(bot)


@require_admin
@commands('rssadd')
def rssadd(bot, trigger):
    if trigger.group(3) is None or trigger.group(4) is None or trigger.group(5) is None or not trigger.group(6) is None:
        bot.say('syntax: {}{} <channel> <name> <url>'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT
    channel = trigger.group(3)
    feedname = trigger.group(4)
    url = trigger.group(5)
    __rssadd(bot, channel, feedname, url)
    return NOLIMIT


@require_admin
@commands('rssdel')
def rssdel(bot, trigger):
    if trigger.group(3) is None or not trigger.group(4) is None:
        bot.say('syntax: {}{} <name>'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT
    feedname = trigger.group(3)
    __rssdel(bot, feedname)
    return NOLIMIT


@require_admin
@commands('rssget')
def rssget(bot, trigger):
    if trigger.group(3) is None or (trigger.group(4) and trigger.group(4) != 'all') or trigger.group(5):
        bot.say('syntax: {}{} <name> [all]'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT
    feedname = trigger.group(3)
    scope = ''
    if trigger.group(4):
        scope = trigger.group(4)
    __rssget(bot, feedname, scope)
    return NOLIMIT


@require_admin
@commands('rssjoin')
def rssjoin(bot, trigger):
    if trigger.group(2) is not None:
        bot.say('syntax: {}{}'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT
    __rssjoin(bot)
    return NOLIMIT


@require_admin
@commands('rsslist')
def rsslist(bot, trigger):
    if trigger.group(4) is not None:
        bot.say('syntax: {}{} [<feed>|<channel>]'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT
    arg = trigger.group(3)
    __rsslist(bot, arg)
    return NOLIMIT


@require_admin
@commands('rssupdate')
def rssupdate(bot, trigger):
    if not trigger.group(2) is None:
        bot.say('syntax: {}{}'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT
    __rssupdate(bot)
    return NOLIMIT


def __configDefine(bot):

    # define new config section 'rss'
    bot.config.define_section('rss', RSSSection)
    bot.memory['rss'] = SopelMemory()

    # define dict 'feeds'
    bot.memory['rss']['feeds'] = dict()

    # define dict hashes
    bot.memory['rss']['hashes'] = dict()

    return bot


# read config from disk to memory
def __configRead(bot):

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

            result = __dbCheckIfTableExists(bot, feedname)

            # create hash table for this feed in sqlite3 database provided by the sopel framework
            # use UNIQUE for column hash to minimize database writes by using
            # INSERT OR IGNORE (which is an abbreviation for INSERT ON CONFLICT IGNORE)
            if not result:
                __dbCreateTable(bot, feedname)

            # read hashes from database to memory
            hashes = __dbReadHashesFromDatabase(bot, feedname)

            # each hash in hashes consists of
            # hash[0]: id
            # hash[1]: md5 hash
            for hash in hashes:
                bot.memory['rss']['hashes'][feedname].append(hash[1])

    message = 'read config from disk'
    LOGGER.debug(message)


# save config from memory to disk
def __configSave(bot):
    if not bot.memory['rss']['feeds']:
        return NOLIMIT

    # save hashes from memory to database
    for feedname in bot.memory['rss']['feeds']:
        __dbSaveHashesToDatabase(bot, feedname)

    # we want no more than MAX_HASHES in our database
    for feedname in bot.memory['rss']['feeds']:
        __dbRemoveOldHashesFromDatabase(bot, feedname)

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
        bot.config.save()
        message = 'saved config to disk'
        LOGGER.debug(message)
    except:
        message = 'unable to save config to disk!'
        LOGGER.error(message)


def __dbCheckIfTableExists(bot, feedname):
    tablename = __hashTablename(feedname)
    sql_check_table = "SELECT name FROM sqlite_master WHERE type='table' AND name=(?)"
    return bot.db.execute(sql_check_table, (tablename,)).fetchall()


def __dbCreateTable(bot, feedname):
    tablename = __hashTablename(feedname)

    # create hash table for this feed in sqlite3 database provided by the sopel framework
    # use UNIQUE for column hash to minimize database writes by using
    # INSERT OR IGNORE (which is an abbreviation for INSERT ON CONFLICT IGNORE)
    sql_create_table = "CREATE TABLE '{}' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)".format(tablename)
    bot.db.execute(sql_create_table)
    message = 'added sqlite table "{}" for feed "{}"'.format(tablename, feedname)
    LOGGER.debug(message)


def __dbDropTable(bot, feedname):
    tablename = __hashTablename(feedname)
    sql_drop_table = "DROP TABLE '{}'".format(tablename)
    bot.db.execute(sql_drop_table)
    message = 'dropped sqlite table "{}" of feed "{}"'.format(tablename, feedname)
    LOGGER.debug(message)


def __dbGetNumberOfRows(bot, feedname):
    tablename = __hashTablename(feedname)
    sql_count_hashes = "SELECT count(*) FROM '{}'".format(tablename)
    return bot.db.execute(sql_count_hashes).fetchall()[0][0]


def __dbReadHashesFromDatabase(bot, feedname):
    tablename = __hashTablename(feedname)
    sql_hashes = "SELECT * FROM '{}'".format(tablename)
    message = 'read hashes of feed "{}" from sqlite table "{}"'.format(feedname, tablename)
    LOGGER.debug(message)
    return bot.db.execute(sql_hashes).fetchall()


def __dbRemoveOldHashesFromDatabase(bot, feedname):
    tablename = __hashTablename(feedname)
    rows = __dbGetNumberOfRows(bot, feedname)

    if rows > MAX_HASHES_PER_FEED:

        # calculate number of rows to delete in table hashes
        delete_rows = rows - MAX_HASHES_PER_FEED

        # prepare sqlite statement to figure out
        # the ids of those hashes which should be deleted
        sql_first_hashes = "SELECT id FROM '{}' ORDER BY '{}'.id LIMIT (?)".format(tablename, tablename)

        # loop over the hashes which should be deleted
        for row in bot.db.execute(sql_first_hashes, (str(delete_rows),)).fetchall():

            # delete old hashes from database
            sql_delete_hashes = "DELETE FROM '{}' WHERE id = (?)".format(tablename)
            bot.db.execute(sql_delete_hashes, (str(row[0]),))

        message = 'removed {} rows in table "{}" of feed "{}"'.format(str(delete_rows), tablename, feedname)
        LOGGER.debug(message)

def __dbSaveHashesToDatabase(bot, feedname):
    tablename = __hashTablename(feedname)
    hashes = bot.memory['rss']['hashes'][feedname].get()

    # INSERT OR IGNORE is the short form of INSERT ON CONFLICT IGNORE
    sql_save_hashes = "INSERT OR IGNORE INTO '{}' VALUES (NULL,?)".format(tablename)

    for hash in hashes:
        try:
            bot.db.execute(sql_save_hashes, (hash,))
            message = 'saved hashes of feed "{}" to sqlite table "{}"'.format(feedname, tablename)
            LOGGER.debug(message)
        except:
            # if we have concurrent feed update threads then a database lock may occur
            # this is no problem as the ring buffer will be saved during the next feed update
            pass


def __feedAdd(bot, channel, feedname, url):
    __dbCreateTable(bot, feedname)

    # create new RingBuffer for hashes of feed items
    bot.memory['rss']['hashes'][feedname] = RingBuffer(MAX_HASHES_PER_FEED)
    message = 'added ring buffer for feed "{}"'.format(feedname)
    LOGGER.debug(message)

    # create new dict for feed properties
    bot.memory['rss']['feeds'][feedname] = { 'channel': channel, 'name': feedname, 'url': url }

    message_info = 'added rss feed "{}" to channel "{}" with url "{}"'.format(feedname, channel, url)
    LOGGER.info(message_info)

    return message_info


def __feedCheck(bot, feedreader, channel, feedname):

    result = []

    # read feed
    feed = feedreader.read()
    if not feed:
        message = 'unable to read feed'
        result.append(message)

    # check that feed name is unique
    if __feedExists(bot, feedname):
        message = 'feed name "{}" is already in use, please choose a different name'.format(feedname)
        result.append(message)

    # check that channel starts with #
    if not channel.startswith('#'):
        message = 'channel "{}" must start with a "#"'.format(channel)
        result.append(message)

    # check that feed items have either title or description
    item = feed['entries'][0]
    if not hasattr(item, 'title') and not hasattr(item, 'description'):
        message = 'feed items have neither title nor description'
        result.append(message)

    return result


def __feedDelete(bot, feedname):
    channel = bot.memory['rss']['feeds'][feedname]['channel']
    url = bot.memory['rss']['feeds'][feedname]['url']

    del(bot.memory['rss']['feeds'][feedname])
    message_info = 'deleted rss feed "{}" in channel "{}" with url "{}"'.format(feedname, channel, url)
    LOGGER.info(message_info)

    del(bot.memory['rss']['hashes'][feedname])
    message = 'deleted ring buffer for feed "{}"'.format(feedname)
    LOGGER.debug(message)

    __dbDropTable(bot, feedname)
    return message_info


def __feedExists(bot, feedname):
    if feedname in bot.memory['rss']['feeds']:
        return True
    return False


def __feedUpdate(bot, feedreader, feedname, chatty):
    feed = feedreader.read()

    if not feed:
        url = bot.memory['rss']['feeds'][feedname]['url']
        message = 'unable to read url "{}" of feed "{}"'.format(url, feedname)
        LOGGER.error(message)
        return NOLIMIT

    channel = bot.memory['rss']['feeds'][feedname]['channel']

    # bot.say new or all items
    for item in reversed(feed['entries']):
        hash = __hashString(feedname + item['title'] + item['link'] + item['summary'])
        new_item = not hash in bot.memory['rss']['hashes'][feedname].get()
        if chatty or new_item:
            if new_item:
                bot.memory['rss']['hashes'][feedname].append(hash)
                __dbSaveHashesToDatabase(bot, feedname)
            message = bold('[' + feedname + ']') + ' '
            message += item['title'] + ' ' + bold('→') + ' ' + item['link']
            LOGGER.debug(message)
            bot.say(message, channel)


def __hashString(string):
    return hashlib.md5(string.encode('utf-8')).hexdigest()


def __hashTablename(tablename):
    # we need to hash the name of the table as sqlite3 does not permit to substitute table names
    return 'rss_' + __hashString(tablename)


def __rssadd(bot, channel, feedname, url):
    feedreader = FeedReader(url)
    checkresults = __feedCheck(bot, feedreader, channel, feedname)
    if checkresults:
        for message in checkresults:
            LOGGER.debug(message)
            bot.say(message)
        return NOLIMIT
    message = __feedAdd(bot, channel, feedname, url)
    bot.say(message)
    bot.join(channel)
    __configSave(bot)
    return NOLIMIT


def __rssdel(bot, feedname):
    if not __feedExists(bot, feedname):
        bot.say('feed "{}" doesn\'t exist!'.format(feedname))
        return NOLIMIT
    message = __feedDelete(bot, feedname)
    bot.say(message)
    __configSave(bot)


def __rssget(bot, feedname, scope = ''):
    # if chatty is True then the bot will post feed items to a channel
    chatty = False

    if scope == 'all':
        chatty = True

    if not __feedExists(bot, feedname):
        message = 'feed {} doesn\'t exist'.format(feedname)
        LOGGER.debug(message)
        bot.say(message)
        return NOLIMIT

    url = bot.memory['rss']['feeds'][feedname]['url']
    feedreader = FeedReader(url)
    __feedUpdate(bot, feedreader, feedname, chatty)
    __configSave(bot)
    return NOLIMIT


def __rssjoin(bot):
    for feedname, feed in bot.memory['rss']['feeds'].items():
        bot.join(feed['channel'])
    if bot.config.core.logging_channel:
        bot.join(bot.config.core.logging_channel)
    return NOLIMIT


def __rsslist(bot, arg):
    # list feed
    if arg and __feedExists(bot, arg):
        feed = bot.memory['rss']['feeds'][arg]
        bot.say('{} {} {}'.format(feed['channel'], feed['name'], feed['url']))
        return NOLIMIT

    # list feeds in channel
    for feedname, feed in bot.memory['rss']['feeds'].items():
        if arg and arg != feed['channel']:
            continue
        bot.say('{} {} {}'.format(feed['channel'], feed['name'], feed['url']))
        return NOLIMIT

    bot.say('neither feed "{}" nor feed in channel "{}" found'.format(arg, arg))
    return NOLIMIT


@interval(UPDATE_INTERVAL)
def __rssupdate(bot):
    for feedname in bot.memory['rss']['feeds']:

        # the conditional check is necessary to avoid
        # "RuntimeError: dictionary changed size during iteration"
        # which occurs if a feed has been deleted in the meantime
        if __feedExists(bot, feedname):
            url = bot.memory['rss']['feeds'][feedname]['url']
            feedreader = FeedReader(url)
            __feedUpdate(bot, feedreader, feedname, False)
    return NOLIMIT


# Implementing an rss feed reader for dependency injection
class FeedReader:
    def __init__(self, url):
        self.url = url

    def read(self):
        try:
            feed = feedparser.parse(self.url)
            return feed
        except:
            return False


# Implementing a ring buffer
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
