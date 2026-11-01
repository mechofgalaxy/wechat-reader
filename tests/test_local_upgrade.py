"""Regression scenarios use only synthetic SQLite databases, never account data."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock
import test_reader_upstream as fixtures

spec = importlib.util.spec_from_file_location('reader_under_test', fixtures.CLI)
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)

class LocalUpgradeTest(unittest.TestCase):
    setUp = fixtures.ReaderContractTest.setUp
    tearDown = fixtures.ReaderContractTest.tearDown
    _build_fixtures = fixtures.ReaderContractTest._build_fixtures
    run_cli = fixtures.ReaderContractTest.run_cli
    run_with_config = fixtures.ReaderContractTest.run_with_config

    def config_update(self, **fields):
        config = json.loads(self.config.read_text())
        config.update(fields)
        self.config.write_text(json.dumps(config))

    def db(self):
        return reader.DatabaseSet(self.config)

    def report(self, **kw):
        return reader.freshness_report(self.db(), **kw)

    def cli_freshness(self, *args):
        return self.run_cli('freshness', *args)['data']['freshness']

    def session_time(self, value):
        with sqlite3.connect(self.session) as conn:
            conn.execute("UPDATE SessionTable SET last_timestamp=? WHERE username='wxid_alice'", (value,))

    def test_old_but_synchronized_chat_is_fresh(self):
        result = self.cli_freshness('--chat', 'wxid_alice')
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['chat_latest_timestamp'], 200)
        self.assertEqual(result['timestamp_checked_chat_count'], 1)
        self.assertEqual(result['scope'], 'configured_local_databases_only')

    def test_session_ahead_warns_and_threshold_is_explicit(self):
        self.session_time(321)
        result = self.cli_freshness('--chat', 'wxid_alice')
        self.assertEqual(result['status'], 'possibly_stale')
        self.assertEqual(result['max_session_lag_seconds'], 121)
        self.assertIn('session_ahead_of_readable_messages', result['warnings'])
        self.assertEqual(self.cli_freshness('--chat', 'wxid_alice', '--stale-after-seconds', '121')['status'], 'ok')

    def test_historical_and_empty_filtered_queries_check_unfiltered_latest(self):
        result = self.run_cli('timeline', 'wxid_alice', '--before', '150')['data']
        self.assertEqual([x['local_id'] for x in result['messages']], [1])
        self.assertEqual(result['freshness']['status'], 'ok')
        self.assertTrue(result['freshness']['query_windowed'])
        result = self.run_cli('search', 'not-present', '--chat', 'wxid_alice')['data']
        self.assertEqual(result['messages'], [])
        self.assertEqual(result['freshness']['chat_latest_timestamp'], 200)
        self.assertEqual(result['freshness']['status'], 'ok')

    def test_empty_global_search_does_not_claim_timestamp_verification(self):
        result = self.run_cli('search', 'not-present')['data']['freshness']
        self.assertEqual(result['status'], 'inventory_only')
        self.assertEqual(result['timestamp_checked_chat_count'], 0)

    def test_inventory_only_opens_no_database(self):
        db = self.db()
        with mock.patch.object(db, 'connect', side_effect=AssertionError('must not open')):
            result = reader.freshness_report(db)
        self.assertEqual(result['status'], 'inventory_only')
        self.assertTrue(result['inventory_complete'])

    def test_unknown_numbered_shards_detected_but_never_opened(self):
        unknown = self.data_root / 'message_1.db'
        unknown.write_bytes(b'not a database; must not be opened')
        (self.data_root / 'message_fts.db').touch()
        (self.data_root / 'message_resource.db').touch()
        (self.data_root / 'message_2.db-wal').touch()
        db = self.db()
        original = db.connect
        seen = []
        @contextlib.contextmanager
        def tracked(path):
            seen.append(path)
            with original(path) as conn:
                yield conn
        with mock.patch.object(db, 'connect', tracked):
            result = reader.freshness_report(db, all_chats=True, verify_timestamps=True)
        self.assertEqual(result['status'], 'incomplete_shards')
        self.assertEqual(result['unknown_shards'], ['data with spaces/message_1.db'])
        self.assertEqual(result['numbered_shards_on_disk'], 2)
        self.assertNotIn(unknown, seen)

    def test_sibling_biz_family_and_account_boundary(self):
        root = self.data_root / 'selected' / 'db_storage'
        (root / 'message').mkdir(parents=True)
        (root / 'biz_message').mkdir()
        target = root / 'message' / 'message_0.db'
        shutil.copy2(self.message, target)
        (root / 'biz_message' / 'biz_message_0.db').touch()
        other = self.data_root / 'other-account' / 'db_storage' / 'message'
        other.mkdir(parents=True)
        (other / 'message_99.db').touch()
        self.config_update(message_dbs=[str(target)])
        result = self.report()
        self.assertEqual(result['unknown_shards'], ['biz_message/biz_message_0.db'])
        self.assertEqual(result['numbered_shards_on_disk'], 2)

    def test_missing_and_duplicate_configured_shards(self):
        self.config_update(message_dbs=[str(self.message), str(self.data_root / 'message_1.db'), str(self.message)])
        result = self.report()
        self.assertEqual(result['status'], 'incomplete_shards')
        self.assertEqual(result['duplicate_configured_shard_count'], 1)
        self.assertEqual(result['missing_shards'], ['data with spaces/message_1.db'])

    def test_inventory_permission_error_is_not_complete(self):
        with mock.patch.object(Path, 'iterdir', side_effect=PermissionError('private detail')):
            result = self.report()
        self.assertEqual(result['status'], 'incomplete_shards')
        self.assertIn('shard_inventory_unverified', result['warnings'])
        self.assertNotIn('private detail', json.dumps(result))

    def test_unknown_shards_degrade_doctor_and_access_plan(self):
        (self.data_root / 'message_7.db').touch()
        result = self.run_cli('access-plan')['data']
        self.assertTrue(result['live_database_read_ok'])
        self.assertEqual(result['state'], 'incomplete_shards')
        result = self.run_cli('doctor')['data']
        self.assertEqual(result['summary'], 'degraded')
        self.assertIn('unconfigured_numbered_shards', [d['code'] for d in result['diagnostics']])

    def test_unreadable_timestamp_is_redacted_and_unverified(self):
        db = self.db()
        with mock.patch.object(db, 'connect', side_effect=OSError('sensitive fake error')):
            result = reader.freshness_report(db, talkers=['wxid_alice'], verify_timestamps=True)
        self.assertEqual(result['status'], 'unverified_timestamps')
        self.assertEqual(result['timestamp_unverified_chat_count'], 1)
        self.assertEqual(result['timestamp_checked_chat_count'], 0)
        self.assertNotIn('sensitive fake error', json.dumps(result))

    def test_missing_session_is_unverified(self):
        with sqlite3.connect(self.session) as conn:
            conn.execute("DELETE FROM SessionTable WHERE username='wxid_alice'")
        result = self.report(talkers=['wxid_alice'], verify_timestamps=True)
        self.assertEqual(result['status'], 'unverified_timestamps')
        self.assertEqual(result['timestamp_unverified_chat_count'], 1)

    def test_missing_message_table_is_unverified_not_compared_to_epoch(self):
        with sqlite3.connect(self.message) as conn:
            conn.execute('DROP TABLE "' + reader.message_table('wxid_alice') + '"')
        result = self.report(talkers=['wxid_alice'], verify_timestamps=True)
        self.assertEqual(result['status'], 'unverified_timestamps')
        self.assertEqual(result['missing_message_chat_count'], 1)
        self.assertEqual(result['max_session_lag_seconds'], 0)
        self.assertEqual(result['lagging_chat_count'], 0)

    def test_all_chats_reports_metadata_without_names_or_bodies(self):
        result = self.cli_freshness()
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['timestamp_checked_chat_count'], 2)
        self.assertEqual(result['per_shard_latest_timestamp'], {'data with spaces/message_0.db': 330})
        serialized = json.dumps(result, ensure_ascii=False)
        for text in ['wxid_alice', 'team@chatroom', '明天发方案', '合作方', str(self.data_root)]:
            self.assertNotIn(text, serialized)

    def test_source_change_since_query_start_warns(self):
        db = self.db()
        self.session_time(200)
        result = reader.freshness_report(db, talkers=['wxid_alice'], verify_timestamps=True)
        # Even a same-value SQL update may be optimized away; force metadata mutation.
        if not result['changed_sources']:
            stamp = self.message.stat()
            os.utime(self.message, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 1_000_000))
            result = reader.freshness_report(db, talkers=['wxid_alice'], verify_timestamps=True)
        self.assertEqual(result['status'], 'possibly_stale')
        self.assertIn('source_changed_during_read', result['warnings'])

    def test_shard_appearing_during_check_is_detected(self):
        db = self.db()
        original = db.connect
        @contextlib.contextmanager
        def tracked(path):
            with original(path) as conn:
                yield conn
            (self.data_root / 'message_9.db').touch()
        with mock.patch.object(db, 'connect', tracked):
            result = reader.freshness_report(db, talkers=['wxid_alice'], verify_timestamps=True)
        self.assertEqual(result['status'], 'incomplete_shards')
        self.assertIn('data with spaces/message_9.db', result['unknown_shards'])

    def test_search_cross_shard_sender_type_offset_and_context(self):
        target = self.data_root / 'message_1.db'
        shutil.copy2(self.message, target)
        with sqlite3.connect(target) as conn:
            conn.execute('DELETE FROM "' + reader.message_table('team@chatroom') + '"')
            table = reader.message_table('wxid_alice')
            conn.execute(f'DELETE FROM "{table}"')
            conn.execute(f'INSERT INTO "{table}" VALUES(3,103,1,3,1,250,0,"你好 later","")')
            conn.execute(f'INSERT INTO "{table}" VALUES(4,104,1,4,2,280,0,"你好 outgoing","")')
        self.config_update(message_dbs=[str(self.message), str(target)])
        for filters in [('--sender', 'wxid_alice'), ('--no-from-me',)]:
            result = self.run_cli('search', '你好', '--type', 'text', '--base-kind', '1', *filters, '--limit', '1')['data']
            self.assertEqual([r['local_id'] for r in result['messages']], [3])
            self.assertTrue(result['query']['has_more'])
            result = self.run_cli('search', '你好', '--type', 'text', *filters, '--limit', '1', '--offset', '1')['data']
            self.assertEqual([r['local_id'] for r in result['messages']], [1])
            self.assertFalse(result['query']['has_more'])
        result = self.run_cli('search-context', '你好', '--no-from-me', '--limit', '1')['data']
        self.assertEqual(result['results'][0]['match']['local_id'], 3)

    def test_search_modes_and_zero_negative_pagination(self):
        for mode, term in [('exact', '你好'), ('prefix', '你'), ('regex', '^你'), ('substring', '好')]:
            data = self.run_cli('search', term, '--search-mode', mode, '--limit', '1')['data']
            self.assertEqual(data['messages'][0]['local_id'], 1)
            self.assertFalse(data['query']['has_more'])
        data = self.run_cli('search', '.', '--search-mode', 'regex', '--limit', '0')['data']
        self.assertEqual(data['messages'], [])
        self.assertFalse(data['query']['has_more'])
        for args in [('search', '.', '--limit', '-1'), ('search', '.', '--offset', '-1'), ('search-context', '.', '--limit', '-1'), ('freshness', '--stale-after-seconds', '-1')]:
            result = self.run_with_config(self.config, *args, expected=1)
            self.assertEqual(result['error']['code'], 'invalid_argument')

    def test_context_no_text_removes_neighbor_raw_body(self):
        result = self.run_cli('search-context', '明天发方案', '--no-include-text')['data']['results'][0]
        for row in [result['match'], *result['context']]:
            for key in ['message_content', 'compress_content', 'text', 'content']:
                self.assertNotIn(key, row)

    def test_empty_tail_warning_stderr_preserves_jsonl_stdout(self):
        self.session_time(500)
        result = subprocess.run([sys.executable, str(fixtures.CLI), '--config', str(self.config), 'tail', 'wxid_alice', '--since-local-id', '999', '--jsonl'], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '')
        self.assertEqual(json.loads(result.stderr)['freshness']['status'], 'possibly_stale')

    def test_aggregate_and_zero_timestamp_sessions_do_not_create_fake_lag(self):
        with sqlite3.connect(self.session) as conn:
            conn.execute("INSERT INTO SessionTable(username,last_timestamp) VALUES('brandsessionholder',1700000000)")
            conn.execute("INSERT INTO SessionTable(username,last_timestamp) VALUES('empty_session',0)")
        result = self.cli_freshness()
        self.assertEqual(result['status'], 'unverified_timestamps')
        self.assertEqual(result['timestamp_checked_chat_count'], 2)
        self.assertEqual(result['timestamp_unverified_chat_count'], 2)
        self.assertEqual(result['missing_message_chat_count'], 1)
        self.assertEqual(result['empty_session_timestamp_count'], 1)
        self.assertEqual(result['max_session_lag_seconds'], 0)

    def test_empty_message_table_cannot_be_declared_fresh(self):
        with sqlite3.connect(self.message) as conn:
            conn.execute('DELETE FROM "' + reader.message_table('wxid_alice') + '"')
        result = self.cli_freshness('--chat', 'wxid_alice')
        self.assertEqual(result['status'], 'unverified_timestamps')
        self.assertEqual(result['missing_message_chat_count'], 1)
        self.assertEqual(result['timestamp_checked_chat_count'], 0)

    def test_freshness_tool_contract(self):
        result = self.run_cli('tool-schema', 'freshness')['data']
        self.assertTrue(result['tool']['read_only'])
        self.assertIn('inventory_only', result['tool']['inputSchema']['properties'])

if __name__ == '__main__':
    unittest.main()
