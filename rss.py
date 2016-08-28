__author__ = "Fabio Tea <ft2011@gmail.com>"

import feedparser
from urllib.request import urlopen
from sopel.tools import SopelMemory, SopelMemoryWithDefault
from sopel.module import commands, example, NOLIMIT, require_privilege, OP, require_admin
from sopel.config.types import (StaticSection, ValidatedAttribute, ListAttribute)


class RSSSection(StaticSection):
    feeds = ListAttribute("feeds", default=[])
    update_interval = ValidatedAttribute("update_interval", int, default=10)


def setup(bot):
    bot.config.define_section("rss", RSSSection)
    bot.memory["rss"] = SopelMemory()
    bot.memory["rss"]["feeds"] = []
    bot.memory["rss"]["update_interval"] = 10

    if bot.config.rss.feeds:
        bot.memory["rss"]["feeds"] = bot.config.rss.feeds
    if bot.config.rss.update_interval:
        bot.memory["rss"]["update_interval"] = bot.config.rss.update_interval


def configure(config):
    config.define_section("rss", RSSSection)
    config.rss.configure_setting("feeds", "Feed URLs")
    config.rss.configure_setting("update_interval", "How often to check? (secounds)")


def shutdown(bot):
    print("shutting down...")
    bot.debug("RSS", "shutting down...", "always")
    bot.config.rss.feeds = bot.memory["rss"]["feeds"]
    bot.config.rss.update_interval = bot.memory["rss"]["update_interval"]
    bot.config.save()

    print(bot.config.rss.feeds)
    bot.debug("RSS", bot.config.rss.feeds, "always")
    bot.debug("RSS", bot.config.rss.update_interval, "always")


@require_admin
@commands("rssget")
def rssget(bot, trigger):
    if not trigger.group(2) is None:
        bot.say("coming soon")
        return NOLIMIT

        # rss = "http://lorem-rss.herokuapp.com/feed"
        # feed = feedparser.parse(rss)
        # for key in feed["entries"]:
        #     bot.say(unidecode.unidecode(key["title"]))


@require_admin
@commands("rsslist")
@example(".rsslist")
def rsslist(bot, trigger):
    if not trigger.group(2) is None:
        bot.say("expecting no parameter for this command...")
        return NOLIMIT

    feeds = bot.memory["rss"]["feeds"]
    bot.say("RSS Feed URLs (#{}): ".format(len(feeds)))
    for feed in feeds:
        bot.say("{}: {}".format(feeds.index(feed) + 1, feed))
    return NOLIMIT


@require_admin
@commands("rssadd")
@example(".rssadd http://google.com")
def rssadd(bot, trigger):
    url = trigger.group(2)

    if trigger.group(2) is None:
        bot.say("expecting one parameter for this command...")
        return NOLIMIT

    try:
        with urlopen(url) as f:
            if f.status == 200:
                bot.memory["rss"]["feeds"].append(url)
                # bot.config.save()
                bot.say("RSS feed '{}' added successfully".format(url))

    except:
        bot.say("Unable to add feed '{}' - Invalid URL!".format(url))
    return NOLIMIT


@require_admin
@commands("rssdel")
@example(".rssdel 2")
def rssdel(bot, trigger):
    idx = trigger.group(2)

    if idx is None:
        bot.say("expecting one parameter for this command...")
        return NOLIMIT

    try:
        if bot.memory["rss"]["feeds"][idx]:
            bot.memory["rss"]["feeds"].remove(idx)
            # bot.config.save()
            bot.say("RSS feed '{}' deleted successfully".format(idx))
    except:
        bot.say("Unable to delete feed '{}' - No such index!".format(idx))
    return NOLIMIT


@require_admin
@commands("rssclear")
@example(".rssclear")
def rssclear(bot, trigger):
    if not trigger.group(2) is None:
        bot.say("expecting no parameter for this command...")
        return NOLIMIT

    bot.memory["rss"]["feeds"].clear()
    # bot.config.save()
    bot.say("All RSS feeds deleted successfully")
    return NOLIMIT
