"""Regression evidence for the third fresh-user retrieval failures."""
import importlib
from types import SimpleNamespace

import pytest

ms = importlib.import_module('mcp_server.mpep_search')
mt = importlib.import_module('mcp_server.tools.mpep_tools')
lt = importlib.import_module('mcp_server.tools.patent_law_tools')
ed = importlib.import_module('mcp_server.epo_downloaders')


class MCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register


def section_tool(chunks, metadata):
    mcp = MCP()
    idx = ms.MPEPIndex.__new__(ms.MPEPIndex)
    idx.chunks, idx.metadata = chunks, metadata
    mt.register_mpep_tools(mcp, idx, None, None, None, None, lambda _: lambda f: f, None)
    return mcp.tools['get_mpep_section']


def test_epc_uses_body_bookmarks_not_amendment_table(tmp_path):
    fitz = pytest.importorskip('pymupdf')
    path = tmp_path / 'epc.pdf'
    with fitz.open() as doc:
        for text in ['Amendments\nImplementing Regulations\n' + 'Front matter. ' * 10,
                     'Article 8479\nClaims\nThe claims shall be clear and concise. ' * 5,
                     'Implementing Regulations\nTable of contents\nRule 1',
                     'Rule 1\nWritten proceedings\nAll proceedings in writing. ' * 5,
                     'Rules relating to Fees\nArticle 1\nOther provisions. ' * 5]:
            page = doc.new_page()
            page.insert_text((72, 72), text)
        doc.set_toc([[1, 'Convention', 1], [2, 'Article 84 Claims', 2],
                     [1, 'Implementing Regulations to the Convention', 3],
                     [2, 'Rule 1 Written proceedings', 4], [1, 'Rules relating to Fees', 5]])
        doc.save(path)
    chunks = ms.MPEPIndex.__new__(ms.MPEPIndex).extract_text_from_epc(path)
    articles = [c for c in chunks if c['source'] == 'EPC']
    rules = [c for c in chunks if c['source'] == 'EPC_RULES']
    assert articles and rules
    assert {c['page'] for c in articles} == {2}
    assert all(c['is_statute'] and not c['is_regulation'] for c in articles)
    assert all('84' in c['section'] and '8479' not in c['section'] for c in articles)
    assert {c['page'] for c in rules} == {4}


def test_unrecognized_epc_does_not_guess_classification(tmp_path):
    fitz = pytest.importorskip('pymupdf')
    path = tmp_path / 'unknown.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), 'Implementing Regulations\n' + 'unknown ' * 30)
        doc.save(path)
    assert ms.MPEPIndex.__new__(ms.MPEPIndex).extract_text_from_epc(path) == []


def test_epc_legacy_warning():
    assert 'setup --rebuild' in ms.get_index_warnings([{'source': 'EPC_RULES'}])[0]
    assert ms.get_index_warnings([{'source': 'EPC'}, {'source': 'EPC_RULES'}]) == []
    assert ms.get_index_warnings([{'source': 'MPEP'}]) == []


@pytest.mark.parametrize('section', ['608', '608.01(b)', '2173.02', '2111'])
def test_section_body_heading_not_contents_or_reference(section):
    chapter = f'MPEP {int(section.split(".")[0]) // 100 * 100}'
    chunks = [f'[{chapter}] Contents\n{section} \nTitle\n',
              f'[{chapter}] {section}  Discussion without a revision marker.',
              f'[{chapter}] Earlier text\n{section}  Requested title\n[R-01.2024]\nStart body.',
              f'[{chapter}] Continued body.',
              f'[{chapter}] 2199  Next section [R-01.2024]\nUnrelated body.']
    meta = [{'section': chapter, 'source': 'MPEP', 'page': p, 'file': 'mpep.pdf'}
            for p in [1, 2, 3, 4, 5]]
    tool = section_tool(chunks, meta)
    result = tool(section, max_chunks=1)
    assert result['chapter'] == chapter
    assert result['boundary'] == 'approximate'
    assert result['truncated'] is True
    assert result['total_chunks'] == 2
    assert 'Start body' in result['chunks'][0]['text']
    assert result['chunks'][0]['metadata']['page'] == 3
    missing = tool('699.99')
    assert 'search_mpep' in missing['error']


def test_section_does_not_match_number_prefix_or_wrong_source():
    tool = section_tool(['[MPEP 600] 608.01(b)  Abstract [R-01.2024]\nText'],
                        [{'section': 'MPEP 600', 'source': 'MPEP', 'page': 1}])
    assert 'error' in tool('608.01')
    assert 'error' in tool('608.01(b)', max_chunks=0)


