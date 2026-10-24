#!/usr/bin/env python3
"""OpenStreetMap 데이터로 임장용 SVG 지도와 도보 동선을 만든다. 표준 라이브러리만 쓴다.

하위 명령
  geocode "<검색어>"                       Nominatim으로 좌표 후보를 찾는다 (1초에 1회 제한을 지킨다)
  find --around LAT,LON [--radius M] "<정규식>"   Overpass로 근처의 이름 있는 OSM 객체를 찾는다
  build spec.json                          지도 SVG와 구간별 도보 거리를 만든다

데이터 출처는 OpenStreetMap contributors (ODbL)다. 결과물에 출처 표기를 반드시 남긴다.
좌표는 커뮤니티 편집 데이터라 "위치 참고" 수준이다. 도보 시간은 4.5km/h 가정이며 신호 대기와 경사를 반영하지 않는다.
"""
import argparse
import hashlib
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = 'imjang-skill/1.0 (personal real-estate research)'
OVERPASS = ['https://overpass-api.de/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter']
NOMINATIM = 'https://nominatim.openstreetmap.org'
ATTRIBUTION = '© OpenStreetMap contributors (ODbL)'
DEFAULT_CACHE = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'imjang-map-cache')

# ── 네트워크와 캐시 ──────────────────────────────────────────────────────────

def _cache_path(cache_dir, key):
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, hashlib.sha1(key.encode('utf-8')).hexdigest() + '.json')


def _post(url, body, timeout):
    """curl이 있으면 curl을 쓴다. 일부 환경에서 urllib 연결이 응답 없이 멈추는 문제가 있었다."""
    curl = shutil.which('curl')
    if curl:
        r = subprocess.run([curl, '-s', '-f', '-m', str(timeout), '-A', UA, '--data-binary', '@-', url],
                           input=body, capture_output=True)
        if r.returncode != 0:
            raise OSError('curl exit %d' % r.returncode)
        return r.stdout
    req = urllib.request.Request(url, data=body, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def overpass(query, cache_dir):
    path = _cache_path(cache_dir, 'ov:' + query)
    if os.path.exists(path):
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    body = urllib.parse.urlencode({'data': query}).encode('utf-8')
    last = None
    for attempt in range(3):
        for ep in OVERPASS:
            try:
                log('Overpass 요청 (%s, %d번째)' % (ep.split('/')[2], attempt + 1))
                data = json.loads(_post(ep, body, 180).decode('utf-8'))
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False)
                return data
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
                last = e
                log('  실패: %s' % e)
        time.sleep(5 * (attempt + 1))
    raise SystemExit('Overpass 요청 실패: %s' % last)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


_last_nominatim = [0.0]


