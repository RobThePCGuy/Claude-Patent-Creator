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


def test_unrecognized_epc_does_not_guess_classification(tmp_path):
    fitz = pytest.importorskip('pymupdf')
    path = tmp_path / 'unknown.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((72, 72), 'Implementing Regulations\n' + 'unknown ' * 30)
        doc.save(path)
    assert ms.MPEPIndex.__new__(ms.MPEPIndex).extract_text_from_epc(path) == []


def test_epc_legacy_warning():
    assert ms.get_index_warnings([{'source': 'EPC_RULES'}])
    assert ms.get_index_warnings([{'source': 'EPC'}, {'source': 'EPC_RULES'}]) == []
    assert ms.get_index_warnings([{'source': 'MPEP'}]) == []


def test_section_does_not_match_number_prefix_or_wrong_source():
    tool = section_tool(['[MPEP 600] 608.01(b)  Abstract [R-01.2024]\nText'],
                        [{'section': 'MPEP 600', 'source': 'MPEP', 'page': 1}])
    assert 'error' in tool('608.01')


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


@pytest.mark.parametrize('failure', ['404', 'boilerplate'])
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
        if key == 'f_iv_4_1.html':
            return Response('<html>Unavailable</html>', 404 if failure == '404' else 200)
        return Response(pages[key])
    monkeypatch.setattr(ed.requests, 'get', get)
    dest = tmp_path / 'guidelines.txt'
    ok = ed._scrape_epo_guidelines_html(dest, year=2026)
    assert ok is False
    assert not dest.exists(), 'partial/navigation-only corpus must not appear installed'


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
    assert warnings


def test_chapter_lookup_is_exact_and_source_scoped():
    tool = section_tool(['chapter', 'wrong chapter', 'wrong source'], [
        {'section': 'MPEP 600', 'source': 'MPEP', 'page': 1},
        {'section': 'MPEP 6000', 'source': 'MPEP', 'page': 1},
        {'section': 'MPEP 600', 'source': 'EPC', 'page': 1},
    ])
    result = tool('600')
    assert [c['text'] for c in result['chunks']] == ['chapter']


def test_law_passages_disclose_legacy_epc_misclassification():
    idx = SimpleNamespace(metadata=[{'source': 'EPC_RULES'}])
    idx.search = lambda **kw: [{'metadata': {'source': 'EPC_RULES'}, 'relevance_score': 1}]
    coverage = law_tool(idx)('Article 84', jurisdiction='EPO')[0]['coverage']
    assert coverage['index_warnings']