def law_tool(index):
    mcp = MCP()
    lt.register_patent_law_tools(mcp, index, lambda *a, **k: None,
                                lambda *a, **k: None, None, None, None)
    return mcp.tools['search_patent_law']


@pytest.mark.parametrize('jurisdiction', ['EPO', None])
def test_partial_sources_disclosed_even_with_results(jurisdiction):
    idx = SimpleNamespace(metadata=[{'source': 'EPC'}, {'source': 'EPC_RULES'}])
    idx.search = lambda **kw: ([] if kw.get('source_filter') == 'EPO_GUIDELINES' else
                              [{'metadata': {'source': 'EPC'}, 'relevance_score': 1}])
    result = law_tool(idx)('claims', jurisdiction=jurisdiction)
    assert result[0]['relevance_score'] == 1
    coverage = result[0]['coverage']
    assert 'EPO_GUIDELINES' in coverage['missing_sources']
    assert 'EPC' in coverage['searched_sources']
    assert 'EPO_GUIDELINES' not in coverage['searched_sources']
    assert 'not searched' in coverage['warning']


def test_failed_source_is_not_called_missing():
    idx = SimpleNamespace(metadata=[{'source': s} for s in lt.JURISDICTION_SOURCES['EPO']])
    def search(**kw):
        if kw.get('source_filter') == 'EPO_GUIDELINES':
            raise RuntimeError('backend unavailable')
        return [{'metadata': {'source': 'EPC'}, 'relevance_score': 1}]
    idx.search = search
    coverage = law_tool(idx)('claims', jurisdiction='EPO')[0]['coverage']
    assert coverage['missing_sources'] == []
    assert coverage['failed_sources'] == ['EPO_GUIDELINES']


class Response:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code != 200:
            raise RuntimeError(f'HTTP {self.status_code}')


def test_guidelines_uses_published_pdf_and_falls_back(tmp_path, monkeypatch):
    urls = []
    monkeypatch.setattr(ed, '_download_file', lambda url, *a, **kw: urls.append(url) or False)
    monkeypatch.setattr(ed, '_scrape_epo_guidelines_html',
                        lambda path, year: path.write_text('HTML body') or True)
    assert ed.scrape_epo_guidelines(tmp_path, year=2026)
    assert urls == [
        'https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-2026-hyperlinked.pdf',
        'https://link.epo.org/web/legal/guidelines-epc/en-epc-guidelines-2026-hyperlinked.pdf?v=2026',
    ]
    assert (tmp_path / ed.EPO_GUIDELINES_FILE).read_text() == 'HTML body'


@pytest.mark.parametrize('failure', [None, '404', 'boilerplate'])
def test_html_fallback_follows_sections_and_rejects_incomplete_corpus(tmp_path, monkeypatch, failure):
    base = ed.EPO_GUIDELINES_BASE_URL + '/2026/'
    pages = {'index.html': '<h1>Guidelines for Examination</h1><div class="epolegal-content">' +
             ''.join(f'<a href="{p}_i.html">Part {p}</a>' for p in 'abcdefgh') + '</div>'}
    for part in 'abcdefgh':
        pages[part + '_i.html'] = ('<h1>Part</h1><div class="epolegal-content">'
                                '</div><div class="bottom-list">'
                                '<a href="f_iv_4_1.html">Clarity</a></div>')
    pages['f_iv_4_1.html'] = ('<h1>4.1 Clarity</h1><div class="epolegal-content">'
                             '<p>The claims shall be clear.</p><span class="Del">Obsolete text</span>'
                             '<a href="/en/legal/epc/2020/a84.html">Article 84</a>'
                             '<a href="e_xiv.html">Stale cross-reference</a></div>')
    def get(url, **kwargs):
        assert url.startswith(base), 'must stay in selected English edition'
        key = url.removeprefix(base)
        if key == 'f_iv_4_1.html' and failure:
            return Response('<html>Unavailable</html>', 404 if failure == '404' else 200)
        return Response(pages[key])
    monkeypatch.setattr(ed.requests, 'get', get)
    dest = tmp_path / 'guidelines.txt'
    ok = ed._scrape_epo_guidelines_html(dest, year=2026)
    if failure:
        assert ok is False
        assert not dest.exists(), 'partial/navigation-only corpus must not appear installed'
    else:
        assert ok is True
        text = dest.read_text()
        assert 'The claims shall be clear.' in text
        assert 'Obsolete text' not in text
        assert '10/10' in text
        assert base + 'f_iv_4_1.html' in text


