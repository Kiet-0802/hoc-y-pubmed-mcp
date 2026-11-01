import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pubmed

XML = b"""<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><ArticleTitle>Randomized study of teaching</ArticleTitle><Journal><Title>Medical Education</Title><JournalIssue><PubDate><Year>2026</Year></PubDate></JournalIssue></Journal><Abstract><AbstractText Label="RESULTS">Sample text.</AbstractText></Abstract><PublicationTypeList><PublicationType>Randomized Controlled Trial</PublicationType></PublicationTypeList></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1000/example</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>"""


def test_parse_metadata():
    item = pubmed._parse_pubmed_xml(XML)[0]
    assert item['pmid'] == '12345'
    assert item['doi'] == '10.1000/example'
    assert item['abstract_available'] is True
    assert 'abstract' not in item


def test_fetch_has_abstract(monkeypatch):
    async def fake_get(path, params): return XML
    monkeypatch.setattr(pubmed, '_ncbi_get', fake_get)
    import asyncio
    item=asyncio.run(pubmed.fetch_medical_article('12345'))
    assert item['status'] == 'ok'
    assert item['abstract'] == 'RESULTS: Sample text.'
    assert item['abstract_is_full_text'] is False


def test_search_and_filter(monkeypatch):
    calls=[]
    async def fake_get(path, params):
        calls.append((path,params))
        if path == 'esearch.fcgi': return b'<eSearchResult><Count>1</Count><IdList><Id>12345</Id></IdList></eSearchResult>'
        return XML
    monkeypatch.setattr(pubmed, '_ncbi_get', fake_get)
    import asyncio
    result=asyncio.run(pubmed.search_medical_literature('medical education', study_type='randomized_trial', since_year=2020))
    assert len(result['articles']) == 1
    assert 'randomized controlled trial[pt]' in calls[0][1]['term']
    assert '2020:3000[dp]' in calls[0][1]['term']


def test_bad_input_rejected():
    import asyncio
    for pmid in ('123 OR 1=1', '1,2','abc',''):
        with pytest.raises(ValueError): asyncio.run(pubmed.fetch_medical_article(pmid))
    with pytest.raises(ValueError): pubmed._check_query('x',5,'any',None)
    with pytest.raises(ValueError): pubmed._check_query('example',5,'unsupported',None)
    with pytest.raises(ValueError): pubmed._check_query('example',99,'any',None)
