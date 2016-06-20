import feedparser
import operator
import hashlib
from urllib.request import urlopen
from sopel.tools import SopelMemory
from sopel.module import commands, interval, NOLIMIT, require_privmsg, require_admin
from sopel.config.types import (StaticSection, ListAttribute)


class RSSSection(StaticSection):
    del_by_id = ListAttribute('del_by_id', default=False)
    feeds = ListAttribute('feeds', default=[])
    hashes = ListAttribute('hashes', default=[])
    monitoring_channel = ListAttribute('monitoring_channel',default=[])


def setup(bot):
    bot.config.define_section('rss', RSSSection)
    bot.memory['rss'] = SopelMemory()
    bot.memory['rss']['del_by_id'] = False
    bot.memory['rss']['feeds'] = []
    bot.memory['rss']['hashes'] = RingBuffer(1000)
    bot.memory['rss']['monitoring_channel'] = []
    __config_read(bot)


def configure(config):
    config.define_section('rss', RSSSection)
    config.rss.configure_setting('del_by_id', 'allow to delete feeds by index. this is potentially dangerous as the index of the remaining feeds may change after one feed has been deleted')
    config.rss.configure_setting('feeds', 'comma separated strings consisting of channel, name, url separated by spaces')
    config.rss.configure_setting('hashes', 'comma separated strings consisting of hashes of rss feed entries')
    config.rss.configure_setting('monitoring_channel', 'channel in which the bot will report errors')


def shutdown(bot):
    print('Shutting down!')
    bot.debug('rss', 'Shutting down!', 'always')
    __config_save(bot)


@require_admin
@commands('rssadd')
def rssadd(bot, trigger):
    # check number of parameters
    for i in range(2,6):
        if trigger.group(i) is None:
            bot.say('syntax: {}{} <channel> <name> <url>'.format(bot.config.core.prefix, trigger.group(1)))
            return NOLIMIT

    # get arguments
    channel = trigger.group(3)
    name = trigger.group(4)
    url = trigger.group(5)

    # check that feed name is not a number
    try:
        int(name)
    except ValueError:
        pass
    else:
        bot.say('feed name "{}" is invalid, it has to contain at least one letter'.format(name))
        return NOLIMIT

    # check that feed name is unique
    for feed in bot.memory['rss']['feeds']:
        if name == feed['name']:
            bot.say('feed name "{}" is already in use, please choose a different one'.format(name))
            return NOLIMIT

    # check that channel starts with #
    if not channel.startswith('#'):
        bot.say('channel "{}" must begin with a "#"'.format(channel))
        return NOLIMIT

    # check that feed url is online
    try:
        with urlopen(url) as f:
            if f.status == 200:
                # save config to memory
                bot.memory['rss']['feeds'].append({'channel':channel, 'name':name, 'url':url})
                bot.say('rss feed "{}" added successfully'.format(url))
                bot.join(channel)
    except:
        bot.say('unable to add feed "{}": invalid url! syntax: .{} <channel> <name> <url>'.format(url, trigger.group(1)))
        return NOLIMIT

    __config_save(bot)

    return NOLIMIT


