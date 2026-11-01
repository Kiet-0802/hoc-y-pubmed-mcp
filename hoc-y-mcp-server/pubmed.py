"""Bounded, read-only PubMed retrieval. No patient data or arbitrary URLs."""
from __future__ import annotations
import asyncio
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import httpx

NCBI = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils'
PUBMED = 'https://pubmed.ncbi.nlm.nih.gov/'
STUDY_TYPES = {
    'any': '',
    'systematic_review': 'systematic review[pt]',
    'guideline': 'guideline[pt]',
    'randomized_trial': 'randomized controlled trial[pt]',
    'observational': '(cohort studies[mesh] OR case-control studies[mesh])',
}
_lock = asyncio.Lock()
_next_request = 0.0


def _node_text(node: ET.Element | None) -> str:
    return ' '.join(''.join(node.itertext()).split()) if node is not None else ''


def _first(root: ET.Element, path: str) -> str:
    return _node_text(root.find(path))


def _parse_article(article: ET.Element, include_abstract: bool = False) -> dict[str, Any]:
    pmid = _first(article, './/MedlineCitation/PMID')
    title = _first(article, './/Article/ArticleTitle')
    journal = _first(article, './/Article/Journal/Title')
    pubdate = article.find('.//Article/Journal/JournalIssue/PubDate')
    date = _node_text(pubdate)
    doi = ''
    for item in article.findall('.//ArticleId'):
        if item.attrib.get('IdType') == 'doi':
            doi = _node_text(item)
            break
    types = [_node_text(t) for t in article.findall('.//PublicationTypeList/PublicationType')]
    data = {
        'pmid': pmid, 'title': title[:500], 'journal': journal[:300],
        'publication_date_as_reported': date[:100],
        'doi': doi[:200], 'publication_types': types[:15],
        'url': f'{PUBMED}{pmid}/' if pmid else '',
        'is_retraction_or_correction_related': any('retract' in x.lower() or 'correct' in x.lower() for x in types),
        'abstract_available': article.find('.//Article/Abstract') is not None,
    }
    if include_abstract:
        parts = []
        for element in article.findall('.//Article/Abstract/AbstractText'):
            label = element.attrib.get('Label', '')
            content = _node_text(element)
            if content:
                parts.append((label + ': ' if label else '') + content)
        data['abstract'] = '\n'.join(parts)[:16000]
        data['abstract_is_full_text'] = False
        data['note'] = 'PubMed abstract and metadata only; no study appraisal, GRADE, guideline-currentness, or full-text verification.'
    return data


def _parse_pubmed_xml(xml: bytes, include_abstract: bool = False) -> list[dict[str, Any]]:
    if len(xml) > 2_000_000: raise ValueError('NCBI response exceeded size limit')
    root = ET.fromstring(xml)
    return [_parse_article(a, include_abstract) for a in root.findall('./PubmedArticle')]


def _check_query(query: str, max_results: int, study_type: str, since_year: int | None):
    if not isinstance(query, str) or not 3 <= len(query.strip()) <= 240:
        raise ValueError('query must be 3..240 characters')
    if any(ord(c) < 32 for c in query): raise ValueError('control characters are not allowed')
    if not isinstance(max_results, int) or not 1 <= max_results <= 8:
        raise ValueError('max_results must be between 1 and 8')
    if study_type not in STUDY_TYPES:
        raise ValueError(f'study_type must be one of {list(STUDY_TYPES)}')
    if since_year is not None and (not isinstance(since_year, int) or not 1980 <= since_year <= datetime.now(timezone.utc).year):
        raise ValueError('since_year is outside the supported range')


async def _ncbi_get(path: str, params: dict[str, str | int]) -> bytes:
    global _next_request
    if path not in ('esearch.fcgi','efetch.fcgi'):
        raise ValueError('unsupported NCBI operation')
    args = dict(params)
    args['tool'] = 'HocYMedicalEducation'
    contact = os.getenv('NCBI_CONTACT_EMAIL', '')
    if contact: args['email'] = contact
    key = os.getenv('NCBI_API_KEY', '')
    if key: args['api_key'] = key
    # Single process pacing: one NCBI request per 0.5s, below the unauthenticated 3/s limit.
    async with _lock:
        delta = _next_request - time.monotonic()
        if delta > 0: await asyncio.sleep(delta)
        _next_request = time.monotonic() + 0.5
        async with httpx.AsyncClient(timeout=httpx.Timeout(12.0), follow_redirects=False) as client:
            response = await client.get(f'{NCBI}/{path}', params=args)
            response.raise_for_status()
            if len(response.content) > 2_000_000: raise ValueError('response too large')
            return response.content


async def search_medical_literature(query: str, study_type: str = 'any', since_year: int | None = None, max_results: int = 5) -> dict[str, Any]:
    _check_query(query, max_results, study_type, since_year)
    term = query.strip()
    if STUDY_TYPES[study_type]: term += ' AND ' + STUDY_TYPES[study_type]
    if since_year: term += f' AND {since_year}:3000[dp]'
    xml = await _ncbi_get('esearch.fcgi', {'db':'pubmed','term':term, 'retmode':'xml','retmax':max_results,'sort':'pub date'})
    root=ET.fromstring(xml)
    ids=[e.text.strip() for e in root.findall('.//IdList/Id') if e.text and re.fullmatch(r'\d{1,12}',e.text.strip())]
    total = _first(root,'./Count')
    if not ids:
        return {'query':query,'study_type':study_type,'reported_count':int(total or 0),'articles':[], 'note':'No results for this search; this does not prove evidence is absent.'}
    articles = _parse_pubmed_xml(await _ncbi_get('efetch.fcgi', {'db':'pubmed','id':','.join(ids),'retmode':'xml'}))
    return {'query':query,'study_type':study_type,'reported_count':int(total or 0), 'articles':articles, 'note':'Metadata-based search, sorted by publication date, not by study validity or certainty. Check primary guidelines and full texts for clinical recommendations.'}


async def fetch_medical_article(pmid: str) -> dict[str, Any]:
    if not isinstance(pmid, str) or not re.fullmatch(r'\d{1,12}',pmid):
        raise ValueError('PMID must contain 1 to 12 digits only')
    articles = _parse_pubmed_xml(await _ncbi_get('efetch.fcgi', {'db':'pubmed','id':pmid,'retmode':'xml'}), include_abstract=True)
    if not articles:
        return {'pmid':pmid,'status':'not_found','note':'PubMed record not available.'}
    return {'status':'ok',**articles[0]}