def nominatim(path, params, cache_dir):
    url = NOMINATIM + path + '?' + urllib.parse.urlencode(params)
    cp = _cache_path(cache_dir, 'nm:' + url)
    if os.path.exists(cp):
        with open(cp, encoding='utf-8') as f:
            return json.load(f)
    wait = 1.2 - (time.time() - _last_nominatim[0])
    if wait > 0:
        time.sleep(wait)
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ko'})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.loads(r.read().decode('utf-8'))
    _last_nominatim[0] = time.time()
    with open(cp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    return data

# ── 기하 ────────────────────────────────────────────────────────────────────

def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def local_xy(lat, lon, lat0):
    return (lon * 111320 * math.cos(math.radians(lat0)), lat * 110574)


def centroid(coords):
    """coords: [(lat, lon)]. 닫힌 다각형이면 면적 무게중심, 아니면 중간 지점."""
    if len(coords) < 3 or coords[0] != coords[-1]:
        return coords[len(coords) // 2]
    lat0 = coords[0][0]
    pts = [local_xy(la, lo, lat0) for la, lo in coords]
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        c = x1 * y2 - x2 * y1
        a += c
        cx += (x1 + x2) * c
        cy += (y1 + y2) * c
    if abs(a) < 1e-9:
        return coords[0]
    cx /= 3 * a
    cy /= 3 * a
    return (cy / 110574, cx / (111320 * math.cos(math.radians(lat0))))


def in_poly(lat, lon, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-18) + xi:
            inside = not inside
        j = i
    return inside


def geom_of(el):
    return [(p['lat'], p['lon']) for p in el.get('geometry', [])]

# ── 보행망 ──────────────────────────────────────────────────────────────────

BAD_HIGHWAY = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'proposed', 'construction', 'raceway',
               'bus_guideway', 'escape', 'platform', 'elevator', 'rest_area', 'services', 'corridor'}


def walkable(tags):
    h = tags.get('highway')
    if not h or tags.get('indoor'):
        return False
    foot_ok = tags.get('foot') in ('yes', 'designated', 'permissive')
    if h in BAD_HIGHWAY and not foot_ok:
        return False
    if tags.get('foot') in ('no', 'private'):
        return False
    if tags.get('access') in ('no', 'private') and not foot_ok:
        return False
    if h == 'service' and tags.get('service') in ('parking_aisle', 'driveway') and not foot_ok:
        return False
    return True


class Graph:
    def __init__(self, ways, complex_polys):
        self.adj = {}
        self.xy = {}
        self.polys = complex_polys
        self.pbox = [(min(p[0] for p in poly), min(p[1] for p in poly), max(p[0] for p in poly), max(p[1] for p in poly))
                     for poly in complex_polys]
        for w in ways:
            tags = w.get('tags', {})
            if not walkable(tags):
                continue
            nodes, geom = w.get('nodes', []), geom_of(w)
            if len(nodes) != len(geom):
                continue
            steps = tags.get('highway') == 'steps'
            for i in range(len(nodes) - 1):
                a, b = nodes[i], nodes[i + 1]
                ln = hav(geom[i], geom[i + 1])
                mid = ((geom[i][0] + geom[i + 1][0]) / 2, (geom[i][1] + geom[i + 1][1]) / 2)
                inside = self._inside(mid)
                wt = ln * (3.0 if inside else 1.0) * (1.4 if steps else 1.0)
                self.xy[a], self.xy[b] = geom[i], geom[i + 1]
                self.adj.setdefault(a, []).append((b, wt, ln, steps, inside))
                self.adj.setdefault(b, []).append((a, wt, ln, steps, inside))
        # 끊긴 조각(역 구내 통로, 단지 안 고립 보도)에 스냅되지 않도록 가장 큰 연결 요소만 남긴다
        seen, best = set(), set()
        for start in self.adj:
            if start in seen:
                continue
            comp, stack = {start}, [start]
            while stack:
                u = stack.pop()
                for v, *_ in self.adj[u]:
                    if v not in comp:
                        comp.add(v)
                        stack.append(v)
            seen |= comp
            if len(comp) > len(best):
                best = comp
        self.main = best

    def _inside(self, pt):
        for poly, (s, w, n, e) in zip(self.polys, self.pbox):
            if s <= pt[0] <= n and w <= pt[1] <= e and in_poly(pt[0], pt[1], poly):
                return True
        return False

    def snap(self, pt):
        best, bd = None, 1e18
        for nid, c in self.xy.items():
            if nid not in self.main:
                continue
            d = abs(c[0] - pt[0]) * 110574 + abs(c[1] - pt[1]) * 88000
            if d < bd:
                best, bd = nid, d
        return best, (hav(pt, self.xy[best]) if best else None)

    def path(self, a, b, penalize=True):
        dist = {a: 0.0}
        prev = {}
        pq = [(0.0, a)]
        while pq:
            d, u = heapq.heappop(pq)
            if u == b:
                break
            if d > dist.get(u, 1e18):
                continue
            for v, wt, ln, steps, inside in self.adj.get(u, []):
                nd = d + (wt if penalize else ln * (1.4 if steps else 1.0))
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = (u, ln, steps, inside)
                    heapq.heappush(pq, (nd, v))
        if b not in prev and a != b:
            return None
        nodes = [b]
        meters = steps_m = inside_m = 0.0
        cur = b
        while cur != a:
            u, ln, steps, inside = prev[cur]
            meters += ln
            steps_m += ln if steps else 0
            inside_m += ln if inside else 0
            nodes.append(u)
            cur = u
        nodes.reverse()
        return {'coords': [self.xy[n] for n in nodes], 'nodes': nodes, 'meters': meters, 'steps_m': steps_m, 'inside_m': inside_m}

# ── 지도 그리기 ─────────────────────────────────────────────────────────────

ROAD = {  # 폭(m), 그리는 순서
    'primary': (20, 3), 'primary_link': (12, 3), 'secondary': (17, 3), 'secondary_link': (11, 3),
    'tertiary': (14, 2), 'tertiary_link': (9, 2), 'unclassified': (10, 1), 'residential': (9, 1),
    'living_street': (8, 1), 'service': (5, 0), 'pedestrian': (7, 1),
}
PATHS = {'footway': 2.2, 'path': 2.0, 'cycleway': 2.2, 'steps': 2.6, 'track': 2.4}
LABEL_ROADS = {'primary', 'secondary', 'tertiary', 'unclassified', 'residential'}
PALETTE = ['#1b64da', '#0a7d43', '#7048e8', '#0c8599', '#c2255c', '#5c7cfa']
ROUTE_COLOR = '#d6336c'
KIND_STYLE = {  # (배경색, 글자)
    'school': ('#b45309', '학'), 'park': ('#2f9e44', '공'), 'station': ('#123c73', '역'), 'poi': ('#5f6b7a', '·'),
}


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;'))


def text_w(s, fs):
    return sum((1.0 if ord(c) > 0x2e80 else 0.58) for c in s) * fs


class Proj:
    def __init__(self, bbox, width, max_aspect=1.0, min_aspect=0.42):
        s, w, n, e = bbox
        lat0 = (s + n) / 2
        kx, ky = 111320 * math.cos(math.radians(lat0)), 110574
        wm, hm = (e - w) * kx, (n - s) * ky
        if hm / wm > max_aspect:
            extra = (hm / max_aspect - wm) / 2
            w, e = w - extra / kx, e + extra / kx
            wm = hm / max_aspect
        elif hm / wm < min_aspect:
            extra = (wm * min_aspect - hm) / 2
            s, n = s - extra / ky, n + extra / ky
            hm = wm * min_aspect
        self.s, self.w, self.n, self.e, self.kx, self.ky = s, w, n, e, kx, ky
        self.W, self.k = width, width / wm
        self.H = hm * self.k

    def xy(self, lat, lon):
        return ((lon - self.w) * self.kx * self.k, (self.n - lat) * self.ky * self.k)

    def inside(self, lat, lon, margin=0.0):
        x, y = self.xy(lat, lon)
        return -margin <= x <= self.W + margin and -margin <= y <= self.H + margin

    def bbox(self):
        return (self.s, self.w, self.n, self.e)


def pts_d(proj, coords, close=False):
    parts = []
    for i, (la, lo) in enumerate(coords):
        x, y = proj.xy(la, lo)
        parts.append(('M' if i == 0 else 'L') + '%.1f %.1f' % (x, y))
    return ' '.join(parts) + (' Z' if close else '')


def near_view(proj, coords, margin=40):
    return any(proj.inside(la, lo, margin) for la, lo in coords)


class Labels:
    def __init__(self, W, H):
        self.W, self.H, self.rects = W, H, []

    def add(self, r):
        self.rects.append(r)

    def free(self, r):
        if r[0] < 2 or r[1] < 2 or r[2] > self.W - 2 or r[3] > self.H - 2:
            return False
        return all(r[2] < q[0] or r[0] > q[2] or r[3] < q[1] or r[1] > q[3] for q in self.rects)

    def place(self, x, y, text, fs, mr=0, only=None):
        w, h = text_w(text, fs) + 4, fs * 1.3
        g = mr + 3
        opts = [('r', x + g, y - h / 2), ('l', x - g - w, y - h / 2), ('t', x - w / 2, y - g - h), ('b', x - w / 2, y + g),
                ('tr', x + g, y - g - h), ('tl', x - g - w, y - g - h), ('br', x + g, y + g), ('bl', x - g - w, y + g),
                ('r2', x + g + 12, y - h / 2 - 10), ('l2', x - g - 12 - w, y - h / 2 - 10),
                ('t2', x - w / 2, y - g - h - 12), ('b2', x - w / 2, y + g + 12)]
        if only:
            opts = [o for o in opts if o[0] in only] or opts
        for key, rx, ry in opts:
            r = (rx, ry, rx + w, ry + h)
            if self.free(r):
                self.add(r)
                return rx + 2, ry + h * 0.78, 'start'
        for dist in range(24, 120, 8):
            for ang in range(0, 360, 30):
                rx = x + math.cos(math.radians(ang)) * dist - w / 2
                ry = y + math.sin(math.radians(ang)) * dist - h / 2
                r = (rx, ry, rx + w, ry + h)
                if self.free(r):
                    self.add(r)
                    return rx + 2, ry + h * 0.78, 'start'
        key, rx, ry = opts[0]
        self.add((rx, ry, rx + w, ry + h))
        return rx + 2, ry + h * 0.78, 'start'

    def place_center(self, x, y, text, fs):
        w, h = text_w(text, fs) + 4, fs * 1.3
        r = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
        dy = 0
        for dy in (0, -h - 2, h + 2, -2 * h - 4, 2 * h + 4):
            r = (x - w / 2, y + dy - h / 2, x + w / 2, y + dy + h / 2)
            if self.free(r):
                break
        self.add(r)
        return x, y + dy + fs * 0.35, 'middle'


def interior_point(proj, poly, text, fs):
    xy = [proj.xy(*c) for c in poly]
    xs, ys = [p[0] for p in xy], [p[1] for p in xy]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    tw = text_w(text, fs) / 2

    def inside(x, y):
        c, j = False, len(xy) - 1
        for i in range(len(xy)):
            (xi, yi), (xj, yj) = xy[i], xy[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
                c = not c
            j = i
        return c

    def edge_dist(x, y):
        best = 1e9
        for (ax, ay), (bx, by) in zip(xy, xy[1:]):
            dx, dy = bx - ax, by - ay
            t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy + 1e-12)))
            best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
        return best

    full, loose = [], []
    for i in range(1, 16):
        for j in range(1, 16):
            x, y = x0 + (x1 - x0) * i / 16, y0 + (y1 - y0) * j / 16
            if not inside(x, y):
                continue
            (full if inside(x - tw, y) and inside(x + tw, y) else loose).append((edge_dist(x, y), x, y))
    cands = sorted(full, reverse=True) + sorted(loose, reverse=True)
    return [(x, y) for _, x, y in cands]


