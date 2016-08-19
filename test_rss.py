# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from sopel.modules import rss


def test_hashEntry():
    hash = rss.__hashEntry('thisisatest')
    assert hash == 'f830f69d23b8224b512a0dc2f5aec974'


def test_hashTableName():
    hash = rss.__hashTableName('thisisatest')
    assert hash == 'rss_f830f69d23b8224b512a0dc2f5aec974'


def test_RingBuffer():
    rb = rss.RingBuffer(3)
    rb.append('1')
    assert rb.get() == ['1']
    rb.append('2')
    rb.append('3')
    assert rb.get() == ['1', '2', '3']
    rb.append('4')
    assert rb.get() == ['2', '3', '4']
