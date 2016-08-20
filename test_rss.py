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

@pytest.fixture(scope="function")
def bot(request):
    # init bot mock
    bot = MockSopel('Sopel')
    bot = rss.__configDefine(bot)

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


def test_dbCheckIfTableExists_passes(bot):
    sql_create_table = "CREATE TABLE 'tablename' (id INTEGER PRIMARY KEY, hash VARCHAR(32) UNIQUE)"
    bot.db.execute(sql_create_table)
    result = rss.__dbCheckIfTableExists(bot, 'tablename')
    assert result == [('tablename',)]


def test_dbCheckIfTableExists_fails(bot):
    result = rss.__dbCheckIfTableExists(bot, 'tablename')
    assert result == []


def test_feedAdd_create_db_table(bot):
    rss.__feedAdd(bot, 'channel', 'feed', 'http://www.site.com/feed')
    result = rss.__dbCheckIfTableExists(bot, rss.__hashTableName('feed'))
    assert result == [(rss.__hashTableName('feed'),)]


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
