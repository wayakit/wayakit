# -*- coding: utf-8 -*-
"""Pure text helpers for the WhatsApp review flow. No Odoo imports on purpose:
same trick as trendyol_connector/models/mapping.py, so tests/test_review_links.py
runs with plain python.
"""

REVIEW_ANCHOR = '#o_product_page_reviews'
DEFAULT_BASE_URL = 'https://ksasystem.wayakit.com'


def build_review_text(items, max_len=900):
    """Join ``(name, url)`` pairs into ONE single line for a WhatsApp free text.

    Meta rejects newlines, tabs and runs of more than 4 spaces inside a template
    parameter value, and truncates it around 1024 chars -- hence the ' | ' join,
    the whitespace squashing and the cap.
    """
    parts = []
    for name, url in items:
        label = ' '.join((name or '').split())  # kills newlines, tabs, space runs
        parts.append('%s: %s' % (label, url) if label else url)
    text = ' | '.join(parts)
    if len(text) > max_len:
        # ponytail: cut on a separator so no half-URL survives; raise max_len only
        # if Meta ever raises the parameter limit.
        text = text[:max_len].rsplit(' | ', 1)[0]
    return text
