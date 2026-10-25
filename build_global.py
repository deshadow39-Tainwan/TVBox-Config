#!/usr/bin/env python3
"""Merge public IPTV-org M3U playlists and normalize common Chinese channel names."""
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

# Common channel-name terms only. For comprehensive Simplified-to-Traditional
# conversion, install OpenCC and enable the optional converter below.
COMMON_TERMS = {
    '新闻': '新聞', '体育': '體育', '综合': '綜合', '财经': '財經',
    '电影': '電影', '电视剧': '電視劇', '电视': '電視',
    '少儿': '少兒', '儿童': '兒童', '音乐': '音樂', '纪录': '紀錄',
    '国际': '國際', '卫视': '衛視', '频道': '頻道',
    '高清': '高清', '农业': '農業', '农村': '農村',
    '文化': '文化', '教育': '教育', '旅游': '旅遊',
    '经济': '經濟', '生活': '生活', '购物': '購物',
    '军事': '軍事', '娱乐': '娛樂', '动画': '動畫',
    '纪实': '紀實', '戏曲': '戲曲', '广东': '廣東',
    '广西': '廣西', '福建': '福建', '辽宁': '遼寧',
    '山东': '山東', '陕西': '陝西', '江苏': '江蘇',
    '浙江': '浙江', '湖北': '湖北', '湖南': '湖南',
    '重庆': '重慶', '宁夏': '寧夏', '新疆': '新疆',
    '内蒙古': '內蒙古', '中央': '中央', '中国': '中國',
}

try:
    from opencc import OpenCC
    _opencc = OpenCC('s2twp')
except ImportError:
    _opencc = None


def traditional(text):
    if _opencc is not None:
        return _opencc.convert(text)
    for src, dst in sorted(COMMON_TERMS.items(), key=lambda x: len(x[0]), reverse=True):
        text = text.replace(src, dst)
    return text


def fetch(country):
    req = urllib.request.Request(
        BASE.format(country),
        headers={
            'User-Agent': 'TVBox-Playlist-Builder/1.1',
            'Accept': 'audio/x-mpegurl,text/plain,*/*',
        },
    )
    with urllib.request.urlopen(req, timeout=35) as response:
        content = response.read(20 * 1024 * 1024).decode('utf-8-sig', errors='replace')
    if not content.lstrip().startswith('#EXTM3U'):
        raise ValueError(f'{country}: not M3U (HTML/error page?): {content[:80]!r}')
    return content


def entries(content):
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith('#EXTINF:'):
            continue
        props = []
        url = None
        for next_line in lines[i + 1:]:
            s = next_line.strip()
            if s.startswith('#EXTINF:'):
                break
            if s.startswith('#'):
                props.append(s)
            elif s:
                url = s
                break
        if url and url.startswith(('http://', 'https://')):
            yield line, props, url


def normalize_info(info, region):
    # EXTINF separates metadata and display name at its first comma.
    # Never translate IDs, logos, URLs or other attributes.
    metadata, separator, display_name = info.partition(',')
    if not separator:
        return info
    display_name = traditional(display_name.strip())
    if re.search(r'group-title="[^"]*"', metadata):
        metadata = re.sub(r'group-title="[^"]*"', f'group-title="{region}"', metadata)
    else:
        metadata += f' group-title="{region}"'
    return f'{metadata},{display_name}'


def main():
    merged = ['#EXTM3U']
    seen = set()
    counts = {}
    for code, region in COUNTRIES.items():
        try:
            content = fetch(code)
        except Exception as exc:
            print(f'WARNING {region} ({code}): {exc}')
            continue
        count = 0
        for info, props, url in entries(content):
            if url in seen:
                continue
            seen.add(url)
            merged.extend([normalize_info(info, region), *props, url])
            count += 1
        counts[region] = count
        print(f'{region}: {count} channels')
    if not counts or sum(counts.values()) == 0:
        raise RuntimeError('No valid channels; refusing to publish an empty playlist')
    OUT.write_text('\n'.join(merged) + '\n', encoding='utf-8')
    print(f'Wrote {OUT}: {sum(counts.values())} channels, {len(counts)} regions')
    if _opencc is None:
        print('NOTE: OpenCC not installed; only common channel-name terms were converted.')


if __name__ == '__main__':
    main()
