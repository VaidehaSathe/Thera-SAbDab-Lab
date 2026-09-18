from __future__ import annotations
import json, re, urllib.parse
from datetime import date
import requests

UA='Thera-SAbDab-WHO-INN-Curator/1.0.4 (local scientific curation tool)'

def search_pubmed(term:str, timeout=15):
    params={'db':'pubmed','term':f'"{term}"','retmode':'json','retmax':'20'}
    r=requests.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi',params=params,headers={'User-Agent':UA},timeout=timeout)
    r.raise_for_status(); ids=r.json().get('esearchresult',{}).get('idlist',[])
    if not ids: return []
    s=requests.get('https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi',params={'db':'pubmed','id':','.join(ids),'retmode':'json'},headers={'User-Agent':UA},timeout=timeout)
    s.raise_for_status(); data=s.json().get('result',{})
    out=[]
    for pmid in ids:
        x=data.get(pmid,{})
        out.append({'source':'PubMed','id':pmid,'title':x.get('title',''),'url':f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/','status':'candidate-unverified'})
    return out

def search_clinicaltrials(term:str, timeout=15):
    params={'query.term':f'"{term}"','pageSize':50,'format':'json'}
    r=requests.get('https://clinicaltrials.gov/api/v2/studies',params=params,headers={'User-Agent':UA},timeout=timeout)
    r.raise_for_status(); out=[]
    for st in r.json().get('studies',[]):
        ps=st.get('protocolSection',{}); ident=ps.get('identificationModule',{})
        nct=ident.get('nctId',''); title=ident.get('briefTitle','')
        if nct: out.append({'source':'ClinicalTrials.gov','id':nct,'title':title,'url':f'https://clinicaltrials.gov/study/{nct}','status':'candidate-unverified'})
    return out

def public_search_links(term:str):
    q=urllib.parse.quote_plus(f'"{term}"')
    return {
        'PubMed':f'https://pubmed.ncbi.nlm.nih.gov/?term={q}',
        'ClinicalTrials.gov':f'https://clinicaltrials.gov/search?term={q}',
        'Google Patents':f'https://patents.google.com/?q={q}',
    }

def validate_url(url:str, timeout=12):
    if not re.match(r'^https?://',url or '',re.I): return {'status':'unresolved','final_url':'','detail':'not an HTTP(S) URL'}
    try:
        r=requests.head(url,allow_redirects=True,timeout=timeout,headers={'User-Agent':UA})
        if r.status_code in (403,405) or r.status_code>=500:
            r=requests.get(url,allow_redirects=True,timeout=timeout,headers={'User-Agent':UA},stream=True)
        if 200<=r.status_code<300:
            status='redirected-valid' if r.url.rstrip('/')!=url.rstrip('/') else 'valid'
        elif r.status_code in (401,403,429): status='blocked/inaccessible'
        elif r.status_code==404: status='broken/replaced'
        else: status='unresolved'
        return {'status':status,'final_url':r.url,'detail':f'HTTP {r.status_code}'}
    except requests.RequestException as e:
        return {'status':'unresolved','final_url':'','detail':str(e)}