def halo(extra=''):
    return 'stroke="#fff" stroke-width="3.2" stroke-linejoin="round" paint-order="stroke" %s' % extra


def nice_scale(k):
    for ln in (50, 100, 200, 250, 500, 1000, 2000):
        if 80 <= ln * k <= 170:
            return ln
    return 200


def render_map(spec_map, proj, data, pts, legs, offmap, colors, uid):
    W, H = proj.W, proj.H
    k = proj.k
    out = []
    labels = Labels(W, H)
    defs = []
    out.append('<rect width="%.0f" height="%.0f" fill="#f4f3ee"/>' % (W, H))
    layers = set(spec_map.get('layers', ['water', 'parks', 'complexes', 'roads', 'rail']))

    def poly_path(el):
        return pts_d(proj, geom_of(el), close=True)

    # 물과 녹지
    if 'water' in layers:
        for el in data['water']:
            if near_view(proj, geom_of(el)):
                if el['_closed']:
                    out.append('<path d="%s" fill="#cfe3f2"/>' % poly_path(el))
                else:
                    out.append('<path d="%s" fill="none" stroke="#a8cce6" stroke-width="%.1f" stroke-linecap="round" stroke-linejoin="round"/>'
                               % (pts_d(proj, geom_of(el)), max(1.8, el['_width'] * k)))
    if 'parks' in layers:
        for el in data['parks']:
            if el['_closed'] and near_view(proj, geom_of(el)):
                out.append('<path d="%s" fill="#d8ebd0"/>' % poly_path(el))
    # 건물
    if 'buildings' in layers:
        d = ' '.join(pts_d(proj, geom_of(el), close=True) for el in data['buildings'] if el['_closed'] and near_view(proj, geom_of(el), 10))
        if d:
            out.append('<path d="%s" fill="#e1e3e6"/>' % d)
    # 비교 대상이 아닌 이름 있는 주거지(맥락용)
    target_ids = {p['osm_id'] for p in pts.values() if p.get('osm_id') and p.get('poly')}
    if 'complexes' in layers:
        for el in data['complexes']:
            if el['id'] in target_ids or not el['_closed'] or not near_view(proj, geom_of(el)):
                continue
            out.append('<path d="%s" fill="#e8e9ee" stroke="#d3d6dc" stroke-width="1"/>' % poly_path(el))
    # 도로
    if 'roads' in layers:
        rows = []
        for el in data['roads']:
            h = el['tags'].get('highway')
            if h in ROAD or h in PATHS:
                if near_view(proj, geom_of(el)):
                    rows.append(el)
        rows.sort(key=lambda e: ROAD.get(e['tags']['highway'], (0, -1))[1])
        casing, fill = [], []
        for el in rows:
            h = el['tags']['highway']
            tunnel = el['tags'].get('tunnel') in ('yes', 'building_passage', 'culvert')
            d = pts_d(proj, geom_of(el))
            if h in ROAD:
                wpx = max(2.4, ROAD[h][0] * k)
                col = {'primary': '#fbe4a3', 'primary_link': '#fbe4a3', 'secondary': '#fdefc4', 'secondary_link': '#fdefc4'}.get(h, '#ffffff')
                dash = ' stroke-dasharray="5 3"' if tunnel else ''
                casing.append('<path d="%s" stroke="#c4c9d0" stroke-width="%.1f"%s/>' % (d, wpx + 1.6, dash))
                fill.append('<path d="%s" stroke="%s" stroke-width="%.1f"%s/>' % (d, col, wpx, dash))
            else:
                col = '#b9803f' if h == 'steps' else '#aab1ba'
                fill.append('<path d="%s" stroke="%s" stroke-width="%.1f" stroke-dasharray="%s"/>'
                            % (d, col, max(1.1, PATHS[h] * k), '1.5 1.8' if h == 'steps' else '3 2'))
        out.append('<g fill="none" stroke-linecap="round" stroke-linejoin="round">%s%s</g>' % (''.join(casing), ''.join(fill)))
    # 철도
    if 'rail' in layers:
        for el in data['rails']:
            if near_view(proj, geom_of(el)):
                d = pts_d(proj, geom_of(el))
                out.append('<path d="%s" fill="none" stroke="#7a828c" stroke-width="3" stroke-linejoin="round"/>'
                           '<path d="%s" fill="none" stroke="#fff" stroke-width="1.2" stroke-dasharray="6 6"/>' % (d, d))
    # 도로 이름(경로에 맞춰 글자 배치)
    if 'roads' in layers and spec_map.get('road_labels', True):
        best = {}
        for el in data['roads']:
            nm, h = el['tags'].get('name'), el['tags'].get('highway')
            if not nm or h not in LABEL_ROADS:
                continue
            run, runs = [], []
            for la, lo in geom_of(el):
                if proj.inside(la, lo, 4):
                    run.append((la, lo))
                else:
                    if len(run) > 1:
                        runs.append(run)
                    run = []
            if len(run) > 1:
                runs.append(run)
            for r in runs:
                xy = [proj.xy(*p) for p in r]
                ln = sum(math.dist(a, b) for a, b in zip(xy, xy[1:]))
                if ln >= text_w(nm, 8.5) + 24 and ln > best.get(nm, (0,))[0]:
                    best[nm] = (ln, xy)
        for i, (nm, (ln, xy)) in enumerate(sorted(best.items(), key=lambda kv: -kv[1][0])[:14]):
            dx, dy = xy[-1][0] - xy[0][0], xy[-1][1] - xy[0][1]
            if (abs(dx) >= abs(dy) and dx < 0) or (abs(dx) < abs(dy) and dy > 0):
                xy = xy[::-1]
            pid = '%s-rl%d' % (uid, i)
            defs.append('<path id="%s" d="%s"/>' % (pid, ' '.join(('M' if j == 0 else 'L') + '%.1f %.1f' % p for j, p in enumerate(xy))))
            out.append('<text font-size="8.5" fill="#5b6470" %s><textPath href="#%s" startOffset="50%%" text-anchor="middle">%s</textPath></text>'
                       % (halo('stroke-width="2.6"'), pid, esc(nm)))
            mid = xy[len(xy) // 2]
            labels.add((mid[0] - text_w(nm, 8.5) / 2, mid[1] - 8, mid[0] + text_w(nm, 8.5) / 2, mid[1] + 8))
    # 대상 단지 영역
    shapes = []
    for pid, p in pts.items():
        if p['id'] not in spec_map.get('show', []) and not spec_map.get('show_all'):
            continue
        if p.get('poly') and p['kind'] == 'complex':
            col = colors[p.get('group', pid)]
            shapes.append('<path d="%s" fill="%s" fill-opacity="0.2" stroke="%s" stroke-width="1.8"/>'
                          % (pts_d(proj, p['poly'], close=True), col, col))
        elif p.get('poly') and p['kind'] in ('school', 'park'):
            col = '#2f9e44' if p['kind'] == 'park' else '#b45309'
            shapes.append('<path d="%s" fill="%s" fill-opacity="0.16" stroke="%s" stroke-width="1.4" stroke-dasharray="4 2"/>'
                          % (pts_d(proj, p['poly'], close=True), col, col))
    out.extend(shapes)
    # 경로
    route_svg, stop_svg = [], []
    for leg in legs:
        if not leg.get('coords'):
            continue
        d = pts_d(proj, leg['coords'])
        if leg['optional']:
            route_svg.append('<path d="%s" fill="none" stroke="#123c73" stroke-opacity="0.75" stroke-width="2.6" stroke-dasharray="6 5" stroke-linecap="round" stroke-linejoin="round"/>' % d)
        else:
            route_svg.append('<path d="%s" fill="none" stroke="#fff" stroke-width="7.5" stroke-linecap="round" stroke-linejoin="round"/>'
                             '<path d="%s" fill="none" stroke="%s" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>'
                             % (d, d, ROUTE_COLOR))
            xy = [proj.xy(*c) for c in leg['coords']]
            tot = sum(math.dist(a, b) for a, b in zip(xy, xy[1:]))
            acc, target = 0.0, tot * 0.55
            for a, b in zip(xy, xy[1:]):
                seg = math.dist(a, b)
                if seg and acc + seg >= target:
                    t = (target - acc) / seg
                    px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
                    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
                    route_svg.append('<path d="M-5 -4.5L5 0L-5 4.5Z" fill="#fff" stroke="%s" stroke-width="1.6" stroke-linejoin="round" transform="translate(%.1f %.1f) rotate(%.0f)"/>' % (ROUTE_COLOR, px, py, ang))
                    break
                acc += seg
    out.extend(route_svg)
    for leg in legs:
        for c in leg.get('coords') or []:
            px, py = proj.xy(*c)
            labels.add((px - 4, py - 4, px + 4, py + 4))
        xy = [proj.xy(*c) for c in leg.get('coords') or []]
        for a, b in zip(xy, xy[1:]):
            n = int(math.dist(a, b) // 8)
            for i in range(1, n):
                px, py = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
                labels.add((px - 4, py - 4, px + 4, py + 4))
    # 마커
    marker_svgs, label_jobs = [], []
    stop_points = {st['point'] for st in spec_map.get('_stops', [])}
    placed_stops = []
    for stop in spec_map.get('_stops', []):
        x0, y0 = proj.xy(*stop['xy'])
        if not (0 <= x0 <= W and 0 <= y0 <= H):
            continue
        x, y = x0, y0
        for _ in range(12):
            near = [(px, py) for px, py in placed_stops if math.hypot(x - px, y - py) < 24]
            if not near:
                break
            px, py = near[0]
            dx, dy = x - px, y - py
            d = math.hypot(dx, dy)
            if d < 1:
                dx, dy, d = 0.0, -1.0, 1.0
            x, y = px + dx / d * 25, py + dy / d * 25
        placed_stops.append((x, y))
        if math.hypot(x - x0, y - y0) > 1:
            marker_svgs.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#191f28" stroke-width="1.6"/>'
                               '<circle cx="%.1f" cy="%.1f" r="3" fill="#191f28" stroke="#fff" stroke-width="1.2"/>' % (x0, y0, x, y, x0, y0))
        labels.add((x - 11, y - 11, x + 11, y + 11))
        marker_svgs.append('<g><title>%s</title><circle cx="%.1f" cy="%.1f" r="10.5" fill="#191f28" stroke="#fff" stroke-width="2"/>'
                           '<text x="%.1f" y="%.1f" font-size="12" font-weight="700" fill="#fff" text-anchor="middle">%d</text></g>'
                           % (esc(stop['label']), x, y, x, y + 4.2, stop['n']))
        if pts[stop['point']]['kind'] != 'complex':
            label_jobs.append((x, y, stop['label'], 11.5, 10.5, '#191f28', 'stop'))
    for pid, p in pts.items():
        if p['id'] not in spec_map.get('show', []) and not spec_map.get('show_all'):
            continue
        if p['kind'] == 'access' or (pid in stop_points and p['kind'] != 'complex'):
            continue
        la, lo = p['lat'], p['lon']
        if not proj.inside(la, lo, 0):
            continue
        x, y = proj.xy(la, lo)
        link = p.get('href')
        if p['kind'] == 'complex':
            col = colors[p.get('group', pid)]
            x, y = proj.xy(*p['center'])
            placed = None
            if p.get('poly'):
                w, h = text_w(p['label'], 12) + 4, 12 * 1.3
                for cx_, cy_ in interior_point(proj, p['poly'], p['label'], 12)[:60]:
                    r = (cx_ - w / 2, cy_ - h / 2, cx_ + w / 2, cy_ + h / 2)
                    if labels.free(r):
                        labels.add(r)
                        placed = (cx_, cy_ + 12 * 0.35, 'middle')
                        break
            if not placed:
                # 단지 안에 자리가 없으면 단지 둘레에서 겹치지 않는 자리를 찾는다
                tx, ty, anc = labels.place(x, y, p['label'], 12, mr=6)
            else:
                tx, ty, anc = placed
            g = '<text x="%.1f" y="%.1f" font-size="12" font-weight="700" fill="%s" text-anchor="%s" %s>%s</text>' % (tx, ty, col, anc, halo(), esc(p['label']))
            if link:
                g = '<a href="%s"><title>%s 카드로 이동</title>%s</a>' % (esc(link), esc(p['label']), g)
            marker_svgs.append(g)
        else:
            bg, ch = KIND_STYLE.get(p['kind'], KIND_STYLE['poi'])
            r = 7.5
            labels.add((x - r - 1, y - r - 1, x + r + 1, y + r + 1))
            marker_svgs.append('<g><title>%s</title><rect x="%.1f" y="%.1f" width="%d" height="%d" rx="3.5" fill="%s" stroke="#fff" stroke-width="1.5"/>'
                               '<text x="%.1f" y="%.1f" font-size="9.5" font-weight="700" fill="#fff" text-anchor="middle">%s</text></g>'
                               % (esc(p['label']), x - r, y - r, 2 * r, 2 * r, bg, x, y + 3.4, ch))
            label_jobs.append((x, y, p['label'] + spec_map.get('_suffix', {}).get(pid, ''), 10.5, r, '#2b3440', 'poi'))
    out.extend(marker_svgs)
    for x, y, text, fs, mr, col, kind in label_jobs:
        tx, ty, anc = labels.place(x, y, text, fs, mr)
        out.append('<text x="%.1f" y="%.1f" font-size="%s" font-weight="%s" fill="%s" text-anchor="%s" %s>%s</text>'
                   % (tx, ty, fs, '700', col, anc, halo(), esc(text)))
    # 지도 밖 지점 화살표 (가장자리에 화살표, 그 안쪽에 흰 바탕 안내)
    for item in offmap:
        la, lo = item['lat'], item['lon']
        if proj.inside(la, lo, 0):
            continue
        cx, cy = W / 2, H / 2
        x, y = proj.xy(la, lo)
        dx, dy = x - cx, y - cy
        mx, my = W / 2 - 14, H / 2 - 14
        t = min(mx / abs(dx) if dx else 1e9, my / abs(dy) if dy else 1e9)
        ax, ay = cx + dx * t, cy + dy * t
        ang = math.degrees(math.atan2(dy, dx))
        out.append('<path d="M-7 -6L8 0L-7 6Z" fill="#123c73" stroke="#fff" stroke-width="1.5" stroke-linejoin="round" transform="translate(%.1f %.1f) rotate(%.0f)"/>' % (ax, ay, ang))
        txt = item['label']
        fs = 10.5
        w, h = text_w(txt, fs) + 14, fs + 9
        ux, uy = -dx / math.hypot(dx, dy), -dy / math.hypot(dx, dy)
        placed = None
        for step in range(0, 14):
            for side in (0, 1, -1):
                bx = ax + ux * (14 + step * 8) - w / 2 + side * (w / 2 + 10) * (abs(uy) > 0.7)
                by = ay + uy * (14 + step * 8) - h / 2 + side * (h + 4) * (abs(uy) <= 0.7)
                bx, by = min(max(bx, 4), W - w - 4), min(max(by, 4), H - h - 22)
                r = (bx, by, bx + w, by + h)
                if labels.free(r):
                    placed = r
                    break
            if placed:
                break
        if not placed:
            placed = (min(max(ax - w, 4), W - w - 4), min(max(ay - h, 4), H - h - 22), 0, 0)
            placed = (placed[0], placed[1], placed[0] + w, placed[1] + h)
        labels.add(placed)
        bx, by = placed[0], placed[1]
        out.append('<g><rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="#fff" fill-opacity="0.94" stroke="#123c73" stroke-width="1"/>'
                   '<text x="%.1f" y="%.1f" font-size="%s" font-weight="700" fill="#123c73">%s</text></g>'
                   % (bx, by, w, h, h / 2, bx + 7, by + h / 2 + fs * 0.36, fs, esc(txt)))
    # 축척, 방위, 출처
    ln = nice_scale(k)
    bx, by = 14, H - 26
    out.append('<g><rect x="%d" y="%d" width="%.1f" height="3" fill="#2b3440"/><text x="%d" y="%d" font-size="10" fill="#2b3440" %s>%s</text></g>'
               % (bx, by, ln * k, bx, by - 4, halo('stroke-width="2.4"'), ('%d m' % ln) if ln < 1000 else ('%d km' % (ln // 1000))))
    out.append('<g transform="translate(%.0f 30)"><path d="M0 -14L6 4L0 0L-6 4Z" fill="#2b3440"/><text y="18" font-size="10" font-weight="700" fill="#2b3440" text-anchor="middle">N</text></g>' % (W - 24))
    out.append('<text x="%.0f" y="%.0f" font-size="9" fill="#6b7684" text-anchor="end" %s>%s</text>' % (W - 8, H - 7, halo('stroke-width="2.4"'), ATTRIBUTION))
    title = spec_map.get('title', '지도')
    return ('<svg class="osm-map" id="%s" viewBox="0 0 %.0f %.0f" role="img" aria-label="%s" xmlns="http://www.w3.org/2000/svg" '
            'font-family="-apple-system,BlinkMacSystemFont,\'Apple SD Gothic Neo\',Pretendard,\'Noto Sans KR\',\'Malgun Gothic\',sans-serif">'
            '<defs>%s</defs>%s</svg>') % (uid, W, H, esc(spec_map.get('aria', title)), ''.join(defs), ''.join(out))

# ── 데이터 가져오기 ─────────────────────────────────────────────────────────

def bbox_str(b):
    return '%.6f,%.6f,%.6f,%.6f' % b


def classify(els):
    data = {'roads': [], 'rails': [], 'water': [], 'parks': [], 'complexes': [], 'buildings': [], 'schools': []}
    for el in els:
        if el['type'] not in ('way', 'relation'):
            continue
        t = el.get('tags', {})
        geoms = []
        if el['type'] == 'way':
            geoms = [el]
        else:
            for m in el.get('members', []):
                if m.get('type') == 'way' and m.get('role') in ('outer', '') and m.get('geometry'):
                    geoms.append({'type': 'way', 'id': el['id'], 'tags': t, 'geometry': m['geometry'], 'nodes': []})
        for g in geoms:
            gg = geom_of(g)
            g['_closed'] = len(gg) > 3 and gg[0] == gg[-1]
            g.setdefault('tags', t)
            if t.get('highway'):
                data['roads'].append(g)
            elif t.get('railway') in ('rail', 'subway', 'light_rail', 'narrow_gauge'):
                data['rails'].append(g)
            elif t.get('waterway') or t.get('natural') == 'water':
                g['_width'] = {'river': 14, 'canal': 8}.get(t.get('waterway'), 4)
                data['water'].append(g)
            elif t.get('leisure') in ('park', 'garden', 'playground', 'recreation_ground') or t.get('natural') == 'wood' or t.get('landuse') in ('forest', 'grass'):
                data['parks'].append(g)
            elif t.get('landuse') == 'residential' and t.get('name'):
                data['complexes'].append(g)
            elif t.get('building'):
                data['buildings'].append(g)
    return data


def fetch_points(spec_points, cache_dir):
    ids = {'node': [], 'way': [], 'relation': []}
    for p in spec_points:
        if p.get('osm'):
            typ, num = p['osm'].split('/')
            ids[typ].append(num)
    parts = []
    for typ, nums in ids.items():
        if nums:
            parts.append('%s(id:%s);' % (typ, ','.join(nums)))
    if not parts:
        return {}
    res = overpass('[out:json][timeout:60];(%s);out geom;' % ''.join(parts), cache_dir)
    return {'%s/%s' % (e['type'], e['id']): e for e in res['elements']}


def resolve_points(spec_points, cache_dir):
    found = fetch_points(spec_points, cache_dir)
    pts = {}
    for i, p in enumerate(spec_points):
        q = dict(p)
        q.setdefault('kind', 'poi')
        if p.get('osm'):
            el = found.get(p['osm'])
            if not el:
                raise SystemExit('OSM 객체를 찾지 못했다: %s (%s)' % (p['osm'], p['id']))
            q['osm_id'] = el['id']
            if el['type'] == 'node':
                q['lat'], q['lon'] = el['lat'], el['lon']
                q['center'] = (el['lat'], el['lon'])
            else:
                if el['type'] == 'relation':
                    ring = []
                    for m in el.get('members', []):
                        if m.get('role') == 'outer' and m.get('geometry'):
                            ring = geom_of(m)
                            break
                else:
                    ring = geom_of(el)
                if not ring:
                    raise SystemExit('지오메트리가 없다: %s' % p['osm'])
                c = centroid(ring)
                q['lat'], q['lon'], q['center'] = c[0], c[1], c
                if len(ring) > 3 and ring[0] == ring[-1]:
                    q['poly'] = ring
            q['source'] = 'OSM ' + p['osm']
        else:
            if 'lat' not in p:
                raise SystemExit('좌표가 없다: %s' % p['id'])
            q['center'] = (p['lat'], p['lon'])
            q['source'] = p.get('source', '직접 입력')
        pts[p['id']] = q
    return pts


def fit_bbox(pts, ids, pad_m):
    la, lo = [], []
    for i in ids:
        p = pts[i]
        for c in (p.get('poly') or [(p['lat'], p['lon'])]):
            la.append(c[0])
            lo.append(c[1])
    lat0 = (min(la) + max(la)) / 2
    dlat = pad_m / 110574
    dlon = pad_m / (111320 * math.cos(math.radians(lat0)))
    return (min(la) - dlat, min(lo) - dlon, max(la) + dlat, max(lo) + dlon)


def kakao_name(s):
    return urllib.parse.quote(s.replace(',', ' '))


def build(spec_path):
    spec = json.load(open(spec_path, encoding='utf-8'))
    out_dir = spec.get('out_dir', '.')
    cache_dir = spec.get('cache_dir', DEFAULT_CACHE)
    os.makedirs(out_dir, exist_ok=True)
    pts = resolve_points(spec['points'], cache_dir)
    groups = []
    for p in spec['points']:
        if p.get('kind') == 'complex' and p.get('group', p['id']) not in groups:
            groups.append(p.get('group', p['id']))
    colors = {g: PALETTE[i % len(PALETTE)] for i, g in enumerate(groups)}
    walk = spec.get('walk_m_per_min', 75)

    # 지도마다 범위를 정한다
    projs = {}
    for m in spec['maps']:
        ids = m.get('fit') or list(pts)
        bb = fit_bbox(pts, ids, m.get('pad_m', 250))
        projs[m['id']] = Proj(bb, m.get('width', 760), m.get('max_aspect', 1.0), m.get('min_aspect', 0.42))
    # 보행망 범위: 지도 범위 + 경로 양 끝 지점 + 여유
    rt = spec.get('route')
    graph_ids = set()
    if rt:
        for st in rt['stops']:
            graph_ids.add(st['point'])
            if st.get('access'):
                graph_ids.add(st['access'])
        for o in rt.get('optional', []):
            graph_ids.add(o['from'])
            graph_ids.add(o['to'])
    union = [projs[m['id']].bbox() for m in spec['maps']]
    if graph_ids:
        union.append(fit_bbox(pts, sorted(graph_ids), spec.get('graph_pad_m', 350)))
    ub = (min(b[0] for b in union), min(b[1] for b in union), max(b[2] for b in union), max(b[3] for b in union))
    q = ('[out:json][timeout:120];('
         'way["highway"](%(b)s);way["railway"~"^(rail|subway|light_rail|narrow_gauge)$"](%(b)s);way["waterway"~"^(river|stream|canal|drain)$"](%(b)s);'
         'way["natural"~"^(water|wood)$"](%(b)s);way["leisure"~"^(park|garden|playground|recreation_ground)$"](%(b)s);'
         'way["landuse"~"^(forest|grass)$"](%(b)s);way["landuse"="residential"]["name"](%(b)s);'
         'relation["natural"="water"](%(b)s);relation["leisure"="park"](%(b)s););out geom;') % {'b': bbox_str(ub)}
    data = classify(overpass(q, cache_dir)['elements'])
    bm = [projs[m['id']].bbox() for m in spec['maps'] if 'buildings' in m.get('layers', [])]
    data['buildings'] = []
    for b in bm:
        qb = '[out:json][timeout:120];way["building"](%s);out geom;' % bbox_str(b)
        data['buildings'] += classify(overpass(qb, cache_dir)['elements'])['buildings']

    result = {'attribution': ATTRIBUTION, 'points': {}, 'legs': [], 'maps': {}, 'links': {}, 'walk_m_per_min': walk}
    for pid, p in pts.items():
        result['points'][pid] = {k: p[k] for k in ('id', 'label', 'kind', 'lat', 'lon', 'source') if k in p}
    # 도보 경로
    stops_xy, legs_all = [], []
    if rt:
        polys = [geom_of(e) for e in data['complexes'] if e['_closed']]
        g = Graph(data['roads'], polys)

        def access_pt(st):
            p = pts[st.get('access') or st['point']]
            tgt = st.get('access_edge_toward')
            if tgt and pts[st['point']].get('poly'):
                t = pts[tgt]
                return min(pts[st['point']]['poly'], key=lambda c: hav(c, (t['lat'], t['lon'])))
            return (p['lat'], p['lon'])

        nodes = []
        for n, st in enumerate(rt['stops'], 1):
            nid, sd = g.snap(access_pt(st))
            nodes.append(nid)
            stops_xy.append({'n': n, 'label': st.get('label') or pts[st['point']]['label'], 'xy': g.xy[nid], 'snap_m': round(sd, 1), 'point': st['point']})
        # on_path: 공원처럼 지나가며 보는 지점은 앞뒤 지점을 잇는 경로 위에서 가장 가까운 점으로 잡는다 (들어갔다 되돌아 나오는 고리 방지)
        for i, st in enumerate(rt['stops']):
            if not st.get('on_path') or i == 0 or i == len(rt['stops']) - 1:
                continue
            through = g.path(nodes[i - 1], nodes[i + 1])
            if not through:
                continue
            p = pts[st['point']]
            targets = p.get('poly') or [(p['lat'], p['lon'])]

            def gap(nd):
                if p.get('poly') and in_poly(g.xy[nd][0], g.xy[nd][1], p['poly']):
                    return 0.0
                return min(hav(g.xy[nd], t) for t in targets)
            best = min(through['nodes'], key=gap)
            if gap(best) > 40:
                # 앞뒤를 잇는 길이 지점 근처를 지나지 않는다 (막다른 공원 등). 앞 지점에서 지점 중심으로 가는 길이 지점 경계에 처음 닿는 곳(입구)을 쓴다
                inward = g.path(nodes[i - 1], nodes[i])
                if inward:
                    best = next((nd for nd in inward['nodes'] if gap(nd) <= 25), nodes[i])
                else:
                    best = nodes[i]
                stops_xy[i]['entrance'] = True
            nodes[i] = best
            stops_xy[i]['xy'] = g.xy[best]
            inside = p.get('poly') and in_poly(g.xy[best][0], g.xy[best][1], p['poly'])
            stops_xy[i]['snap_m'] = 0.0 if inside else round(min(hav(g.xy[best], t) for t in targets), 1)
        for i in range(len(nodes) - 1):
            chain = [nodes[i]]
            via_labels = []
            for vid in rt['stops'][i].get('via', []):
                chain.append(g.snap((pts[vid]['lat'], pts[vid]['lon']))[0])
                via_labels.append(pts[vid]['label'])
            chain.append(nodes[i + 1])
            def run(penalize):
                acc = {'coords': [], 'meters': 0.0, 'steps_m': 0.0, 'inside_m': 0.0}
                for a, b in zip(chain, chain[1:]):
                    part = g.path(a, b, penalize)
                    if not part:
                        return None
                    acc['coords'] += part['coords'] if not acc['coords'] else part['coords'][1:]
                    for key in ('meters', 'steps_m', 'inside_m'):
                        acc[key] += part[key]
                return acc
            r = run(True)
            alt = run(False)
            leg = {'from': stops_xy[i]['label'], 'to': stops_xy[i + 1]['label'], 'optional': False, 'n_from': i + 1, 'n_to': i + 2}
            if via_labels:
                leg['via'] = via_labels
            if r and alt and alt['meters'] < r['meters'] * 0.85 and alt['inside_m'] > r['inside_m']:
                leg['alt'] = {'meters': round(alt['meters']), 'minutes': max(1, round(alt['meters'] / walk)),
                              'inside_complex_m': round(alt['inside_m']), 'coords': alt['coords']}
            if r:
                leg.update(coords=r['coords'], meters=round(r['meters']), minutes=max(1, round(r['meters'] / walk)),
                           steps_m=round(r['steps_m']), inside_complex_m=round(r['inside_m']))
            legs_all.append(leg)
        for o in rt.get('optional', []):
            a, sd1 = g.snap((pts[o['from']]['lat'], pts[o['from']]['lon']))
            b, sd2 = g.snap((pts[o['to']]['lat'], pts[o['to']]['lon']))
            r = g.path(a, b)
            leg = {'from': pts[o['from']]['label'], 'to': pts[o['to']]['label'], 'optional': True, 'note': o.get('note', ''),
                   'from_id': o['from'], 'to_id': o['to'], 'maps': o.get('maps')}
            if r:
                leg.update(coords=r['coords'], meters=round(r['meters']), minutes=max(1, round(r['meters'] / walk)),
                           steps_m=round(r['steps_m']), inside_complex_m=round(r['inside_m']))
            legs_all.append(leg)
        result['legs'] = [dict({k: v for k, v in l.items() if k not in ('coords', 'alt')},
                               **({'alt': {k: v for k, v in l['alt'].items() if k != 'coords'}} if l.get('alt') else {}))
                          for l in legs_all]
        main = [l for l in legs_all if not l['optional'] and 'meters' in l]
        result['route_total'] = {'meters': sum(l['meters'] for l in main), 'minutes': sum(l['minutes'] for l in main)}
        result['stops'] = []
        for st in stops_xy:
            la, lo = st['xy']
            result['stops'].append(dict({k: v for k, v in st.items() if k != 'xy'}, lat=round(la, 6), lon=round(lo, 6),
                                        kakao='https://map.kakao.com/link/map/%s,%.6f,%.6f' % (kakao_name(st['label']), la, lo),
                                        roadview='https://map.kakao.com/link/roadview/%.6f,%.6f' % (la, lo)))
        # 앱으로 열기: 구글 지도 모바일 웹은 경유지를 3개까지만 받으므로 구간을 나눈다
        coords = [st['xy'] for st in stops_xy]

        def ll(c):
            return '%.6f,%.6f' % c
        segs, i = [], 0
        while i < len(coords) - 1:
            j = min(i + 4, len(coords) - 1)
            part = coords[i:j + 1]
            url = 'https://www.google.com/maps/dir/?api=1&origin=%s&destination=%s&travelmode=walking' % (ll(part[0]), ll(part[-1]))
            if len(part) > 2:
                url += '&waypoints=' + urllib.parse.quote('|'.join(ll(c) for c in part[1:-1]), safe=',|')
            segs.append({'from_n': i + 1, 'to_n': j + 1, 'url': url})
            i = j
        result['links']['google_walk'] = segs
    for pid, p in pts.items():
        if p['kind'] == 'access':
            continue
        lat, lon = p['lat'], p['lon']
        result['links'][pid] = {
            'kakao': 'https://map.kakao.com/link/map/%s,%.6f,%.6f' % (kakao_name(p['label']), lat, lon),
            'roadview': 'https://map.kakao.com/link/roadview/%.6f,%.6f' % (lat, lon),
            'naver': 'https://map.naver.com/p/search/' + urllib.parse.quote(p.get('search') or p['label']),
        }
    # 그리기
    for m in spec['maps']:
        proj = projs[m['id']]
        m = dict(m)
        draw_route = bool(rt) and m.get('route', True)
        m['_stops'] = stops_xy if draw_route else []
        def opt_here(l):
            return l['optional'] and m.get('optional_legs', False) and (not l.get('maps') or m['id'] in l['maps'])
        legs = [l for l in legs_all if (not l['optional'] and draw_route) or opt_here(l)]
        offmap = []
        m['_suffix'] = {}
        for l in legs_all:
            if opt_here(l) and 'meters' in l and proj.inside(pts[l['to_id']]['lat'], pts[l['to_id']]['lon']):
                m['_suffix'][l['to_id']] = ' 도보 약 %d분' % l['minutes']
        for l in legs_all:
            if opt_here(l) and 'meters' in l:
                tgt = pts[l['to_id']]
                if not proj.inside(tgt['lat'], tgt['lon']):
                    offmap.append({'lat': tgt['lat'], 'lon': tgt['lon'],
                                   'label': '%s 도보 약 %d분 (%.1fkm)' % (tgt['label'], l['minutes'], l['meters'] / 1000)})
        svg = render_map(m, proj, data, pts, legs, offmap, colors, 'osm-' + m['id'])
        path = os.path.join(out_dir, m['id'] + '.svg')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(svg)
        result['maps'][m['id']] = {'file': path, 'bytes': len(svg.encode('utf-8')), 'width': proj.W, 'height': round(proj.H),
                                   'bbox': [round(x, 6) for x in proj.bbox()], 'colors': {k: v for k, v in colors.items()}}
    with open(os.path.join(out_dir, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps({'maps': result['maps'], 'route_total': result.get('route_total'),
                      'legs': [(l['from'], l['to'], l.get('meters'), l.get('minutes'), l.get('steps_m'), l.get('inside_complex_m'), l['optional']) for l in result['legs']],
                      'snap_m': [(s['label'], s['snap_m']) for s in result.get('stops', [])]}, ensure_ascii=False, indent=1))

# ── 보조 명령 ───────────────────────────────────────────────────────────────

def cmd_geocode(a):
    res = nominatim('/search', {'q': a.query, 'format': 'jsonv2', 'limit': 5, 'countrycodes': 'kr', 'accept-language': 'ko'}, DEFAULT_CACHE)
    for r in res:
        print('%s,%s\t%s/%s\t%s' % (r['lat'], r['lon'], r['osm_type'], r['osm_id'], r['display_name']))
    if not res:
        print('결과 없음')


def cmd_find(a):
    lat, lon = a.around.split(',')
    q = '[out:json][timeout:60];nwr["name"~"%s"](around:%d,%s,%s);out tags center;' % (a.regex, a.radius, lat, lon)
    for e in overpass(q, DEFAULT_CACHE)['elements']:
        c = e.get('center') or {'lat': e.get('lat'), 'lon': e.get('lon')}
        t = e['tags']
        keys = {k: t[k] for k in ('highway', 'railway', 'landuse', 'leisure', 'amenity', 'building', 'addr:housenumber') if k in t}
        print('%s/%s\t%s\t%.5f,%.5f\t%s' % (e['type'], e['id'], t.get('name'), c['lat'], c['lon'], keys))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    g = sub.add_parser('geocode')
    g.add_argument('query')
    f = sub.add_parser('find')
    f.add_argument('--around', required=True)
    f.add_argument('--radius', type=int, default=1500)
    f.add_argument('regex')
    b = sub.add_parser('build')
    b.add_argument('spec')
    a = ap.parse_args()
    {'geocode': cmd_geocode, 'find': cmd_find, 'build': lambda x: build(x.spec)}[a.cmd](a)


if __name__ == '__main__':
    main()