@require_admin
@commands('rssdel')
def rssdel(bot, trigger):
    # get arguments
    arg = trigger.group(3)

    if arg is None:
        if bot.memory['rss']['del_by_id']:
            bot.say('syntax: {}{} <id>|<name>'.format(bot.config.core.prefix, trigger.group(1)))
        else:
            bot.say('syntax: {}{} <name>'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    # check if arg is a number
    try:
        int(arg)
    except ValueError:
        # arg is not a number: name
        __delFeedByName(bot, arg)
    else:
        # arg is a number: id
        if not bot.memory['rss']['del_by_id']:
            # subtract 1 from id argument as rsslist starts counting at 1 and not at 0
            bot.say('please use ".{} {}" to delete feed with the current id {}'.format(trigger.group(1), __getNameByIndex(bot, int(arg) - 1), arg))
            return NOLIMIT

        # subtract 1 from id argument as rsslist starts counting at 1 and not at 0
        __delFeedByIndex(bot, int(arg) - 1)

    __config_save(bot)

    return NOLIMIT


# shoot yourself in the feet
@require_privmsg
@require_admin
@commands('rssdelallfeeds')
def rssdeleteallfeeds(bot, trigger):
    # check number of parameters
    if not trigger.group(2) is None:
        bot.say('syntax: {}{}'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    bot.memory['rss']['feeds'].clear()
    bot.say('all rss feeds deleted successfully')

    __config_save(bot)

    return NOLIMIT


@require_admin
@commands('rssget')
def rssget(bot, trigger):
    # check number of parameters
    if trigger.group(3) is None or (trigger.group(4) and trigger.group(4) != 'all') or trigger.group(5):
        bot.say('syntax: {}{} <name> [<scope>]'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    # if chatty is True then the bot will post feed items to a channel
    chatty = False

    name = trigger.group(3)

    if (trigger.group(4) and trigger.group(4) == 'all'):
        chatty = True

    __updateFeed(bot, name, chatty)

    return NOLIMIT


@require_admin
@commands('rssjoin')
def rssjoin(bot, trigger):
    # check number of parameters
    if not trigger.group(2) is None:
        bot.say('syntax: {}{}'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    for feed in bot.memory['rss']['feeds']:
        bot.join(feed['channel'])

    if bot.memory['rss']['monitoring_channel']:
        bot.join(bot.memory['rss']['monitoring_channel'])

    __config_save(bot)


@require_admin
@commands('rsslist')
def rsslist(bot, trigger):
    # check number of parameters
    if not trigger.group(4) is None:
        bot.say('syntax: {}{} [<channel>]'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    channel = trigger.group(3)

    # check that channel starts with #
    if channel and not channel.startswith('#'):
        bot.say('channel "{}" must begin with a "#"'.format(channel))
        return NOLIMIT

    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        if channel:
            if channel != feed['channel']:
                continue
        bot.say('{}: {} {} {}'.format(feeds.index(feed) + 1, feed['channel'], feed['name'], feed['url']))
    return NOLIMIT


# read config from disk to memory
def __config_read(bot):
    # feeds
    if bot.config.rss.feeds and bot.config.rss.feeds[0]:
        for feed in bot.config.rss.feeds:
            # split feed line by spaces
            atoms = feed.split(' ')
            bot.memory['rss']['feeds'].append({'channel': atoms[0], 'name': atoms[1], 'url': atoms[2]})

    # del_by_id
    if bot.config.rss.del_by_id:
        bot.memory['rss']['del_by_id'] = bot.config.rss.del_by_id

    # monitoring_channel
    if bot.config.rss.monitoring_channel:
        bot.memory['rss']['monitoring_channel'] = bot.config.rss.monitoring_channel

    # sort list by channel name
    bot.memory['rss']['feeds'].sort(key=operator.itemgetter('channel'))

    # read hashes
    for hash in bot.config.rss.hashes:
        bot.memory['rss']['hashes'].append(hash)

    # write config to disk after it has been sorted
    __config_save(bot)


# save config from memory to disk
def __config_save(bot):

    if not bot.memory['rss']['feeds']:
        return NOLIMIT

    # monitoring_channel
    bot.config.rss.monitoring_channel = bot.memory['rss']['monitoring_channel']

    # sort list by channel name
    bot.memory['rss']['feeds'].sort(key=operator.itemgetter('channel'))

    # flatten feeds for config file
    feeds = []
    for feed in bot.memory['rss']['feeds']:
        feeds.append(feed['channel'] + ' ' + feed['name'] + ' ' + feed['url'])
    bot.config.rss.feeds = [",".join(feeds)]

    # save channels
    channels = bot.config.core.channels
    for feed in bot.memory['rss']['feeds']:
        if not feed['channel'] in channels:
            bot.config.core.channels += [feed['channel']]

    # save hashes
    bot.config.rss.hashes = []
    for hash in bot.memory['rss']['hashes'].get():
        bot.config.rss.hashes += [hash]

    try:
        bot.config.save()
    except:
        print('Unable to save config to disk!')
        bot.debug('rss', 'Unable to save config to disk!', 'always')


def __delFeedByIndex(bot, index):
    # read url of feed in order to give feedback after the feed has been deleted
    try:
        url = __getUrlByIndex(bot, index)
    except:
        bot.say('feed number "{}" doesn\'t exist!'.format(index))
        return NOLIMIT

    # delete feed
    try:
        if bot.memory['rss']['feeds'][index]:
            del((bot.memory['rss']['feeds'])[index])
            bot.say('rss feed "{}" deleted successfully'.format(url))
    except:
        bot.say('unable to delete feed "{}": feed number doesn\'t exist!'.format(index))


def __delFeedByName(bot, name):
    index = __getIndexByName(bot, name)
    __delFeedByIndex(bot, index)


def __getChannelByName(bot, name):
    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        if feed['name'] == name:
            return feed['channel']


def __getUrlByName(bot, name):
    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        if feed['name'] == name:
            return feed['url']


def __getIndexByName(bot, name):
    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        if feed['name'] == name:
            return feeds.index(feed)


def __getNameByIndex(bot, index):
    return bot.memory['rss']['feeds'][index]['name']


def __getUrlByIndex(bot, index):
    return bot.memory['rss']['feeds'][index]['url']


def __hashEntry(entry):
    return hashlib.md5(entry.encode('utf-8')).hexdigest()


@interval(60)
def __update(bot):
    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        __updateFeed(bot, feed['name'], False)


def __updateFeed(bot, name, chatty):
    try:
        url = __getUrlByName(bot, name)
        if url is None:
            raise Exception
    except:
        bot.say('url of feed "{}" couldn\'t be read!'.format(name), bot.memory['rss']['monitoring_channel'])
        return NOLIMIT

    try:
        feed = feedparser.parse(url)
    except:
        bot.say('error reading feed "{}"'.format(url), bot.memory['rss']['monitoring_channel'])
        return NOLIMIT

    channel = __getChannelByName(bot, name)

    # print new or all items
    for item in reversed(feed['entries']):
        hash = __hashEntry(name + item['title'] + item['link'] + item['summary'])
        if chatty or not hash in bot.memory['rss']['hashes'].get():
            bot.memory['rss']['hashes'].append(hash)
            message = '\u0002[' + name + ']\u000F '
            message += item['title'] + ' \u0002→\u000F ' + item['link']
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