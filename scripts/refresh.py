#!/usr/bin/env python3
"""Small public-feed importer: no paid APIs, no user data, no fuzzy licence claims.
Usage: python scripts/refresh.py [--offline]
Runs from repository root. Writes only small JSON indexes, not Home Office's full CSV.
"""
from __future__ import annotations
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import urljoin, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
GOV = 'https://www.gov.uk/government/publications/register-of-licensed-sponsors-workers'
UA = 'UK-Sponsorship-Evidence/0.2 (non-commercial project; small public-source index)'
TODAY = datetime.now(timezone.utc)
STAMP = TODAY.strftime('%Y-%m-%dT%H:%M:%SZ')
FRESH = TODAY.strftime('%Y-%m-%d')
SCOPE = re.compile(r'\b(uk|united kingdom|london|manchester|birmingham|bristol|glasgow|edinburgh|leeds|cambridge|oxford|cardiff|liverpool|remote uk|england|scotland|wales)\b', re.I)
KEYWORDS = re.compile(r'\b(account executive|sales|business development|relationship manager|account manager|client manager|broker|insurance|underwriter|consultant|commercial|partnership|financial|banking)\b', re.I)
SPONSOR = re.compile(r'\b(visa\s+sponsorship|sponsor(?:ship|ing)?\s+(?:a\s+)?(?:skilled worker|visa|applicant|candidate)|certificate of sponsorship)\b', re.I)
NEGATIVE = re.compile(r'(visa\s+sponsorship\s+(?:is\s+)?(?:not available|unavailable|not offered)|(?:do not|does not|don.t|doesn.t|cannot|can.t|will not|won.t|unable to|no)\s+(?:provide|offer|support|consider)?\s*(?:visa\s+)?sponsorship|no\s+(?:visa\s+)?sponsorship|not\s+able\s+to\s+sponsor)', re.I)
CASE = re.compile(r'(case.by.case|individual(?:ly)?\s+(?:circumstance|basis)|discuss\s+(?:this|sponsorship).*?(?:recruit|hiring|interview)|sponsorship.*?(?:dependent on|considered|consider|subject to|assess each))', re.I | re.S)
YES = re.compile(r'(visa\s+sponsorship\s*:\s*(?:yes|available)|visa\s+sponsorship\s+(?:is\s+)?available|(?:we|company)\s+(?:(?:are\s+)?able\s+to\s+|can\s+|do\s+)?(?:offer|provide|support)\s+visa\s+sponsorship|(?:we\s+)?(?:are\s+)?(?:in\s+a\s+position\s+to\s+|able\s+to\s+)?offer\s+(?:visa\s+)?sponsorship(?:\s+and/or\s+a\s+visa)?|sponsorship\s+available)', re.I)

def read(path):
    return json.loads((DATA/path).read_text(encoding='utf-8'))

def write(path, payload):
    out = DATA/path
    content = json.dumps(payload,ensure_ascii=False,indent=2) + '\n'
    if not out.exists() or out.read_text(encoding='utf-8') != content:
        out.write_text(content,encoding='utf-8')

