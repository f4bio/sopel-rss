# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.modules import rss
from sopel.test_tools import MockSopel, MockConfig
from sopel.db import SopelDB
import os
import pytest
import sqlite3
import tempfile
import types

@pytest.fixture(scope="module")
def bot(request):
    # init bot mock
    bot = MockSopel('Sopel')
    bot = rss.__config_define(bot)

    # init db mock
    bot.config.core.db_filename = tempfile.mkstemp()[1]
    bot.db = SopelDB(bot.config)

    # add some data
    bot.memory['rss']['feeds']['feed1'] = '#channel1 feed1 http://www.site1.com/feed'
    bot.memory['rss']['feeds']['feed2'] = '#channel2 feed2 http://www.site2.com/feed'
    bot.memory['rss']['feeds']['feed3'] = '#channel3 feed3 http://www.site3.com/feed'

    # monkey patch bot instance
    def say(self, message):
        print(message)
    bot.say = types.MethodType(say, bot)

    # teardown method
    def fin():
        os.remove(bot.config.core.db_filename)
    request.addfinalizer(fin)

    return bot


def test_rssadd_check_feed_valid_feed(bot):
    result = rss.__rssadd_check_feed(bot, '#newchannel', 'newname')
    assert result == 'valid'


def test_rssadd_check_feed_double_feedname(bot):
    result = rss.__rssadd_check_feed(bot, '#newchannel', 'feed1')
    assert result == 'feed name "feed1" is already in use, please choose a different name'


def test_rssadd_check_feed_channel_must_start_with_hash(bot):
    result = rss.__rssadd_check_feed(bot, 'nochannel', 'newname')
    assert result == 'channel "nochannel" must start with a "#"'


def test_addFeed_create_db_table(bot):
    rss.__addFeed(bot, 'channel4', 'feed4', 'http://www.site4.com/feed')
    result = rss.__db_check_if_table_exists(bot, rss.__hashTableName('feed4'))
    assert result == [(rss.__hashTableName('feed4'),)]


def test_addFeed_create_ring_buffer(bot):
    rss.__addFeed(bot, 'channel5', 'feed5', 'http://www.site5.com/feed')
    assert type(bot.memory['rss']['hashes']['feed5']) == rss.RingBuffer


def test_addFeed_create_feed(bot):
    rss.__addFeed(bot, 'channel6', 'feed6', 'http://www.site6.com/feed')
    feed6 = bot.memory['rss']['feeds']['feed6']
    assert feed6 == {'name': 'feed6', 'url': 'http://www.site6.com/feed', 'channel': 'channel6'}


def test_hashEntry_works():
    hash = rss.__hashEntry('thisisatest')
    assert hash == 'f830f69d23b8224b512a0dc2f5aec974'


def test_hashTableName_works():
    hash = rss.__hashTableName('thisisatest')
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
