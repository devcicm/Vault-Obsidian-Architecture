import json

import vault_search as search


def test_live_search_finds_unindexed_and_root_without_hidden_or_backup(tmp_path, monkeypatch):
    (tmp_path / '99_Index').mkdir()
    (tmp_path / '99_Index' / 'search-index.json').write_text(json.dumps({'notes': []}))
    (tmp_path / '07_Knowledge').mkdir()
    (tmp_path / '07_Knowledge' / 'new.md').write_text('---\ntitle: unique-spectrum\n---\nNew body', encoding='utf-8')
    (tmp_path / 'ROOT.md').write_text('---\ntitle: unique-spectrum root\n---\nRoot body', encoding='utf-8')
    (tmp_path / '.history').mkdir()
    (tmp_path / '.history' / 'old.md').write_text('unique-spectrum', encoding='utf-8')
    (tmp_path / 'vault-backups').mkdir()
    (tmp_path / 'vault-backups' / 'old.md').write_text('unique-spectrum', encoding='utf-8')
    monkeypatch.setattr(search, '_raiz', lambda: tmp_path)
    monkeypatch.setattr(search, '_index_file', lambda: tmp_path / '99_Index' / 'search-index.json')
    monkeypatch.setenv('VAULT_MCP_LIVE_SEARCH', '1')
    result = search.vault_search('unique-spectrum')
    assert result['ok'] and not result['incomplete']
    assert {n['path'] for n in result['results']} == {'ROOT.md', '07_Knowledge/new.md'}
    monkeypatch.delenv('VAULT_MCP_LIVE_SEARCH')
    assert search.vault_search('unique-spectrum')['results'] == []


def test_live_search_reports_unreadable_files(tmp_path, monkeypatch):
    (tmp_path / 'bad.md').write_bytes(b'\xff')
    monkeypatch.setattr(search, '_raiz', lambda: tmp_path)
    monkeypatch.setenv('VAULT_MCP_LIVE_SEARCH', '1')
    result = search.vault_search('missing')
    assert result['incomplete'] and len(result['skipped']) == 1
