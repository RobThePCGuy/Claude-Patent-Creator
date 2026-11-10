"""Search helper regressions from review findings 32 and 36-41."""
import importlib
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

bq = importlib.import_module('mcp_server.bigquery_search')
ROOT = Path(__file__).resolve().parents[1]


def helper(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class QueryClient:
    def __init__(self):
        self.sql = None
        self.params = {}

    def query(self, sql, job_config, **kwargs):
        self.sql = sql
        self.params = {p.name: (p.values if hasattr(p, "values") else p.value) for p in job_config.query_parameters}
        return SimpleNamespace(total_bytes_processed=0, result=lambda **kw: [])


def searcher():
    obj = bq.BigQueryPatentSearch.__new__(bq.BigQueryPatentSearch)
    obj.client = QueryClient()
    return obj


@pytest.mark.parametrize(('query', 'title', 'expected'), [
    ('encryption OR cryptography', 'encryption', True),
    ('(mobile OR wireless) AND security', 'mobile security', True),
    ('(mobile OR wireless) AND security', 'mobile', False),
    ('sensor NOT optical', 'optical sensor', False),
    ('sensor NOT optical', 'sensor', True),
    ('sensor NOT optical', None, False),
    ('"wireless power" OR implant', 'implant', True),
    ('"wireless power", sensor', 'wireless power sensor', True),
])
def test_boolean_predicate_matches_query(query, title, expected):
    obj = searcher()
    obj.search_by_keywords(query, search_fields=['title'])
    where = obj.client.sql.split('WHERE', 1)[1].split('ORDER BY')[0]
    where = where.replace('LOWER(title_localized[SAFE_OFFSET(0)].text)', 'LOWER(title)')
    with sqlite3.connect(':memory:') as db:
        result = db.execute('SELECT 1 FROM (SELECT :title AS title, "US" AS country_code) WHERE ' + where,
                            {**obj.client.params, 'title': title}).fetchone()
    assert bool(result) is expected


@pytest.mark.parametrize('query', ['sensor OR', '(sensor', 'sensor)', 'sensor OR AND lens'])
def test_malformed_boolean_query_fails_before_billing(query):
    obj = searcher()
    with pytest.raises(ValueError):
        obj.search_by_keywords(query)
    assert obj.client.sql is None


def test_prior_art_combines_all_filters():
    mod = helper('skills/prior-art-search/prior_art_types.py', 'prior_helper_review')
    obj = searcher()
    mod._bigquery_searcher = obj
    result = mod.search_prior_art('sensor', country='EP', start_year=2024,
                                  end_year=2025, cpc_filter=['G06F', 'H04L'])
    assert result['success'], result
    params = obj.client.params
    assert params['term0'] == '%sensor%'
    assert params['start_yyyymmdd'] == 20240101
    assert params['end_yyyymmdd'] == 20251231
    assert params['cpc_prefixes'] == ['G06F', 'H04L']
    assert 'STARTS_WITH' in obj.client.sql


def test_prior_art_worldwide_has_no_country_predicate():
    mod = helper('skills/prior-art-search/prior_art_types.py', 'prior_helper_world')
    obj = searcher()
    mod._bigquery_searcher = obj
    result = mod.search_prior_art('sensor', country=None)
    assert result['success'], result
    assert result['query_info']['country'] is None
    assert 'country_code = @country' not in obj.client.sql
    assert 'country' not in obj.client.params
    assert 'claims_localized' in obj.client.sql


@pytest.mark.parametrize('section', ['608.01', '608.01(b)'])
def test_mpep_helper_uses_body_headings_and_reports_limits(section):
    mod = helper('skills/mpep-search/mpep_search.py', 'mpep_helper_review')
    mod._mpep_index = SimpleNamespace(
        chunks=[f'{section} Requested title [R-01.2024]\nBody.', 'Continuation.'],
        metadata=[{'section': 'MPEP 600', 'page': p, 'source': 'MPEP'} for p in [1, 2]],
    )
    result = mod.get_mpep_section(section, max_chunks=1)
    assert result['success'], result
    assert result['boundary'] == 'approximate'
    assert result['truncated']
    assert result['total_chunks'] == 2


def test_mpep_failed_initialization_never_caches_ready(monkeypatch, tmp_path):
    mod = helper('skills/mpep-search/mpep_search.py', 'mpep_helper_retry')
    # A real MPEPIndex with a missing file; avoid loading models in its constructor.
    index = mod.MPEPIndex.__new__(mod.MPEPIndex)
    index.index_file = tmp_path / 'missing.faiss'
    index.chunks = []
    monkeypatch.setattr(mod, 'MPEPIndex', lambda: index)
    assert not mod.check_index_status()['ready']
    assert not mod.check_index_status()['ready']
    assert mod._mpep_index is None


@pytest.mark.parametrize("kind", ["project", "paths"])
def test_direct_helpers_read_saved_config_in_fresh_process(tmp_path, kind):
    (tmp_path / 'config.json').write_text(json.dumps({
        'PATENT_DATA_DIR': str(tmp_path / 'saved data'), 'GOOGLE_CLOUD_PROJECT': 'saved-project',
    }))
    env = {k: v for k, v in os.environ.items()
           if k not in ('PATENT_DATA_DIR', 'GOOGLE_CLOUD_PROJECT', 'GOOGLE_APPLICATION_CREDENTIALS')}
    env.update(PATENT_CONFIG_DIR=str(tmp_path), PYTHONPATH=f'{ROOT}:{ROOT / "mcp_server"}')
    project_code = '''
from unittest.mock import patch
from mcp_server.bigquery_search import BigQueryPatentSearch
with patch('google.cloud.bigquery.Client'):
    assert BigQueryPatentSearch().billing_project == 'saved-project'
'''
    paths_code = '''
from mcp_server.data_paths import mpep_dir, index_dir, diagrams_dir
from pathlib import Path
import os
base = Path(os.environ['PATENT_CONFIG_DIR']) / 'saved data'
assert mpep_dir() == base / 'pdfs'
assert index_dir() == base / 'index'
assert diagrams_dir() == base / 'diagrams'
'''
    code = project_code if kind == 'project' else paths_code
    result = subprocess.run([sys.executable, '-c', code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
