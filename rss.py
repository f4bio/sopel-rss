import feedparser
import operator
from unidecode import unidecode
from urllib.request import urlopen
from sopel.tools import SopelMemory, SopelMemoryWithDefault
from sopel.module import commands, example, NOLIMIT, require_privmsg, require_admin
from sopel.config.types import (StaticSection, ValidatedAttribute, ListAttribute)


class RSSSection(StaticSection):
    feeds = ListAttribute('feeds', default=[])


def setup(bot):
    bot.config.define_section('rss', RSSSection)
    bot.memory['rss'] = SopelMemory()
    bot.memory['rss']['feeds'] = []
    _config_read(bot)


def configure(config):
    config.define_section('rss', RSSSection)
    config.rss.configure_setting('feeds', 'strings divided by a newline each consisting of channel, name, url and interval divided by spaces')


def shutdown(bot):
    print('shutting down...')
    bot.debug('rss', 'shutting down...', 'always')
    _config_save(bot)


@require_admin
@commands('rssadd')
@example('.rssadd <channel> <name> <url> <interval>')
def rssadd(bot, trigger):
    # check number of parameters
    for i in range(2,7):
        if trigger.group(i) is None:
            bot.say('syntax: .{} <channel> <name> <url> <interval>'.format(trigger.group(1)))
            return NOLIMIT
    # TODO: check that no parameter contains a comma

    # get arguments
    channel = trigger.group(3)
    name = trigger.group(4)
    url = trigger.group(5)
    interval = trigger.group(6)

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

    # check that feed url is online
    try:
        with urlopen(url) as f:
            if f.status == 200:
                # save config to memory
                bot.memory['rss']['feeds'].append({'channel':channel, 'name':name, 'url':url, 'interval':interval})
                bot.say('rss feed "{}" added successfully'.format(url))
    except:
        bot.say('unable to add feed "{}": invalid url!'.format(url))
        return NOLIMIT

    _config_save(bot)

    return NOLIMIT


@require_admin
@commands('rssdel')
@example('.rssdel <index>|<name>')
def rssdel(bot, trigger):
    # get arguments
    arg = trigger.group(3)

    if arg is None:
        bot.say('syntax: .{} <index>|<name>'.format(trigger.group(1)))
        return NOLIMIT

    # check if arg is a number
    try:
        int(arg)
    except ValueError:
        # arg is not a number
        _delFeedByName(bot, arg)
    else:
        # arg is a number
        _delFeedByIndex(bot, int(arg))

    _config_save(bot)

    return NOLIMIT


# shoot yourself in the feet
@require_privmsg
@require_admin
@commands('rssdeleteallfeeds')
@example('.rssdeleteallfeeds')
def rssdeleteallfeeds(bot, trigger):
    # check number of parameters
    if not trigger.group(2) is None:
        bot.say('.{} must be called without parameters'.format(trigger.group(1)))
        return NOLIMIT

    bot.memory['rss']['feeds'].clear()
    bot.say('all rss feeds deleted successfully')

    _config_save(bot)

    return NOLIMIT


@commands('rssget')
@example('.rssget <name>')
def rssget(bot, trigger):
    # check number of parameters
    if trigger.group(3) is None or trigger.group(4):
        bot.say('syntax: .{} <name>'.format(trigger.group(1)))
        return NOLIMIT

    name = trigger.group(3)

    try:
        url = _getFeedUrlByName(bot, name)
        if url is None:
            raise
    except:
        bot.say('url of feed "{}" couldn\'t be read!'.format(name))
        return NOLIMIT

    feed = feedparser.parse(url)
    for key in feed['entries']:
        bot.say(unidecode(key['title']) + ' - ' + key['link'])
    return NOLIMIT


@require_admin
@commands('rsslist')
@example('.rsslist')
def rsslist(bot, trigger):
    # check number of parameters
    if not trigger.group(2) is None:
        bot.say('.{} must be called without parameters'.format(trigger.group(1)))
        return NOLIMIT

    feeds = bot.memory['rss']['feeds']
    bot.say('number of rss feeds: {}'.format(len(feeds)))
    for feed in feeds:
        bot.say('{}: {} {} {} {}'.format(feeds.index(feed) + 1, feed['channel'], feed['name'], feed['url'], feed['interval']))
    return NOLIMIT


#####


# read config from disk to memory
def _config_read(bot):
    if bot.config.rss.feeds and bot.config.rss.feeds[0]:
        for feed in bot.config.rss.feeds:
            atoms = feed.split(' ')
            bot.memory['rss']['feeds'].append({'channel':atoms[0],'name':atoms[1],'url':atoms[2],'interval':atoms[3]})

    print('Read config from disk!')

    # sort list by channel name
    bot.memory['rss']['feeds'].sort(key=operator.itemgetter('channel'))

    print('Sorted feeds!')

    # write config to disk after it has been sorted
    _config_save(bot)


# save config from memory to disk
def _config_save(bot):

    if not bot.memory['rss']['feeds']:
        return NOLIMIT

    # sort list by channel name
    bot.memory['rss']['feeds'].sort(key=operator.itemgetter('channel'))

    # flatten feeds for config file
    feeds = []
    for feed in bot.memory['rss']['feeds']:
        feeds.append(feed['channel'] + ' ' + feed['name'] + ' ' + feed['url'] + ' ' + feed['interval'])
    bot.config.rss.feeds = [",".join(feeds)]

    try:
        bot.config.save()
        # TODO: remove the next line
        print('Saved config to disk!')
    except:
        print('Unable to save config to disk!')


def _delFeedByIndex(bot, index):
    # read url of feed in order to give feedback after the feed has been deleted
    try:
        url = _getUrlByIndex(bot, index)
    except:
        bot.say('feed number "{}" doesn\'t exist!'.format(index))
        return NOLIMIT

    # delete feed
    try:
        if bot.memory['rss']['feeds'][index - 1]:
            del((bot.memory['rss']['feeds'])[index - 1])
            bot.say('rss feed "{}" deleted successfully'.format(url))
    except:
        bot.say('unable to delete feed "{}": feed number doesn\'t exist!'.format(index))


def _delFeedByName(bot, name):
    index = _getIndexByName(bot, name)
    _delFeedByIndex(bot, index)


def _getFeedUrlByName(bot, name):
    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        if feed['name'] == name:
            return feed['url']


def _getIndexByName(bot, name):
    feeds = bot.memory['rss']['feeds']
    for feed in feeds:
        if feed['name'] == name:
            return feeds.index(feed)


def _getUrlByIndex(bot, index):
    return bot.memory['rss']['feeds'][index-1]['url']
