#!/usr/bin/env python3
"""Merge IPTV-org and optional external TVBox live sources into one M3U. External sources are untrusted: accept only recognizable M3U/TXT playlists. """
import re
import urllib.request
from pathlib import Path

COUNTRIES = {
    'tw': '台灣', 'hk': '香港', 'cn': '中國大陸', 'jp': '日本',
    'kr': '韓國', 'us': '美國', 'gb': '英國', 'ca': '加拿大',
    'fr': '法國', 'de': '德國', 'au': '澳洲',
}
BASE = 'https://iptv-org.github.io/iptv/countries/{}.m3u'
OUT = Path('TVBox_Global_Live.m3u')

# From yigedashu/xwck/main/lrzy/api.json (lives section).
# A few hosts may require credentials, custom headers or regional access.
EXTRA_SOURCES = [
    ('褲佬', 'https://gh-proxy.org/https://raw.githubusercontent.com/Jsnzkpg/Jsnzkpg/refs/heads/Jsnzkpg/Jsnzkpg1', None),
    ('Kimentanm', 'https://raw.githubusercontent.com/Kimentanm/aptv/master/m3u/iptv.m3u', None),
    ('綜合直播', 'https://ds65.tv1288.xyz', 'bingcha/1.1 (mianfeifenxiang) '),
    ('日后', 'http://rihou.cc:555/gggg.nzk', 'okhttp/3'),
    ('宮殿', 'https://gongdian.top/tv/iptv', None),
    ('develop202', 'https://raw.githubusercontent.com/develop202/migu_video/refs/heads/main/interface.txt', None),
    ('EPG直播', 'https://raw.githubusercontent.com/Wirili/IPTV/main/live.txt', None),
    ('電視直播', 'https://raw.githubusercontent.com/Supprise0901/TVBox_live/main/live.txt', None),
    ('酒店源', 'https://gongdian.top/tv/guovin', None),
    ('游魂', 'https://www.iyouhun.com/tv/zb', None),
    ('YanG', 'https://raw.githubusercontent.com/YanG-1989/m3u/main/Gather.m3u', None),
    ('suxuang', 'https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u', None),
]
COMMON_TERMS = {
    '新闻': '新聞', '体育': '體育', '综合': '綜合', '财经': '財經',
    '电影': '電影', '电视剧': '電視劇', '电视': '電視',
    '少儿': '少兒', '儿童': '兒童', '音乐': '音樂', '纪录': '紀錄',
    '国际': '國際', '卫视': '衛視', '频道': '頻道',
    '农业': '農業', '农村': '農村', '旅游': '旅遊',
    '经济': '經濟', '购物': '購物', '军事': '軍事',
    '娱乐': '娛樂', '动画': '動畫', '纪实': '紀實',
    '戏曲': '戲曲', '广东': '廣東', '广西': '廣西',
    '辽宁': '遼寧', '山东': '山東', '陕西': '陝西',
    '江苏': '江蘇', '重庆': '重慶', '宁夏': '寧夏',
    '内蒙古': '內蒙古', '中国': '中國',
}
try:
    from opencc import OpenCC
    converter = OpenCC('s2twp')
except ImportError:
    converter = None


def traditional(value):
    if converter:
        return converter.convert(value)
    for old, new in sorted(COMMON_TERMS.items(), key=lambda pair: -len(pair[0])):
        value = value.replace(old, new)
    return value


def fetch(url, ua=None):
    req = urllib.request.Request(url, headers={
        'User-Agent': ua or 'Mozilla/5.0 TVBox-Playlist-Builder/2.0',
        'Accept': 'audio/x-mpegurl,text/plain,*/*',
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        data = response.read(15 * 1024 * 1024 + 1)
    if len(data) > 15 * 1024 * 1024:
        raise ValueError('source exceeds 15 MiB limit')
    return data.decode('utf-8-sig', errors='replace')


def valid_url(value):
    return value.startswith(('https://', 'http://')) and not any(c.isspace() for c in value)


def parse_m3u(content, region):
    lines = content.splitlines()
    if not content.lstrip().startswith('#EXTM3U'):
        raise ValueError('not M3U')
    result = []
    for idx, line in enumerate(lines):
        if not line.startswith('#EXTINF:'):
            continue
        metadata, sep, name = line.partition(',')
        if not sep:
            continue
        metadata = re.sub(r'group-title="[^"]*"', '', metadata).rstrip()
        metadata += f' group-title="{region}"'
        extras = []
        url = None
        for nxt in lines[idx + 1:]:
            nxt = nxt.strip()
            if nxt.startswith('#EXTINF:'):
                break
            if nxt.startswith('#'):
                # Preserve player headers/options that might be needed.
                extras.append(nxt)
            elif nxt:
                url = nxt
                break
        if url and valid_url(url):
            result.append((f'{metadata},{traditional(name.strip())}', extras, url))
    return result


def parse_txt(content, region):
    # TVBox TXT: group,#genre# followed by channel,url lines.
    if content.lstrip().startswith(('<', '{', '[')):
        raise ValueError('HTML/JSON is not a TVBox TXT playlist')
    result = []
    group = region
    group_marks = 0
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith(('#', '//')):
            continue
        if line.endswith(',#genre#'):
            group_marks += 1
            group = traditional(line[:-8].strip()) or region
            continue
        if ',' not in line:
            continue
        name, url = line.split(',', 1)
        name, url = name.strip(), url.strip()
        if name and valid_url(url):
            # Keep the source and its category identifiable in the global list.
            title = f'{region}｜{group}' if group != region else region
            result.append((f'#EXTINF:-1 group-title="{title}",{traditional(name)}', [], url))
    if not group_marks:
        raise ValueError('not recognizable TVBox TXT (no #genre# groups)')
    return result


def parse(content, region):
    if content.lstrip().startswith('#EXTM3U'):
        return parse_m3u(content, region)
    return parse_txt(content, region)


def main():
    output = ['#EXTM3U']
    seen = set()
    total = 0
    successful_countries = 0
    successful_extra = 0

    def add(items):
        nonlocal total
        count = 0
        for info, options, url in items:
            if url in seen:
                continue
            seen.add(url)
            output.extend([info, *options, url])
            count += 1
        total += count
        return count

    for code, region in COUNTRIES.items():
        try:
            items = parse_m3u(fetch(BASE.format(code)), region)
            count = add(items)
            successful_countries += 1
            print(f'IPTV-org {region}: +{count}')
        except Exception as exc:
            print(f'WARNING IPTV-org {region}: {exc}')

    # The optional sources must not break an otherwise healthy playlist.
    for name, url, ua in EXTRA_SOURCES:
        try:
            items = parse(fetch(url, ua), name)
            if not items:
                raise ValueError('no valid channel entries')
            count = add(items)
            successful_extra += 1
            print(f'External {name}: +{count}')
        except Exception as exc:
            print(f'WARNING external {name}: {exc}')

    if not successful_countries:
        raise RuntimeError('All original IPTV-org sources failed; preserving previous playlist')
    if total == 0:
        raise RuntimeError('No valid channels; preserving previous playlist')
    OUT.write_text('\n'.join(output) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}: {total} unique streams, {successful_extra}/{len(EXTRA_SOURCES)} extra sources parsed')
    if converter is None:
        print('NOTE: OpenCC not installed; common terms only were converted.')


if __name__ == '__main__':
    main()
