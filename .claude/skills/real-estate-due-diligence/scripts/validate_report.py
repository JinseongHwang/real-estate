#!/usr/bin/env python3
"""Validate complex-card boundaries before opening a generated HTML report."""
import sys
from html.parser import HTMLParser
from pathlib import Path


class ReportParser(HTMLParser):
    void = set('area base br col embed hr img input link meta param source track wbr'.split())

    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
        self.card_ids = []
        self.chip_ids = []
        self.ids = set()
        self.anchors = []
        self.osm_maps = 0
        self.map_views = 0
        self.saw_osm_attribution = False

    def handle_data(self, data):
        if 'OpenStreetMap contributors' in data:
            self.saw_osm_attribution = True

    def error(self, message):
        self.errors.append(f'line {self.getpos()[0]}: {message}')

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set(attrs.get('class', '').split())
        parent = self.stack[-1] if self.stack else None
        if parent and 'cx-kpis' in parent[1] and 'k' not in classes:
            self.error('.cx-kpis may contain only .k indicators; close it before body content')
        if 'cx' in classes:
            if any('cx' in node[1] for node in self.stack):
                self.error('complex cards must not be nested')
            card_id = attrs.get('id')
            if not card_id or attrs.get('data-cx') != card_id:
                self.error('card id and data-cx must match')
            self.card_ids.append(card_id)
        if 'cx-kpis' in classes and (not parent or 'cx-body' not in parent[1]):
            self.error('.cx-kpis must be directly inside .cx-body')
        if tag == 'svg' and 'osm-map' in classes:
            self.osm_maps += 1
        if 'map-view' in classes:
            self.map_views += 1
        if tag == 'a' and 'data-cx' in attrs:
            self.chip_ids.append(attrs['data-cx'])
        if 'id' in attrs:
            if attrs['id'] in self.ids:
                self.error(f'duplicate id: {attrs["id"]}')
            self.ids.add(attrs['id'])
        if tag == 'a' and attrs.get('href', '').startswith('#') and len(attrs['href']) > 1:
            self.anchors.append(attrs['href'][1:])
        if tag not in self.void:
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        if tag in self.void:
            return
        if not self.stack or self.stack[-1][0] != tag:
            expected = self.stack[-1][0] if self.stack else 'no open element'
            self.error(f'unbalanced </{tag}>; expected </{expected}>')
            return
        self.stack.pop()

    def validate(self):
        if self.stack:
            self.error('unclosed elements: ' + ', '.join(node[0] for node in self.stack))
        if not self.card_ids:
            self.error('no complex cards found')
        if set(self.chip_ids) != {'all', *self.card_ids}:
            self.error('complex filter chips and cards do not match')
        for anchor in set(self.anchors) - self.ids:
            self.error(f'missing anchor target: {anchor}')
        if self.osm_maps:
            if not self.saw_osm_attribution:
                self.error('OpenStreetMap map present but attribution text is missing')
            if self.map_views < self.osm_maps:
                self.error('every svg.osm-map must sit inside a .map-view container')
        return self.errors


def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: python3 validate_report.py REPORT.html')
    parser = ReportParser()
    parser.feed(Path(sys.argv[1]).read_text(encoding='utf-8'))
    errors = parser.validate()
    if errors:
        print('\n'.join(errors))
        raise SystemExit(1)
    print(f'PASS: balanced tags, {len(parser.card_ids)} complex cards, KPI boundaries, filter IDs and anchors, {parser.osm_maps} OSM maps')


if __name__ == '__main__':
    main()
