# -*- coding: utf-8 -*-
"""Standalone self-check for build_review_text (no Odoo needed).

Run:  python wayakit_customization/tests/test_review_links.py

Guards the one rule that is easy to break and expensive to debug: a WhatsApp
template parameter must be a SINGLE line -- Meta rejects newlines, tabs and runs
of more than 4 spaces, and truncates around 1024 chars.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models'))

from review_text import build_review_text  # noqa: E402


def test_single_line():
    text = build_review_text([
        ('Wayakit  Eco\nPet\tKit', 'https://x.com/shop/product/a#o_product_page_reviews'),
        ('Surface Disinfectant', 'https://x.com/shop/product/b#o_product_page_reviews'),
    ])
    assert '\n' not in text and '\t' not in text, text
    assert not re.search(r' {5,}', text), text
    assert text.count(' | ') == 1, text
    assert text.startswith(
        'Wayakit Eco Pet Kit: https://x.com/shop/product/a#o_product_page_reviews'), text


def test_empty():
    assert build_review_text([]) == ''


def test_url_only_when_no_name():
    assert build_review_text([('', 'https://x.com/p')]) == 'https://x.com/p'


def test_truncates_on_separator():
    items = [('Product %d' % i, 'https://x.com/shop/product/%d' % i) for i in range(60)]
    text = build_review_text(items, max_len=100)
    assert len(text) <= 100, len(text)
    assert not text.endswith(' |') and not text.endswith(' '), repr(text)
    assert text.split(' | ')[-1].startswith('Product '), text


def test_no_truncation_when_short():
    assert build_review_text([('A', 'https://x.com/a')]) == 'A: https://x.com/a'


if __name__ == '__main__':
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok  %s' % name)
    print('all green')
