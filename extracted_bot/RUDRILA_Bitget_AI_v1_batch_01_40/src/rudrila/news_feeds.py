from __future__ import annotations
import calendar, email.utils, html, re, time, urllib.request, xml.etree.ElementTree as ET
from .news_macro import NewsItem

DEFAULT_FEEDS={
  'Federal Reserve':'https://www.federalreserve.gov/feeds/press_all.xml',
  'SEC':'https://www.sec.gov/news/pressreleases.rss',
  'Cointelegraph':'https://cointelegraph.com/rss',
  'CoinDesk':'https://www.coindesk.com/arc/outboundfeeds/rss/'
}
SOURCE_CLASSES={'Federal Reserve':'central_bank','SEC':'regulator','Cointelegraph':'crypto_media','CoinDesk':'crypto_media'}

TAG_RE=re.compile(r'<[^>]+>')
def _txt(x): return html.unescape(TAG_RE.sub(' ',x or '')).strip()
def _parse_time(s):
    if not s: return int(time.time()*1000)
    try: return int(calendar.timegm(email.utils.parsedate(s))*1000)
    except Exception: return int(time.time()*1000)

def fetch_rss(url:str,source:str,timeout=8,max_items=30)->list[NewsItem]:
    req=urllib.request.Request(url,headers={'User-Agent':'RUDRILA-Bitget-AI/1.1 (+news-scoring)'})
    with urllib.request.urlopen(req,timeout=timeout) as r: raw=r.read()
    root=ET.fromstring(raw)
    out=[]
    for item in root.findall('.//item')[:max_items]:
        title=_txt(item.findtext('title')); body=_txt(item.findtext('description'))
        link=_txt(item.findtext('link')); pub=item.findtext('pubDate') or item.findtext('date')
        out.append(NewsItem(title,source,_parse_time(pub),body,link))
    if not out:
        ns={'a':'http://www.w3.org/2005/Atom'}
        for e in root.findall('.//a:entry',ns)[:max_items]:
            title=_txt(e.findtext('a:title','',ns)); body=_txt(e.findtext('a:summary','',ns))
            link=''; le=e.find('a:link',ns)
            if le is not None: link=le.attrib.get('href','')
            pub=e.findtext('a:updated','',ns) or e.findtext('a:published','',ns)
            out.append(NewsItem(title,source,_parse_time(pub),body,link))
    return out

class LiveNewsCollector:
    def __init__(self,feeds=None): self.feeds=feeds or dict(DEFAULT_FEEDS); self.errors={}
    def fetch(self):
        items=[]; self.errors={}
        for source,url in self.feeds.items():
            try: items.extend(fetch_rss(url,source))
            except Exception as e: self.errors[source]=str(e)
        return items
