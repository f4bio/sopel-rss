# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.modules import rss
from sopel.test_tools import MockSopel
import pytest


@pytest.fixture
def bot():
    bot = MockSopel('Sopel')
    bot = rss.__config_define(bot)
    bot.memory['rss']['feeds']['CNBC'] = '#sopel-dev CNBC http://www.cnbc.com/id/100003114/device/rss/rss.html'
    return bot


def test_rssadd_check_feed_valid_feed(bot):
    result = rss.__rssadd_check_feed(bot, '#newchannel', 'newname')
    assert result == 'valid'


def test_rssadd_check_feed_double_feedname(bot):
    result = rss.__rssadd_check_feed(bot, '#newchannel', 'CNBC')
    assert result == 'feed name "CNBC" is already in use, please choose a different name'


def test_rssadd_check_feed_channel_must_start_with_hash(bot):
    result = rss.__rssadd_check_feed(bot, 'nochannel', 'newname')
    assert result == 'channel "nochannel" must start with a "#"'


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
    rb.append('1')
    rb.append('2')
    rb.append('3')
    assert rb.get() == ['1', '2', '3']
    rb.append('4')
    assert rb.get() == ['2', '3', '4']
