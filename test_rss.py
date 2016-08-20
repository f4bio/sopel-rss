# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.db import SopelDB
from sopel.formatting import bold
from sopel.modules import rss
from sopel.test_tools import MockSopel, MockConfig
import feedparser
import os
import pytest
import tempfile
import types

@pytest.fixture(scope="function")
def bot(request):
    # init bot mock
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)

    # init db mock
    bot.config.core.db_filename = tempfile.mkstemp()[1]
    bot.db = SopelDB(bot.config)

    # add some data
    bot.memory['rss']['feeds']['feed1'] = {'channel': '#channel1', 'name': 'feed1', 'url': 'http://www.site1.com/feed'}
    bot.memory['rss']['hashes']['feed1'] = rss.RingBuffer(100)

    # initialize variable which will store every bot.say
    bot.output = ''

    # monkey patch bot instance
    def say(self, message, channel=''):
        bot.output += message + "\n"
    bot.say = types.MethodType(say, bot)

    # teardown method
    def fin():
        os.remove(bot.config.core.db_filename)
    request.addfinalizer(fin)

    return bot


@pytest.fixture(scope="function")
def feedreader():
    feedreader = MockFeedReader()
    return feedreader


def test_configDefine():
    pass


def test_configRead():
    pass


def test_configSave():
    pass


def test_dbCheckIfTableExists_passes(bot):
    sql_create_table = "CREATE TABLE 'tablename' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)"
    bot.db.execute(sql_create_table)
    result = rss.__dbCheckIfTableExists(bot, 'tablename')
    assert result == [('tablename',)]


def test_dbCheckIfTableExists_fails(bot):
    result = rss.__dbCheckIfTableExists(bot, 'tablename')
    assert result == []


def test_dbGetNumerOfRows(bot):
    ROWS = 10
    tablename = rss.__hashTablename('feedname')
    rss.__feedAdd(bot, '#channel', 'feedname', 'feedurl')
    for i in range(ROWS):
        hash = rss.__hashString(str(i))
        bot.memory['rss']['hashes']['feedname'].append(hash)
    rss.__dbSaveHashesToDatabase(bot, 'feedname')
    rows_feed = rss.__dbGetNumberOfRows(bot, tablename)
    assert rows_feed == ROWS


def test_dbRemoveOldHashesFromDatabase(bot):
    SURPLUS_ROWS = 10
    tablename = rss.__hashTablename('feedname')
    rss.__feedAdd(bot, '#channel', 'feedname', 'feedurl')
    bot.memory['rss']['hashes']['feedname'] = rss.RingBuffer(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS)
    for i in range(rss.MAX_HASHES_PER_FEED + SURPLUS_ROWS):
        hash = rss.__hashString(str(i))
        bot.memory['rss']['hashes']['feedname'].append(hash)
    rss.__dbSaveHashesToDatabase(bot, 'feedname')
    rss.__dbRemoveOldHashesFromDatabase(bot, 'feedname')
    rows_feed = rss.__dbGetNumberOfRows(bot, tablename)
    assert rows_feed == rss.MAX_HASHES_PER_FEED


def test_dbSaveHashesToDatabase(bot, feedreader):
    rss.__feedAdd(bot, '#channel', 'feedname', 'feedurl')
    rss.__feedUpdate(bot, feedreader, 'feedname', True)
    rss.__dbSaveHashesToDatabase(bot, 'feedname')
    sql_read_hashes = 'SELECT * FROM ' + rss.__hashTablename('feedname')
    result = bot.db.execute(sql_read_hashes).fetchall()
    expected = [(1, '63a03d3de497c75afa1fef0250595946'), (2, '2cc0fcae6d21bfed13314c10089d007d'), (3, 'c1d413bba94540cda87ec8ab1113b95c')]
    assert expected == result


def test_feedAdd_create_db_table(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    result = rss.__dbCheckIfTableExists(bot, rss.__hashTablename('feed'))
    assert result == [(rss.__hashTablename('feed'),)]


def test_feedAdd_create_ring_buffer(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    assert type(bot.memory['rss']['hashes']['feed']) == rss.RingBuffer


def test_feedAdd_create_feed(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    feed = bot.memory['rss']['feeds']['feed']
    assert feed == {'name': 'feed', 'url': 'http://www.site.com/feed', 'channel': 'channel'}


def test_feedCheck_valid(bot):
    result = rss.__feedCheck(bot, '#newchannel', 'newname')
    assert result == 'valid'


def test_feedCheck_feedname_duplicate(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    result = rss.__feedCheck(bot, '#newchannel', 'feed')
    assert result == 'feed name "feed" is already in use, please choose a different name'


def test_feedCheck_channel_must_start_with_hash(bot):
    result = rss.__feedCheck(bot, 'nohashchar', 'newname')
    assert result == 'channel "nohashchar" must start with a "#"'


def test_feedDelete_delete_db_table(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    rss.__feedDelete(bot, 'feed')
    result = rss.__dbCheckIfTableExists(bot, 'feed')
    assert result == []


def test_feedDelete_delete_ring_buffer(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    rss.__feedDelete(bot, 'feed')
    assert 'feed' not in bot.memory['rss']['hashes']


def test_feedDelete_delete_feed(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    rss.__feedDelete(bot, 'feed')
    assert 'feed' not in bot.memory['rss']['feeds']


def test_feedUpdate_print_messages(bot, feedreader):
    rss.__feedUpdate(bot, feedreader, 'feed1', True)
    expected = bold('[feed1]') + ' Title 1 ' + bold('→') + " https://www.site1.com/article1\n" + bold('[feed1]') + ' Title 2 ' + bold('→') + " https://www.site1.com/article2\n" + bold('[feed1]') + ' Title 3 ' + bold('→') + " https://www.site1.com/article3\n"
    output = bot.output
    assert expected == output


def test_feedUpdate_store_hashes(bot, feedreader):
    rss.__feedUpdate(bot, feedreader, 'feed1', True)
    expected = ['463f9357db6c20a94a68f9c9ef3bb0fb', 'af2110eedcbb16781bb46d8e7ca293fe', '309be3bef1ff3e13e9dbfc010b25fd9c']
    hashes = bot.memory['rss']['hashes']['feed1'].get()
    assert expected == hashes


def test_feedUpdate_no_update(bot, feedreader):
    rss.__feedUpdate(bot, feedreader, 'feed1', True)
    bot.output = ''
    rss.__feedUpdate(bot, feedreader, 'feed1', False)
    assert bot.output == ''


def test_hashString_works():
    hash = rss.__hashString('thisisatest')
    assert hash == 'f830f69d23b8224b512a0dc2f5aec974'


def test_hashTablename_works():
    hash = rss.__hashTablename('thisisatest')
    assert hash == 'rss_f830f69d23b8224b512a0dc2f5aec974'


def test_RingBuffer_append():
    rb = rss.RingBuffer(3)
    assert rb.get() == []
    rb.append('1')
    assert rb.get() == ['1']


def test_RingBuffer_overflow():
    rb = rss.RingBuffer(3)
    rb.append('hash1')
    rb.append('hash2')
    rb.append('hash3')
    assert rb.get() == ['hash1', 'hash2', 'hash3']
    rb.append('hash4')
    assert rb.get() == ['hash2', 'hash3', 'hash4']


# Implementing a mock rss feed reader
class MockFeedReader:
    def read(self):
        rawdata='''<?xml version="1.0" encoding="utf-8" ?>
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
        feed = feedparser.parse(rawdata)
        return feed
