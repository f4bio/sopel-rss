# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.db import SopelDB
from sopel.formatting import bold
from sopel.modules import rss
from sopel.test_tools import MockSopel, MockConfig
import feedparser
import fileinput
import os
import pytest
import tempfile
import types


FEED_VALID = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="https://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>https://www.site1.com/feed</link>
<description></description>
<language>en</language>

<item>
<title>Title 3</title>
<link>https://www.site1.com/article3</link>
<description>&lt;p&gt;Summary of article 3&lt;/p&gt;</description>
<comments>https://www.site1.com/article3#comments</comments>
<category domain="https://www.site1.com/term/2">Term 2</category>
<pubDate>Sat, 20 Aug 2016 03:00:00 +0000</pubDate>
<dc:creator />
<guid isPermaLink="false">3 at https://www.site1.com/</guid>
</item>

<item>
<title>Title 2</title>
<link>https://www.site1.com/article2</link>
<description>&lt;p&gt;Summary of article 2&lt;/p&gt;</description>
<comments>https://www.site1.com/article2#comments</comments>
<category domain="https://www.site1.com/term/1">Term 1</category>
<pubDate>Sat, 20 Aug 2016 01:00:00 +0000</pubDate>
<dc:creator />
<guid isPermaLink="false">2 at https://www.site1.com/</guid>
</item>

<item>
<title>Title 1</title>
<link>https://www.site1.com/article1</link>
<description>&lt;p&gt;Summary of article 1&lt;/p&gt;</description>
<comments>https://www.site1.com/article1#comments</comments>
<category domain="https://www.site1.com/term/1">Term 1</category>
<pubDate>Sat, 20 Aug 2016 01:00:00 +0000</pubDate>
<dc:creator />
<guid isPermaLink="false">1 at https://www.site1.com/</guid>
</item>

</channel>
</rss>'''


FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="https://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site</title>
<link>https://www.site.com/feed</link>
<description></description>

<item>
<link>https://www.site.com/article</link>
</item>

</channel>
</rss>'''


def __fixtureBotSetup(request):
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    bot.config.core.db_filename = tempfile.mkstemp()[1]
    bot.db = SopelDB(bot.config)
    bot.output = ''

    # monkey patch bot
    def join(self, channel):
        if channel not in bot.channels:
            bot.channels.append(channel)
    bot.join = types.MethodType(join, bot)
    def say(self, message, channel = ''):
        bot.output += message + "\n"
    bot.say = types.MethodType(say, bot)

    # tear down bot
    def fin():
        os.remove(bot.config.filename)
        os.remove(bot.config.core.db_filename)
    request.addfinalizer(fin)

    return bot


def __fixtureBotAddData(bot, id, format, url):
    bot.memory['rss']['feeds']['feed'+id] = {'channel': '#channel' + id, 'name': 'feed' + id, 'url': url}
    bot.memory['rss']['hashes']['feed'+id] = rss.RingBuffer(100)
    bot.memory['rss']['formats']['feed'+id] = rss.FeedFormater(format)
    sql_create_table = 'CREATE TABLE ' + rss.__hashTablename('feed'+id) + ' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)'
    bot.db.execute(sql_create_table)
    bot.channels = ['#channel'+id]
    return bot