def get(url,max_bytes=3_000_000):
    if not url.startswith('https://'):
        raise ValueError('Only HTTPS source URLs permitted')
    req = Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/html,text/csv,*/*'})
    with urlopen(req,timeout=22) as response:
        body=response.read(max_bytes+1)
    if len(body)>max_bytes: raise ValueError('Source exceeded size cap')
    return body

class Links(HTMLParser):
    def __init__(self): super().__init__();self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            if href and ('.csv' in href.lower() or 'attachment' in href.lower()): self.links.append(href)

def register_csv_urls(page_html):
    """Accept the raw government attachment, never its HTML preview (.csv/preview)."""
    p = Links()
    p.feed(page_html)
    urls = []
    for href in p.links:
        url = urljoin(GOV, unescape(href))
        parsed = urlparse(url)
        if parsed.scheme != 'https':
            continue
        if parsed.hostname not in ('assets.publishing.service.gov.uk', 'www.gov.uk', 'publishing.service.gov.uk'):
            continue
        if not parsed.path.lower().endswith('.csv'):
            continue
        if url not in urls:
            urls.append(url)
    return urls


def official_register():
    """Fetch and sanity-check the current raw Home Office CSV attachment."""
    html = get(GOV, 2_000_000).decode('utf-8', 'replace')
    urls = register_csv_urls(html)
    if not urls:
        raise ValueError('No raw government CSV attachment found')
    failures = []
    for url in reversed(urls):
        try:
            data = get(url, 25_000_000)
            first = data[:1000].lower().lstrip()
            if b'<html' in first or b'<!doctype' in first:
                raise ValueError('Government attachment returned HTML, not CSV')
            rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig', 'replace'))))
            if not 20000 <= len(rows) <= 500000:
                raise ValueError('Register has unexpected row count: ' + str(len(rows)))
            if not rows or not any('organisation' in (k or '').lower() for k in rows[0]):
                raise ValueError('Unexpected government CSV headers')
            by_name = {}
            def getcol(row, part):
                return next((v or '' for k, v in row.items() if k and part in k.lower()), '')
            for row in rows:
                name = getcol(row, 'organisation').strip()
                if not name:
                    continue
                by_name.setdefault(name.casefold(), []).append({
                    'name': name, 'town': getcol(row, 'town').strip(),
                    'route': getcol(row, 'route').strip(),
                    'rating': (getcol(row, 'type & rating') or getcol(row, 'rating')).strip()
                })
            return by_name, url, len(rows)
        except (ValueError, HTTPError, URLError, TimeoutError) as exc:
            failures.append(str(exc)[:160])
    raise ValueError('None of the government CSV attachments passed validation: ' + '; '.join(failures))


def history_for(name):
    """Read independently verified FOI figures, never compute a false zero."""
    path=DATA/'history.csv'
    if not name or not path.exists(): return None
    with path.open(newline='',encoding='utf-8-sig') as f:
        arr=[r for r in csv.DictReader(f) if r.get('employer_legal_name','').strip().casefold()==name.casefold()]
    verified=[]
    for a in arr:
        if not a.get('source_url','').startswith('https://') or not a.get('checked_on') or not a.get('value'): continue
        verified.append({'value':a['value'],'period':a['period'],'metric':a['metric'],'route':a['route'],'source_url':a['source_url'],'checked_on':a['checked_on']})
    return sorted(verified,key=lambda x:x['period'],reverse=True)[:12] or None

def sponsor_match(sources,register,source_url):
    """Only confirm Skilled Worker licences for curated, unambiguous legal entities."""
    output={}
    for source in sources:
        brand=source['company'].strip()
        legal=source.get('legal_name','').strip()
        register_name=source.get('register_name',legal or brand).strip()
        expected_town=source.get('register_town','').strip()
        possible=register.get(register_name.casefold(),[])
        if expected_town:
            possible=[r for r in possible if r['town'].casefold()==expected_town.casefold()]
        groups={(r['name'].casefold(),r['town'].casefold()) for r in possible}
        if len(groups)!=1 or not possible:
            continue
        skilled=[r for r in possible if 'skilled worker' in r['route'].lower()]
        hit=(skilled or possible)[0]
        exact_legal=bool(legal) and legal.casefold()==register_name.casefold()
        linked_entity=(bool(legal) and bool(source.get('company_number'))
                       and source.get('entity_match_url','').startswith('https://'))
        verified=bool(skilled) and (exact_legal or linked_entity)
        status='verified' if verified else 'name_only'
        record={
            'status':status,'legal_name':legal or hit['name'],
            'register_name':hit['name'],'town':hit['town'],
            'route':hit['route'],'rating':hit['rating'],'checked_on':FRESH,
            'register_source':source_url,
            'company_number':source.get('company_number',''),
            'entity_match_url':source.get('entity_match_url',''),
            'history':history_for(hit['name']) if verified else None,
            'match_basis':('Exact curated legal entity and Skilled Worker route'
                           if exact_legal and verified
                           else 'Curated employer-to-register identity cross-reference and Skilled Worker route'
                           if verified else 'Register name found; legal entity or Skilled Worker route not established')
        }
        output[legal or brand]=record
        if legal and brand.casefold()!=legal.casefold():
            output[brand]=record
    return output

def as_text(s):
    # Greenhouse location fields are objects; Ashby fields are usually strings.
    if isinstance(s, dict):
        s = s.get('name') or s.get('location') or ''
    if not isinstance(s, str):
        return ''
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', ' ', s))).strip()

def classify(text):
    # Intentional conservative rules: avoid claiming that general company support applies here.
    if NEGATIVE.search(text): return 'exclude', 'Advert includes wording against sponsorship'
    if SPONSOR.search(text) and (CASE.search(text) or re.search(r'(?:right\s+candidate|not\s+(?:able|possible)\s+to\s+.{0,30}sponsor\s+.{0,50}every\s+(?:role|candidate))',text,re.I)):
        p=CASE.search(text) or SPONSOR.search(text)
        return 'conditional',text[max(0,p.start()-65):p.end()+110][:260]
    p=YES.search(text)
    if p: return 'stated',text[max(0,p.start()-40):p.end()+75][:210]
    return 'unknown','No unambiguous sponsorship promise found in the advert'

def listing(source,item):
    text=as_text(item.get('descriptionPlain') or item.get('descriptionHtml') or item.get('content') or '')
    title=as_text(item.get('title',''))
    loc=as_text(item.get('location',''))
    addr = item.get('address') or {}
    if not isinstance(addr, dict): addr = {}
    postal = addr.get('postalAddress') or {}
    if not isinstance(postal, dict): postal = {}
    country = postal.get('addressCountry', '')
    if not (SCOPE.search(loc) or str(country).lower() in ('gb','gbr','uk','united kingdom')): return None
    if not KEYWORDS.search(title): return None
    if len(text)>110000: text=text[:110000]
    status,evidence=classify(text)
    if status=='exclude': return None
    url=item.get('jobUrl') or item.get('absolute_url') or ''
    apply_url=item.get('applyUrl') or url
    if not safe_https(url) or not safe_https(apply_url):return None
    from urllib.parse import urlparse
    allowed=('jobs.ashbyhq.com','job-boards.greenhouse.io','job-boards.eu.greenhouse.io','boards.greenhouse.io')
    if urlparse(url).hostname not in allowed or urlparse(apply_url).hostname not in allowed: return None
    # A public employer feed alone is not proof of an actively sponsorable vacancy.
    if status=='unknown': status='unknown' # not called confirmed, even if the employer has a licence
    role_id=hashlib.sha256(url.encode()).hexdigest()[:16]
    salary='Not disclosed'
    compensation=item.get('compensation') or {}
    if isinstance(compensation,dict):
        salary=as_text(compensation.get('scrapeableCompensationSalarySummary') or '') or salary
    sector=source.get('sector','Sales / commercial')
    return {'id':'feed-'+role_id,'company':source['company'],'legal_name':source.get('legal_name',''),
        'title':title,'location':loc or 'UK (see advert)','category':sector,
        'salary':salary,'sponsorship':status,'evidence':evidence,'evidence_source':'Automated text extraction from employer feed',
        'evidence_url':url,'apply_url':apply_url,'verified_on':FRESH,'posted_at':(item.get('publishedAt') or '')[:10],
        'last_seen':FRESH,'active':True,'review':'auto','summary':source.get('sector','Commercial')+' — check employer advert for role-specific sponsorship and eligibility.'}

def safe_https(x):return isinstance(x,str) and x.startswith('https://')

def get_source_jobs(src):
    if src['provider']=='ashby':
        u='https://api.ashbyhq.com/posting-api/job-board/'+src['board']+'?includeCompensation=true'
        response=json.loads(get(u,12_000_000))
        return [x for x in response.get('jobs',[]) if x.get('isListed') is not False]
    if src['provider']=='greenhouse':
        u='https://boards-api.greenhouse.io/v1/boards/'+src['board']+'/jobs?content=true'
        response=json.loads(get(u,12_000_000))
        return response.get('jobs',[])
    raise ValueError('Unsupported public feed provider')

def main():
    offline='--offline' in sys.argv
    payload=read('jobs.json'); sources=[s for s in read('sources.json') if s.get('enabled')]
    past=payload.get('jobs',[])
    by_url={j['apply_url']:j for j in past}
    good=0;bad=[];seen=set()
    if not offline:
        for src in sources[:15]:
            try:
                records=get_source_jobs(src)
                good+=1
                urls=set()
                for i in records[:150]:
                    job=listing(src,i)
                    if job is None:continue
                    u=job['apply_url'];urls.add(u);seen.add(u)
                    old=by_url.get(u)
                    if old and old.get('review')=='manual':
                        old['active']=True;old['last_seen']=FRESH
                    elif old and old.get('sponsorship') in ('stated','conditional') and job['sponsorship']=='unknown':
                        job['sponsorship']='unknown' # Do not silently preserve outdated evidence.
                        by_url[u]=job
                    else: by_url[u]=job
                # Remove only when a successful full feed no longer contains the URL.
                for j in by_url.values():
                    if j.get('company')==src['company'] and j.get('apply_url','').startswith(('https://jobs.ashbyhq.com/'+src['board']+'/', 'https://job-boards.greenhouse.io/'+src['board']+'/', 'https://job-boards.eu.greenhouse.io/'+src['board']+'/')) and j.get('apply_url') not in {a.get('applyUrl') or a.get('jobUrl') or a.get('absolute_url') for a in records}:
                        j['active']=False
            except (ValueError,KeyError,TimeoutError,URLError,HTTPError) as e:
                bad.append(src['company']+': '+str(e)[:120])
        if good==0:
            print('No feeds succeeded; preserving last successful public data. Errors: '+'; '.join(bad),file=sys.stderr)
            # Sponsor register still needs its daily refresh even when job APIs fail.
            latest=None
        else:
            latest=list(by_url.values())
        # Small public index, not a scraped bulk job warehouse.
        if latest is not None:
            latest.sort(key=lambda j:(j.get('last_seen',''),j.get('posted_at','')),reverse=True)
            latest=latest[:300]
            payload={'updated_at':FRESH,'mode':'automated','jobs':latest}
            write('jobs.json',payload)
    else: print('Offline validation: {} job cards, {} configured sources'.format(len(past),len(sources)))
    sponsors=read('sponsors.json')
    last=sponsors.get('updated_at') or '1970-01-01'
    # A curated identity change should trigger an immediate recheck even on the same day.
    source_hash=hashlib.sha256(json.dumps(sources,sort_keys=True).encode('utf-8')).hexdigest()
    if not offline and (FRESH > last[:10] or sponsors.get('source_config_hash') != source_hash):
        try:
            register,reg_url,total=official_register()
            companies=sponsor_match(sources,register,reg_url)
            for key,record in companies.items():
                prior=sponsors.get('companies',{}).get(key,{})
                if prior.get('first_observed_on') and prior.get('status')==record.get('status'):
                    record['first_observed_on']=prior['first_observed_on']
                else:
                    record['first_observed_on']=FRESH
            write('sponsors.json',{'updated_at':STAMP,'official_register_url':GOV,
                'source_csv':reg_url,'rows_read':total,'source_config_hash':source_hash,'note':'Official register checked daily. Exact brand matches still need legal-entity verification. First observed here is not a licence start date. Missing CoS history is unknown, never zero.',
                'companies':companies})
        except Exception as e:
            print('Sponsor refresh failed; preserving prior sponsor data: '+str(e),file=sys.stderr)
    if bad:print('Partial feed failures: '+'; '.join(bad),file=sys.stderr)
    # A failed source must not clear previously checked public records.
    return 0 if offline or good>0 else 1

if __name__=='__main__':sys.exit(main())
