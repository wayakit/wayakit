#!/usr/bin/env python
"""Standalone self-check: python quality_custom/tests/test_view_xpath.py

Odoo resolves view xpaths only at install time, so a typo costs a full odoo.sh
build cycle to discover. This replays our xpaths against the real Enterprise arch
we inherit, offline.

ponytail: string-matches the target attribute instead of reimplementing Odoo's
view-inheritance engine. Enough to catch a broken xpath; the staging checklist
covers the rest.
"""
import os
import sys
from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
ENTERPRISE = os.path.abspath(os.path.join(
    HERE, '..', '..', '..', 'enterprise'))

# The view we inherit: it is the one that injects the norm/tolerance block.
PARENT_VIEW = os.path.join(
    ENTERPRISE, 'quality_control', 'views', 'quality_views.xml')
PARENT_RECORD_ID = 'quality_point_view_form_inherit_quality_control'

OUR_VIEW = os.path.join(HERE, '..', 'views', 'quality_point_views.xml')

# Keep in sync with views/quality_point_views.xml.
XPATHS = [
    "//label[@for='tolerance_min']",
    "//field[@name='tolerance_min']/..",
]
EXPECTED_INVISIBLE = "test_type not in ('measure', 'worksheet')"


def _arch_of(path, record_id):
    """Return the <arch> element of the ir.ui.view record with the given id."""
    tree = etree.parse(path)
    rec = tree.xpath("//record[@id=$rid]", rid=record_id)
    assert len(rec) == 1, "record %s not found in %s" % (record_id, path)
    arch = rec[0].xpath("./field[@name='arch']")
    assert len(arch) == 1, "no arch on %s" % record_id
    return arch[0]


def test_xpaths_resolve_uniquely():
    """Each xpath must hit exactly one node in the parent arch we inherit."""
    arch = _arch_of(PARENT_VIEW, PARENT_RECORD_ID)
    for expr in XPATHS:
        hits = arch.xpath(expr)
        assert len(hits) == 1, \
            "%s matched %d nodes (need exactly 1)" % (expr, len(hits))


def test_targets_are_the_tolerance_block():
    """Guard against the xpaths silently drifting onto the wrong nodes."""
    arch = _arch_of(PARENT_VIEW, PARENT_RECORD_ID)

    label = arch.xpath(XPATHS[0])[0]
    assert label.tag == 'label', "expected a <label>, got <%s>" % label.tag
    assert label.get('string') == 'Tolerance', label.get('string')

    div = arch.xpath(XPATHS[1])[0]
    assert div.tag == 'div', "expected a <div>, got <%s>" % div.tag
    names = div.xpath(".//field/@name")
    assert names == ['tolerance_min', 'tolerance_max'], names


def test_parent_still_hides_on_measure_only():
    """If Odoo ever relaxes this upstream, our override is dead weight."""
    arch = _arch_of(PARENT_VIEW, PARENT_RECORD_ID)
    for expr in XPATHS:
        node = arch.xpath(expr)[0]
        assert node.get('invisible') == "test_type != 'measure'", \
            "upstream changed to %r -- re-check this module" % node.get('invisible')


def test_our_view_overrides_both_nodes():
    """Our arch must set the same relaxed condition on both target nodes."""
    arch = _arch_of(OUR_VIEW, 'view_quality_point_form_quality_custom')
    exprs = arch.xpath("./xpath/@expr")
    assert exprs == XPATHS, "xpaths drifted from this test: %s" % exprs

    for xp in arch.xpath("./xpath"):
        assert xp.get('position') == 'attributes', xp.get('position')
        attrs = xp.xpath("./attribute[@name='invisible']")
        assert len(attrs) == 1, "expected one invisible attribute"
        assert attrs[0].text == EXPECTED_INVISIBLE, attrs[0].text

    # 'worksheet' is the whole point of this module; 'measure' must survive.
    for token in ("'measure'", "'worksheet'"):
        assert token in EXPECTED_INVISIBLE, token


if __name__ == '__main__':
    if not os.path.isdir(ENTERPRISE):
        sys.exit("enterprise addons not found at %s" % ENTERPRISE)
    for name, fn in sorted(globals().items()):
        if name.startswith('test_'):
            fn()
            print("ok  %s" % name)
    print("\nall good")