@pytest.fixture(scope="function")
def bot(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', rss.FORMAT_DEFAULT, 'http://www.site1.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_config_read(request):
    bot = __fixtureBotSetup(request)
    return bot


@pytest.fixture(scope="function")
def bot_config_save(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', rss.FORMAT_DEFAULT, 'http://www.site1.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_rsslist(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', rss.FORMAT_DEFAULT, 'http://www.site1.com/feed')
    bot = __fixtureBotAddData(bot, '2', rss.FORMAT_DEFAULT, 'http://www.site2.com/feed')
    return bot


@pytest.fixture(scope="function")
def bot_rssupdate(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', rss.FORMAT_DEFAULT, FEED_VALID)
    return bot


@pytest.fixture(scope="module")
def feedreader_feed_valid():
    return MockFeedReader(FEED_VALID)


@pytest.fixture(scope="module")
def feedreader_feed_item_neither_title_nor_description():
    return MockFeedReader(FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION)


def test_configDefine_SopelMemory():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']) == rss.SopelMemory


def test_configDefine_feeds():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']['feeds']) == dict


def test_configDefine_hashes():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']['hashes']) == dict


def test_configDefine_formats():
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)
    assert type(bot.memory['rss']['formats']) == dict


def test_configRead_channel(bot_config_read):
    bot_config_read.config.rss.feeds = ['#readchannel readname http://www.readsite.com/feed']
    rss.__configRead(bot_config_read)
    channel = bot_config_read.memory['rss']['feeds']['readname']['channel']
    assert '#readchannel' == channel


def test_configRead_format(bot_config_read):
    bot_config_read.config.rss.feeds = ['#readchannel readname http://www.readsite.com/feed lst+tl']
    rss.__configRead(bot_config_read)
    channel = bot_config_read.memory['rss']['formats']['readname'].get()
    assert 'lst+tl' == channel


def test_configSave_writes(bot_config_save):
    rss.__configSave(bot_config_save)
    expected = '''[core]
owner = '''+'''
admins = '''+'''
homedir = ''' + bot_config_save.config.homedir + '''
db_filename = '''+ bot_config_save.db.filename + '''
channels = #channel1

[rss]
feeds = #channel1 feed1 http://www.site1.com/feed

'''
    f = open(bot_config_save.config.filename, 'r')
    config = f.read()
    assert expected == config


def test_dbCreateTable_and_dbCheckIfTableExists(bot):
    rss.__dbCreateTable(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [(rss.__hashTablename('feedname'),)] == result


def test_dbDropTable(bot):
    rss.__dbCreateTable(bot, 'feedname')
    rss.__dbDropTable(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [] == result


def test_dbGetNumerOfRows(bot):
    ROWS = 10
    for i in range(ROWS):
        hash = rss.__hashString(str(i))
        bot.memory['rss']['hashes']['feed1'].append(hash)
    rss.__dbSaveHashesToDatabase(bot, 'feed1')
    rows_feed = rss.__dbGetNumberOfRows(bot, 'feed1')
    assert ROWS == rows_feed


def test_dbRemoveOldHashesFromDatabase(bot):
    SURPLUS_ROWS = 10
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS)
    for i in range(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS):
        hash = rss.__hashString(str(i))
        bot.memory['rss']['hashes']['feed1'].append(hash)
    rss.__dbSaveHashesToDatabase(bot, 'feed1')
    rss.__dbRemoveOldHashesFromDatabase(bot, 'feed1')
    rows_feed = rss.__dbGetNumberOfRows(bot, 'feed1')
    assert rss.MAX_HASHES_PER_FEED == rows_feed


def test_dbSaveHashesToDatabase(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    rss.__dbSaveHashesToDatabase(bot, 'feed1')
    hashes = rss.__dbReadHashesFromDatabase(bot, 'feed1')
    expected = [(1, '463f9357db6c20a94a68f9c9ef3bb0fb'), (2, 'af2110eedcbb16781bb46d8e7ca293fe'), (3, '309be3bef1ff3e13e9dbfc010b25fd9c')]
    assert expected == hashes


def test_feedAdd_create_db_table(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [(rss.__hashTablename('feedname'),)] == result


def test_feedAdd_create_ring_buffer(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed')
    assert type(bot.memory['rss']['hashes']['feedname']) == rss.RingBuffer


def test_feedAdd_create_feed(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed')
    feed = bot.memory['rss']['feeds']['feedname']
    assert {'name': 'feedname', 'url': 'http://www.site.com/feed', 'channel': '#channel'} == feed


def test_feedCheck_valid(bot, feedreader_feed_valid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_valid, '#newchannel', 'newname')
    assert not checkresults


def test_feedCheck_feedname_must_be_unique(bot, feedreader_feed_valid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_valid, '#newchannel', 'feed1')
    assert ['feed name "feed1" is already in use, please choose a different name'] == checkresults


def test_feedCheck_channel_must_start_with_hash(bot, feedreader_feed_valid):
    checkresults = rss.__feedCheck(bot, feedreader_feed_valid, 'nohashchar', 'newname')
    assert ['channel "nohashchar" must start with a "#"'] == checkresults


def test_feedCheck_feeditem_must_have_title_or_description(bot, feedreader_feed_item_neither_title_nor_description):
    checkresults = rss.__feedCheck(bot, feedreader_feed_item_neither_title_nor_description, '#newchannel', 'newname')
    assert ['feed items have neither title nor description'] == checkresults


def test_feedDelete_delete_db_table(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed')
    rss.__feedDelete(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [] == result


def test_feedDelete_delete_ring_buffer(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed')
    rss.__feedDelete(bot, 'feedname')
    assert 'feedname' not in bot.memory['rss']['hashes']


def test_feedDelete_delete_feed(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    rss.__feedDelete(bot, 'feed')
    assert 'feed' not in bot.memory['rss']['feeds']


def test_feedExists_passes(bot):
    assert rss.__feedExists(bot, 'feed1') == True


def test_feedExists_fails(bot):
    assert rss.__feedExists(bot, 'nofeed') == False


def test_feedUpdate_print_messages(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " https://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " https://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " https://www.site1.com/article3\n"
    assert expected == bot.output


def test_feedUpdate_store_hashes(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['463f9357db6c20a94a68f9c9ef3bb0fb', 'af2110eedcbb16781bb46d8e7ca293fe', '309be3bef1ff3e13e9dbfc010b25fd9c']
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_feedUpdate_no_update(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    bot.output = ''
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', False)
    assert '' == bot.output


def test_hashString_works():
    hash = rss.__hashString('thisisatest')
    assert 'f830f69d23b8224b512a0dc2f5aec974' == hash


def test_hashTablename_works():
    hash = rss.__hashTablename('thisisatest')
    assert 'rss_f830f69d23b8224b512a0dc2f5aec974' == hash


def test_rssadd(bot):
    rss.__rssadd(bot, '#channel', 'feedname', FEED_VALID)
    assert rss.__feedExists(bot, 'feedname') == True


def test_rssdel(bot):
    rss.__rssadd(bot, '#channel', 'feedname', FEED_VALID)
    rss.__rssdel(bot, 'feedname')
    assert rss.__feedExists(bot, 'feedname') == False


def test_rssget_update(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    rss.__rssget(bot, 'feedname', 'all')
    bot.output = ''
    rss.__rssget(bot, 'feedname')
    assert '' == bot.output


def test_rssget_all(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID)
    rss.__rssget(bot, 'feedname', 'all')
    expected = bold('[feedname]') + ' Title 1 ' + bold('→') + " https://www.site1.com/article1\n" + bold('[feedname]') + ' Title 2 ' + bold('→') + " https://www.site1.com/article2\n" + bold('[feedname]') + ' Title 3 ' + bold('→') + " https://www.site1.com/article3\n"
    assert expected == bot.output


def test_rssjoin(bot):
    rss.__rssjoin(bot)
    channels = []
    for feed in bot.memory['rss']['feeds']:
        feedchannel = bot.memory['rss']['feeds'][feed]['channel']
        if feedchannel not in channels:
            channels.append(feedchannel)
    assert channels == bot.channels


def test_rsslist_all(bot_rsslist):
    rss.__rsslist(bot_rsslist, '')
    expected = '#channel2 feed2 http://www.site2.com/feed\n#channel1 feed1 http://www.site1.com/feed\n'
    assert expected == bot_rsslist.output


def test_rsslist_feed(bot):
    rss.__rsslist(bot, 'feed1')
    expected = '#channel1 feed1 http://www.site1.com/feed\n'
    assert expected == bot.output


def test_rsslist_channel(bot):
    rss.__rsslist(bot, '#channel1')
    expected = '#channel1 feed1 http://www.site1.com/feed\n'
    assert expected == bot.output


def test_rsslist_no_feed_found(bot):
    rss.__rsslist(bot, 'invalid')
    assert '' == bot.output


def test_rssupdate_update(bot_rssupdate):
    rss.__rssupdate(bot_rssupdate)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " https://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " https://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " https://www.site1.com/article3\n"
    assert expected == bot_rssupdate.output


def test_rssupdate_no_update(bot_rssupdate):
    rss.__rssupdate(bot_rssupdate)
    bot.output = ''
    rss.__rssupdate(bot_rssupdate)
    assert '' == bot.output


def test_FeedFormater_get():
    ff = rss.FeedFormater('value')
    assert 'value' == ff.get()


def test_RingBuffer_append():
    rb = rss.RingBuffer(3)
    assert rb.get() == []
    rb.append('1')
    assert ['1'] == rb.get()


def test_RingBuffer_overflow():
    rb = rss.RingBuffer(3)
    rb.append('hash1')
    rb.append('hash2')
    rb.append('hash3')
    assert ['hash1', 'hash2', 'hash3'] == rb.get()
    rb.append('hash4')
    assert ['hash2', 'hash3', 'hash4'] == rb.get()


# Implementing a mock rss feed reader
class MockFeedReader:
    def __init__(self, url):
        self.url = url

    def read(self):
        feed = feedparser.parse(self.url)
        return feed
