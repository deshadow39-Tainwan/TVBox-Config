#!/usr/bin/env python3
"""Merge IPTV-org and compatible live playlists referenced by 20260103.json."""
import json
import re
import urllib.request
from pathlib import Path

COUNTRIES = {'tw':'台灣','hk':'香港','cn':'中國大陸','jp':'日本','kr':'韓國','us':'美國','gb':'英國','ca':'加拿大','fr':'法國','de':'德國','au':'澳洲'}
BASE = 'https://iptv-org.github.io/iptv/countries/{}.m3u'
SOURCE_CONFIG = 'https://raw.githubusercontent.com/yigedashu/xwck/refs/heads/main/20260103.json'
OUT = Path('TVBox_Global_Live.m3u')
COMMON_TERMS = {'新闻':'新聞','体育':'體育','综合':'綜合','财经':'財經','电影':'電影','电视剧':'電視劇','电视':'電視','少儿':'少兒','儿童':'兒童','音乐':'音樂','纪录':'紀錄','国际':'國際','卫视':'衛視','频道':'頻道','农业':'農業','农村':'農村','旅游':'旅遊','经济':'經濟','购物':'購物','军事':'軍事','娱乐':'娛樂','动画':'動畫','纪实':'紀實','广东':'廣東','广西':'廣西','辽宁':'遼寧','山东':'山東','陕西':'陝西','江苏':'江蘇','重庆':'重慶','内蒙古':'內蒙古','中国':'中國'}
try:
    from opencc import OpenCC
    converter = OpenCC('s2twp')
except ImportError:
    converter = None

def traditional(value):
    if converter:
        return converter.convert(value)
    for a,b in sorted(COMMON_TERMS.items(), key=lambda x:-len(x[0])):
        value=value.replace(a,b)
    return value

def download(url, ua='TVBox-Playlist-Builder/2.0'):
    req=urllib.request.Request(url,headers={'User-Agent':ua,'Accept':'text/plain,application/json,application/x-mpegURL,*/*'})
    with urllib.request.urlopen(req,timeout=25) as response:
        data=response.read(20*1024*1024+1)
    if len(data)>20*1024*1024:
        raise ValueError('Source exceeds 20 MB')
    return data.decode('utf-8-sig',errors='replace')

def m3u_entries(text):
    lines=text.splitlines()
    if not text.lstrip().startswith('#EXTM3U'):
        raise ValueError('Not M3U')
    pending=None
    for line in lines:
        s=line.strip()
        if s.startswith('#EXTINF:'):
            pending=s
        elif s.startswith(('http://','https://')) and pending:
            yield pending,s
            pending=None

def txt_entries(text):
    if re.search(r'<html|<!doctype|<script|<div\b',text[:2048],re.I):
        raise ValueError('HTML response')
    group='其他'
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith(('#','//')):
            continue
        if ',#genre#' in line:
            group=line.split(',#genre#',1)[0].strip() or '其他'
            continue
        if ',' not in line:
            continue
        name,url=line.split(',',1)
        name=name.strip()
        url=url.strip().split('$',1)[0].strip()
        if name and url.startswith(('https://','http://')):
            yield f'#EXTINF:-1 group-title="{group}",{name}',url

def parse_playlist(text):
    stripped=text.lstrip()
    if stripped.startswith('#EXTM3U'):
        return list(m3u_entries(text))
    if stripped.startswith(('{','[')):
        raise ValueError('JSON is not a direct channel playlist')
    if re.search(r'<html|<!doctype|<script|<div\b',stripped[:2048],re.I):
        raise ValueError('HTML is not a channel playlist')
    return list(txt_entries(text))

def normalize_info(info,group):
    meta,sep,name=info.partition(',')
    if not sep:
        return None
    name=traditional(name.strip())
    group=traditional(group).replace('"','')
    if re.search(r'group-title="[^"]*"',meta):
        meta=re.sub(r'group-title="[^"]*"',lambda _:f'group-title="{group}"',meta)
    else:
        meta+=f' group-title="{group}"'
    return f'{meta},{name}'

def main():
    sources=[(region,BASE.format(code),None) for code,region in COUNTRIES.items()]
    try:
        config=json.loads(download(SOURCE_CONFIG))
        for item in config.get('lives',[]):
            url=item.get('url','')
            if url.startswith(('https://','http://')):
                # Use the original declared URL, not a guessed replacement.
                sources.append(('原始-'+str(item.get('name','直播')),url,item.get('ua')))
    except Exception as exc:
        print(f'WARNING 20260103 config: {exc}')
    output=['#EXTM3U']
    seen=set()
    counts={}
    for group,url,ua in sources:
        try:
            items=parse_playlist(download(url,ua or 'TVBox-Playlist-Builder/2.0'))
            if not items:
                raise ValueError('No parseable channels')
        except Exception as exc:
            print(f'WARNING {group}: {exc}')
            continue
        added=0
        for info,stream in items:
            if stream in seen:
                continue
            norm=normalize_info(info,group)
            if norm is None:
                continue
            seen.add(stream)
            output.extend((norm,stream))
            added+=1
        counts[group]=added
        print(f'{group}: +{added} channels')
    if not seen:
        raise RuntimeError('No channels available; refusing to overwrite playlist')
    OUT.write_text('\n'.join(output)+'\n',encoding='utf-8')
    print(f'Wrote {OUT}: {len(seen)} unique channels')
    if converter is None:
        print('NOTE: OpenCC not installed; common terms only converted.')

if __name__=='__main__':
    main()
