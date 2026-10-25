#!/usr/bin/env python3
"""Combine public IPTV-org country playlists, validate M3U and deduplicate."""
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

def fetch(country):
    req = urllib.request.Request(BASE.format(country), headers={'User-Agent': 'TVBox-Playlist-Builder/1.0', 'Accept': 'audio/x-mpegurl,text/plain,*/*'})
    with urllib.request.urlopen(req, timeout=35) as response:
        content = response.read(20 * 1024 * 1024).decode('utf-8-sig', errors='replace')
    if not content.lstrip().startswith('#EXTM3U'):
        raise ValueError(f'{country}: response is not M3U (possible HTML/error page): {content[:80]!r}')
    return content

def entries(text):
    lines = text.splitlines()
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

def main():
    merged = ['#EXTM3U']
    seen = set()
    counts = {}
    for code, name in COUNTRIES.items():
        try:
            content = fetch(code)
        except Exception as exc:
            print(f'WARNING {name} ({code}): {exc}')
            continue
        n = 0
        for info, props, url in entries(content):
            # Keep regional variants of channels, avoid exact URL duplicates.
            if url in seen:
                continue
            seen.add(url)
            info = re.sub(r'group-title="[^"]*"', f'group-title="{name}"', info)
            if 'group-title=' not in info:
                info = info.replace('#EXTINF:', f'#EXTINF:-1 group-title="{name}" ', 1) if info.startswith('#EXTINF:-1,') else info.replace(',', f' group-title="{name}",', 1)
            merged.extend([info, *props, url])
            n += 1
        counts[name] = n
        print(f'{name}: {n} channels')
    if not counts or sum(counts.values()) == 0:
        raise RuntimeError('No valid channels; refusing to publish an empty playlist')
    OUT.write_text('\n'.join(merged) + '\n', encoding='utf-8')
    print(f'Wrote {OUT} with {sum(counts.values())} channels across {len(counts)} regions')

if __name__ == '__main__':
    main()