def test_html_empty_chapter_follows_official_child_navigation(tmp_path, monkeypatch):
    base = ed.EPO_GUIDELINES_BASE_URL + '/2026/'
    def get(url, **kw):
        key = url.removeprefix(base)
        if key == 'index.html':
            return Response('<div class="epolegal-content">Guidelines ' + ''.join(
                f'<a href="{p}_i.html">Part {p}</a>' for p in 'abcdefgh') + '</div>')
        if key == 'f_iv_4_1.html':
            return Response('<div class="epolegal-content">Actual clarity body</div>')
        return Response('<div class="epolegal-content"></div><div class="bottom-list">'
                        '<a href="f_iv_4_1.html">Clarity</a></div>')
    monkeypatch.setattr(ed.requests, 'get', get)
    dest = tmp_path / 'guidelines.txt'
    assert ed._scrape_epo_guidelines_html(dest, year=2026)
    assert 'Actual clarity body' in dest.read_text()


def test_index_load_reports_legacy_warning(tmp_path, monkeypatch):
    import json
    idx = ms.MPEPIndex.__new__(ms.MPEPIndex)
    idx.index_file = tmp_path / 'index.faiss'
    idx.index_file.touch()
    idx.metadata_file = tmp_path / 'metadata.json'
    idx.metadata_file.write_text(json.dumps({'chunks': ['text'], 'metadata': [{'source': 'EPC_RULES'}]}))
    idx.bm25_file = tmp_path / 'absent.json'
    ms._load_vector_libs()  # faiss is imported on first index use
    monkeypatch.setattr(ms.faiss, 'read_index', lambda _: object())
    warnings = []
    monkeypatch.setattr(ms, '_log_warning', warnings.append)
    idx.build_index()
    assert any('setup --rebuild' in message for message in warnings)


def test_section_split_heading_order_and_descendants():
    chapter = 'MPEP 600'
    start = '608.01(b)  Abstract of the Disclosure\n'
    texts = [start, '[R-01.2024]\nAbstract body',
             '608.01(c)  Background [R-01.2024]\nOther body']
    metas = [{'section': chapter, 'source': 'MPEP', 'page': p} for p in [3, 3, 4]]
    tool = section_tool([texts[2], texts[0], texts[1]], [metas[2], metas[0], metas[1]])
    result = tool('608.01(b)')
    assert result['total_chunks'] == 2
    assert [c['metadata']['page'] for c in result['chunks']] == [3, 3]
    assert not result['truncated']


def test_chapter_lookup_is_exact_and_source_scoped():
    tool = section_tool(['chapter', 'wrong chapter', 'wrong source'], [
        {'section': 'MPEP 600', 'source': 'MPEP', 'page': 1},
        {'section': 'MPEP 6000', 'source': 'MPEP', 'page': 1},
        {'section': 'MPEP 600', 'source': 'EPC', 'page': 1},
    ])
    result = tool('600')
    assert result['boundary'] == 'exact'
    assert [c['text'] for c in result['chunks']] == ['chapter']


def test_pdf_error_cache_retry_extracts_published_pdf(tmp_path, monkeypatch):
    fitz = pytest.importorskip('pymupdf')
    def download(url, path, description, **kw):
        if '?v=2026' not in url:
            return False
        with fitz.open() as doc:
            doc.new_page().insert_text((72, 72), 'Guidelines for Examination\nApril 2026')
            doc.save(path)
        return True
    monkeypatch.setattr(ed, '_download_file', download)
    monkeypatch.setattr(ed, '_scrape_epo_guidelines_html', lambda *a, **kw: False)
    assert ed.scrape_epo_guidelines(tmp_path, year=2026)
    assert 'April 2026' in (tmp_path / ed.EPO_GUIDELINES_FILE).read_text()


def test_parent_section_includes_descendants_but_stops_at_peer():
    texts = ['608  Disclosure [R-01.2024]\nBody',
             '608.01  Specification [R-01.2024]\nSubsection',
             '608.01(b)  Abstract [R-01.2024]\nAbstract',
             '609  Information [R-01.2024]\nOther body']
    metas = [{'section': 'MPEP 600', 'source': 'MPEP', 'page': p} for p in range(1, 5)]
    result = section_tool(texts, metas)('608')
    assert result['total_chunks'] == 3
    assert [c['metadata']['page'] for c in result['chunks']] == [1, 2, 3]


def test_law_passages_disclose_legacy_epc_misclassification():
    idx = SimpleNamespace(metadata=[{'source': 'EPC_RULES'}])
    idx.search = lambda **kw: [{'metadata': {'source': 'EPC_RULES'}, 'relevance_score': 1}]
    coverage = law_tool(idx)('Article 84', jurisdiction='EPO')[0]['coverage']
    assert 'classification defect' in coverage['index_warnings'][0]
    assert 'unreliable' in coverage['index_warnings'][0]
