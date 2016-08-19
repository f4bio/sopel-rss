# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from sopel.modules import rss

def test_hashEntry():
    hash = rss.__hashEntry('thisisatest')
    assert hash == 'f830f69d23b8224b512a0dc2f5aec974'

def test_hashTableName():
    hash = rss.__hashTableName('thisisatest')
    assert hash == 'rss_f830f69d23b8224b512a0dc2f5aec974'
