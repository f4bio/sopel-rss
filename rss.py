import pprint
import feedparser
import operator
import hashlib
from urllib.request import urlopen
from sopel.tools import SopelMemory
from sopel.module import commands, example, interval, NOLIMIT, require_privmsg, require_admin
from sopel.config.types import (StaticSection, ListAttribute)


class RSSSection(StaticSection):
    del_by_id = ListAttribute('del_by_id', default=False)
    feeds = ListAttribute('feeds', default=[])


def setup(bot):
    bot.config.define_section('rss', RSSSection)
    bot.memory['rss'] = SopelMemory()
    bot.memory['rss']['del_by_id'] = False
    bot.memory['rss']['feeds'] = []
    bot.memory['rss']['uptime'] = 0
    __config_read(bot)


def configure(config):
    config.define_section('rss', RSSSection)
    config.rss.configure_setting('del_by_id', 'allow to delete feeds by index. this is potentially dangerous as the index of the remaining feeds may change after one feed has been deleted')
    config.rss.configure_setting('feeds', 'strings divided by a newline each consisting of channel, name, url and interval divided by spaces')


def shutdown(bot):
    print('Shutting down!')
    bot.debug('rss', 'Shutting down!', 'always')
    __config_save(bot)


@require_admin
@commands('rssadd')
@example('.rssadd <channel> <name> <url> <interval>')
def rssadd(bot, trigger):
    # check number of parameters
    for i in range(2,7):
        if trigger.group(i) is None:
            bot.say('syntax: {}{} <channel> <name> <url> <interval>'.format(bot.config.core.prefix, trigger.group(1)))
            return NOLIMIT

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

    # check that channel starts with #
    if not channel.startswith('#'):
        bot.say('channel "{}" must begin with a "#"'.format(channel))
        return NOLIMIT

    # check that interval is a number
    try:
        int(interval)
    except ValueError:
        bot.say('feed interval "{}" must be a number'.format(interval))
        return NOLIMIT

    # check that feed url is online
    try:
        with urlopen(url) as f:
            if f.status == 200:
                # save config to memory
                bot.memory['rss']['feeds'].append({'channel':channel, 'name':name, 'url':url, 'interval':interval})
                bot.say('rss feed "{}" added successfully'.format(url))
                bot.join(channel)
    except:
        bot.say('unable to add feed "{}": invalid url! syntax: .{} <channel> <name> <url> <interval>'.format(url, trigger.group(1)))
        return NOLIMIT

    __config_save(bot)

    return NOLIMIT


@require_admin
@commands('rssdel')
@example('.rssdel <id>|<name>')
def rssdel(bot, trigger):
    # get arguments
    arg = trigger.group(3)

    if arg is None:
        bot.say('syntax: {}{} <id>|<name>'.format(bot.config.core.prefix, trigger.group(1)))
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
@example('.rssdelallfeeds')
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
@example('.rssget <name> [<scope>]')
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
@example('.rssjoin')
def rssjoin(bot, trigger):
    # check number of parameters
    if not trigger.group(2) is None:
        bot.say('syntax: {}{}'.format(bot.config.core.prefix, trigger.group(1)))
        return NOLIMIT

    for feed in bot.memory['rss']['feeds']:
        bot.join(feed['channel'])

    __config_save(bot)


@require_admin
@commands('rsslist')
@example('.rsslist')
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
        bot.say('{}: {} {} {} {}'.format(feeds.index(feed) + 1, feed['channel'], feed['name'], feed['url'], feed['interval']))
    return NOLIMIT


# read config from disk to memory
def __config_read(bot):
    # feeds
    if bot.config.rss.feeds and bot.config.rss.feeds[0]:
        for feed in bot.config.rss.feeds:
            # split feed line by spaces
            atoms = feed.split(' ')

            # if there is no position (last item) of feed stored in config file then append NOPOSITION
            if len(atoms) == 4:
                atoms.append('NOPOSITION')

            bot.memory['rss']['feeds'].append({'channel': atoms[0], 'name': atoms[1], 'url': atoms[2], 'interval': atoms[3], 'position': atoms[4]})

    # del_by_id
    if bot.config.rss.del_by_id:
        bot.memory['rss']['del_by_id'] = bot.config.rss.del_by_id

    # sort list by channel name
    bot.memory['rss']['feeds'].sort(key=operator.itemgetter('channel'))

    # write config to disk after it has been sorted
    __config_save(bot)


# save config from memory to disk
def __config_save(bot):

    if not bot.memory['rss']['feeds']:
        return NOLIMIT

    # sort list by channel name
    bot.memory['rss']['feeds'].sort(key=operator.itemgetter('channel'))

    # flatten feeds for config file
    feeds = []
    for feed in bot.memory['rss']['feeds']:
        position = ''
        try:
            if feed['position'] != 'NOPOSITION':
                position = ' ' + __hashPosition(feed['position'])
        except:
            pass
        feeds.append(feed['channel'] + ' ' + feed['name'] + ' ' + feed['url'] + ' ' + feed['interval'] + position)
    bot.config.rss.feeds = [",".join(feeds)]

    # save channels
    channels = bot.config.core.channels
    for feed in bot.memory['rss']['feeds']:
      if not feed['channel'] in channels:
          bot.config.core.channels += [feed['channel']]

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


def __getPositionByName(bot, name):
    index = __getIndexByName(bot, name)
    try:
        return bot.memory['rss']['feeds'][index]['position']
    except KeyError:
        return 'NOPOSITION'


def __getUrlByIndex(bot, index):
    return bot.memory['rss']['feeds'][index]['url']


def __hashPosition(position):
    return hashlib.md5(position.encode('utf-8')).hexdigest()


def __setPositionByName(bot, name, position):
    index = __getIndexByName(bot, name)
    bot.memory['rss']['feeds'][index]['position'] = position


@interval(60)
def __update(bot):
    cycle = 60
    uptime = bot.memory['rss']['uptime']

    # loop over feeds
    for feed in bot.memory['rss']['feeds']:

        # check if feed should be updated
        # this line is the calculus when to trigger an update
        if uptime % int(feed['interval']) < cycle:

            # post updates
            __updateFeed(bot, feed['name'], False)

    # avoid upper limit of uptime variable size
    if uptime > cycle * 10:
        uptime %= cycle * 10

    # increment uptime
    bot.memory['rss']['uptime'] = uptime + cycle


def __updateFeed(bot, name, chatty):
    try:
        url = __getUrlByName(bot, name)
        if url is None:
            raise Exception
    except:
        bot.say('url of feed "{}" couldn\'t be read!'.format(name))
        return NOLIMIT

    try:
        feed = feedparser.parse(url)
    except:
        bot.say('error reading feed "{}"'.format(url))
        return NOLIMIT

    channel = __getChannelByName(bot, name)

    position = __getPositionByName(bot, name)
    new_position = position

    # print new or all items
    for item in reversed(feed['entries']):
        if chatty:
            message = '\u0002[' + name + ']\u000F '
            message += item['title'] + ' \u0002→\u000F ' + item['link']
            try:
                message += '(✎ ' + item['dc:creator'] + ')'
            except:
                pass
            bot.say(message, channel)
        new_position = __hashPosition(item['title'] + item['link'] + item['summary'])
        if position == new_position:
            chatty = True

    __setPositionByName(bot, name, new_position)

    # write config to disk after new position has been set
    __config_save(bot)
