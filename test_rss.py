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
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site 1 Articles</title>
<link>http://www.site1.com/feed</link>
<description></description>
<language>en</language>

<item>
<title>Title 3</title>
<link>http://www.site1.com/article3</link>
<description>&lt;p&gt;Summary of article 3&lt;/p&gt;</description>
<comments>http://www.site1.com/article3#comments</comments>
<category domain="http://www.site1.com/term/2">Term 2</category>
<pubDate>Sat, 20 Aug 2016 03:00:00 +0000</pubDate>
<dc:creator />
<guid isPermaLink="false">3 at http://www.site1.com/</guid>
</item>

<item>
<title>Title 2</title>
<link>http://www.site1.com/article2</link>
<description>&lt;p&gt;Summary of article 2&lt;/p&gt;</description>
<comments>http://www.site1.com/article2#comments</comments>
<category domain="http://www.site1.com/term/1">Term 1</category>
<pubDate>Sat, 20 Aug 2016 01:00:00 +0000</pubDate>
<dc:creator />
<guid isPermaLink="false">2 at http://www.site1.com/</guid>
</item>

<item>
<title>Title 1</title>
<link>http://www.site1.com/article1</link>
<description>&lt;p&gt;Summary of article 1&lt;/p&gt;</description>
<comments>http://www.site1.com/article1#comments</comments>
<category domain="http://www.site1.com/term/1">Term 1</category>
<pubDate>Sat, 20 Aug 2016 01:00:00 +0000</pubDate>
<dc:creator />
<guid isPermaLink="false">1 at http://www.site1.com/</guid>
</item>

</channel>
</rss>'''


FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION = '''<?xml version="1.0" encoding="utf-8" ?>
<rss version="2.0" xml:base="http://www.site1.com/feed" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel>
<title>Site</title>
<link>http://www.site.com/feed</link>
<description></description>

<item>
<link>http://www.site.com/article</link>
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


def __fixtureBotAddData(bot, id, url, format):
    bot.memory['rss']['feeds']['feed'+id] = {'channel': '#channel' + id, 'name': 'feed' + id, 'url': url}
    bot.memory['rss']['hashes']['feed'+id] = rss.RingBuffer(100)
    bot.memory['rss']['formats']['feed'+id] = rss.FeedFormater(format, url)
    sql_create_table = 'CREATE TABLE ' + rss.__digestTablename('feed'+id) + ' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)'
    bot.db.execute(sql_create_table)
    bot.channels = ['#channel'+id]
    return bot


