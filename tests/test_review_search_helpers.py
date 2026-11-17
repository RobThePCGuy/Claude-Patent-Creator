"""Search helper regressions from review findings 32 and 36-41."""
import importlib
import importlib.util
import json
import os
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


@pytest.mark.parametrize('query', ['sensor OR', '(sensor', 'sensor)', 'sensor OR AND lens'])
def test_malformed_boolean_query_fails_before_billing(query):
    obj = searcher()
    with pytest.raises(ValueError):
        obj.search_by_keywords(query)
    assert obj.client.sql is None


def test_mpep_failed_initialization_never_caches_ready(monkeypatch, tmp_path):
    mod = helper('skills/mpep-search/mpep_search.py', 'mpep_helper_retry')
    # A real MPEPIndex with a missing file; avoid loading models in its constructor.
    index = mod.MPEPIndex.__new__(mod.MPEPIndex)
    index.index_file = tmp_path / 'missing.faiss'
    index.chunks = []
    monkeypatch.setattr(mod, 'MPEPIndex', lambda: index)
    assert not mod.check_index_status()['ready']
    assert not mod.check_index_status()['ready']


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