@pytest.fixture(scope="function")
def bot(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', 'http://www.site1.com/feed', rss.FORMAT_DEFAULT, )
    return bot


@pytest.fixture(scope="function")
def bot_config_read(request):
    bot = __fixtureBotSetup(request)
    return bot


@pytest.fixture(scope="function")
def bot_config_save(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', 'http://www.site1.com/feed', rss.FORMAT_DEFAULT)
    return bot


@pytest.fixture(scope="function")
def bot_rssList(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', 'http://www.site1.com/feed', rss.FORMAT_DEFAULT)
    bot = __fixtureBotAddData(bot, '2', 'http://www.site2.com/feed', rss.FORMAT_DEFAULT, )
    return bot


@pytest.fixture(scope="function")
def bot_rssUpdate(request):
    bot = __fixtureBotSetup(request)
    bot = __fixtureBotAddData(bot, '1', FEED_VALID, rss.FORMAT_DEFAULT)
    return bot


@pytest.fixture(scope="module")
def feedreader_feed_valid():
    return MockFeedReader(FEED_VALID)


@pytest.fixture(scope="module")
def feedreader_feed_item_neither_title_nor_description():
    return MockFeedReader(FEED_ITEM_NEITHER_TITLE_NOR_DESCRIPTION)


# Implementing a mock rss feed reader
class MockFeedReader:
    def __init__(self, url):
        self.url = url

    def read(self):
        feed = feedparser.parse(self.url)
        return feed


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
    assert [(rss.__digestTablename('feedname'),)] == result


def test_dbDropTable(bot):
    rss.__dbCreateTable(bot, 'feedname')
    rss.__dbDropTable(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [] == result


def test_dbGetNumerOfRows(bot):
    ROWS = 10
    for i in range(ROWS):
        hash = rss.__digestString(str(i))
        bot.memory['rss']['hashes']['feed1'].append(hash)
    rss.__dbSaveHashesToDatabase(bot, 'feed1')
    rows_feed = rss.__dbGetNumberOfRows(bot, 'feed1')
    assert ROWS == rows_feed


def test_dbRemoveOldHashesFromDatabase(bot):
    SURPLUS_ROWS = 10
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS)
    for i in range(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS):
        hash = rss.__digestString(str(i))
        bot.memory['rss']['hashes']['feed1'].append(hash)
    rss.__dbSaveHashesToDatabase(bot, 'feed1')
    rss.__dbRemoveOldHashesFromDatabase(bot, 'feed1')
    rows_feed = rss.__dbGetNumberOfRows(bot, 'feed1')
    assert rss.MAX_HASHES_PER_FEED == rows_feed


def test_dbSaveHashToDatabase(bot):
    rss.__dbSaveHashToDatabase(bot, 'feed1', '463f9357db6c20a94a68f9c9ef3bb0fb')
    hashes = rss.__dbReadHashesFromDatabase(bot, 'feed1')
    expected = [(1, '463f9357db6c20a94a68f9c9ef3bb0fb')]
    assert expected == hashes


def test_dbSaveAllHashesToDatabase(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    rss.__feedAdd(bot, 'channel2', 'feed2', 'http://www.site2.com/feed', rss.FORMAT_DEFAULT)
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed2', True)
    rss.__dbSaveAllHashesToDatabase(bot)
    hashes1 = rss.__dbReadHashesFromDatabase(bot, 'feed1')
    hashes2 = rss.__dbReadHashesFromDatabase(bot, 'feed1')
    expected = [(1, '757eab7d0c4f7c6302cf57647d189c3d'), (2, 'b102c2a7acb849f1f583acbd1993e1b0'), (3, '1a3ec7ff94952a9ac1fa157caddcca65')]
    assert expected == hashes1
    assert expected == hashes2


def test_digestString_works():
    digest = rss.__digestString('thisisatest')
    assert 'f830f69d23b8224b512a0dc2f5aec974' == digest


def test_digestTablename_works():
    digest = rss.__digestTablename('thisisatest')
    assert 'rss_f830f69d23b8224b512a0dc2f5aec974' == digest


def test_feedAdd_create_db_table(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed', rss.FORMAT_DEFAULT)
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [(rss.__digestTablename('feedname'),)] == result


def test_feedAdd_create_ring_buffer(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed', rss.FORMAT_DEFAULT)
    assert type(bot.memory['rss']['hashes']['feedname']) == rss.RingBuffer


def test_feedAdd_create_feed(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed', rss.FORMAT_DEFAULT)
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
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed', rss.FORMAT_DEFAULT)
    rss.__feedDelete(bot, 'feedname')
    result = rss.__dbCheckIfTableExists(bot, 'feedname')
    assert [] == result


def test_feedDelete_delete_ring_buffer(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', 'http://www.site.com/feed', rss.FORMAT_DEFAULT)
    rss.__feedDelete(bot, 'feedname')
    assert 'feedname' not in bot.memory['rss']['hashes']


def test_feedDelete_delete_feed(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed', rss.FORMAT_DEFAULT)
    rss.__feedDelete(bot, 'feed')
    assert 'feed' not in bot.memory['rss']['feeds']


def test_feedExists_passes(bot):
    assert rss.__feedExists(bot, 'feed1') == True


def test_feedExists_fails(bot):
    assert rss.__feedExists(bot, 'nofeed') == False


def test_feedUpdate_print_messages(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_feedUpdate_store_hashes(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['757eab7d0c4f7c6302cf57647d189c3d', 'b102c2a7acb849f1f583acbd1993e1b0', '1a3ec7ff94952a9ac1fa157caddcca65']
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_feedUpdate_no_update(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    bot.output = ''
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', False)
    assert '' == bot.output


def test_hashesAdd(bot, feedreader_feed_valid):
    rss.__feedUpdate(bot, feedreader_feed_valid, 'feed1', True)
    expected = ['757eab7d0c4f7c6302cf57647d189c3d', 'b102c2a7acb849f1f583acbd1993e1b0', '1a3ec7ff94952a9ac1fa157caddcca65']
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(100)
    rss.__hashesAdd(bot, 'feed1')
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_rssAdd(bot):
    rss.__rssAdd(bot, '#channel', 'feedname', FEED_VALID, rss.FORMAT_DEFAULT)
    assert rss.__feedExists(bot, 'feedname') == True


def test_rssDel(bot):
    rss.__rssAdd(bot, '#channel', 'feedname', FEED_VALID, rss.FORMAT_DEFAULT)
    rss.__rssDel(bot, 'feedname')
    assert rss.__feedExists(bot, 'feedname') == False


def test_rssGet_update(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID, rss.FORMAT_DEFAULT)
    rss.__rssGet(bot, 'feedname', 'all')
    bot.output = ''
    rss.__rssGet(bot, 'feedname')
    assert '' == bot.output


def test_rssGet_all(bot):
    rss.__feedAdd(bot, '#channel', 'feedname', FEED_VALID, rss.FORMAT_DEFAULT)
    rss.__rssGet(bot, 'feedname', 'all')
    expected = bold('[feedname]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feedname]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feedname]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot.output


def test_rssJoin(bot):
    rss.__rssJoin(bot)
    channels = []
    for feed in bot.memory['rss']['feeds']:
        feedchannel = bot.memory['rss']['feeds'][feed]['channel']
        if feedchannel not in channels:
            channels.append(feedchannel)
    assert channels == bot.channels


def test_rssList_all(bot_rssList):
    rss.__rssList(bot_rssList, '')
    expected1 = '#channel1 feed1 http://www.site1.com/feed'
    expected2 = '#channel2 feed2 http://www.site2.com/feed'
    assert expected1 in bot_rssList.output
    assert expected2 in bot_rssList.output


def test_rssList_feed(bot):
    rss.__rssList(bot, 'feed1')
    expected = '#channel1 feed1 http://www.site1.com/feed\n'
    assert expected == bot.output


def test_rssList_channel(bot):
    rss.__rssList(bot, '#channel1')
    expected = '#channel1 feed1 http://www.site1.com/feed\n'
    assert expected == bot.output


def test_rssList_no_feed_found(bot):
    rss.__rssList(bot, 'invalid')
    assert '' == bot.output


def test_rssUpdate_update(bot_rssUpdate):
    rss.__rssUpdate(bot_rssUpdate)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " http://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " http://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " http://www.site1.com/article3\n"
    assert expected == bot_rssUpdate.output


def test_rssUpdate_no_update(bot_rssUpdate):
    rss.__rssUpdate(bot_rssUpdate)
    bot.output = ''
    rss.__rssUpdate(bot_rssUpdate)
    assert '' == bot.output


def test_FeedFormater_get():
    ff = rss.FeedFormater('value', 'http://www.site.com/feed')
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
