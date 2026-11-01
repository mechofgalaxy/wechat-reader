"""Real local integration with fictional accounts; native dialogs are mocked only."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock
import first_run as first
import test_reader_upstream as fixtures


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name).resolve()
        self.patch = mock.patch.dict(os.environ, {'HOME': str(self.home), 'WECHAT_READER_HOME': str(self.home/'app')})
        self.patch.start()

    def tearDown(self):
        self.patch.stop(); self.tmp.cleanup()

    def args(self, **kw):
        result = dict(name='personal', database_root=None, access_file=None, apply=False, request_access=False)
        result.update(kw); return SimpleNamespace(**result)

    def test_discovery_never_reads_messages_or_keys(self):
        base = self.home/'Documents/xwechat_files'
        for n in ('alice', 'bob'):
            (base/n/'db_storage').mkdir(parents=True)
            (base/n/'db_storage'/'private.db').write_bytes(b'PRIVATE-CONTENT')
        outside = self.home/'elsewhere'; (outside/'db_storage').mkdir(parents=True)
        (base/'symlink').symlink_to(outside, target_is_directory=True)
        with mock.patch.object(Path, 'read_bytes', side_effect=AssertionError('must not read content')):
            report = first.discover(self.home)
        self.assertEqual(len(report['candidates']), 2)
        self.assertFalse(report['chat_content_read'])
        self.assertNotIn('PRIVATE-CONTENT', json.dumps(report))

    def test_cloud_linux_does_not_claim_acquisition(self):
        with mock.patch.object(first.platform, 'system', return_value='Linux'):
            # Missing bundled helper cannot silently fall back to PATH or download one.
            with self.assertRaises(first.access.AccessError):
                first.bundled_provider()

    def test_invalid_name_and_symlink_prefix_fail(self):
        with self.assertRaises(first.access.AccessError): first.profile_path('../other')
        target=self.home/'target';target.mkdir()
        (self.home/'app').symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(first.access.AccessError, 'symlink'): first.profile_path('personal')

    def test_cancelled_native_consent_is_no_acquisition(self):
        with mock.patch.object(first.subprocess, 'run', return_value=SimpleNamespace(returncode=1)) as run:
            with self.assertRaisesRegex(first.access.AccessError, 'user_cancelled'):
                first.request_user_consent(self.home/'account/db_storage')
        cmd=run.call_args.args[0]
        self.assertEqual(cmd[0], '/usr/bin/osascript')
        self.assertIn('default button "Cancel"', cmd[2])
        self.assertFalse((self.home/'app').exists())

    def test_acquisition_waits_for_native_confirmation_and_rechecks(self):
        root=self.home/'db_storage';root.mkdir()
        sequence=[{'state':'provider_required'}, {'state':'authorization_required'}, {'state':'ready','live_database_read_ok':True}]
        with mock.patch.object(first.access,'onboard',side_effect=sequence) as onboarding, \
             mock.patch.object(first,'bundled_provider',return_value=(self.home/'helper','a'*64)), \
             mock.patch.object(first.access,'preflight_database_access'), \
             mock.patch.object(first.access,'preflight_debugger'), \
             mock.patch.object(first,'request_user_consent',side_effect=first.access.AccessError('user_cancelled')):
            with self.assertRaises(first.access.AccessError):first.connect(self.args(database_root=str(root),request_access=True))
            self.assertEqual(onboarding.call_count,2)

    def test_existing_material_to_real_read_and_repeat(self):
        if fixtures.SQLCIPHER is None:self.skipTest('SQLCipher unavailable')
        f=fixtures.ReaderContractTest();f.setUp()
        try:
            root=self.home/'account/db_storage';root.mkdir(parents=True)
            key='67'*32
            for source in (f.session,f.contact,f.message): f.encrypt_fixture(source,root/source.name,key)
            accessfile=self.home/'access.json';accessfile.write_text(json.dumps({p.name:key for p in root.glob('*.db')}));accessfile.chmod(0o600)
            original=accessfile.read_bytes()
            args=self.args(database_root=str(root),access_file=str(accessfile),apply=True)
            with mock.patch.object(first,'request_user_consent',side_effect=AssertionError('must reuse material')):
                result=first.connect(args)
            self.assertEqual(result['state'],'ready')
            self.assertTrue(result['live_database_read_ok'])
            self.assertNotIn(key,json.dumps(result))
            self.assertTrue(result['identity_needs_confirmation'])
            self.assertEqual(accessfile.read_bytes(),original)
            config=first.profile_path('personal')
            db=first.reader.DatabaseSet(config)
            self.assertTrue(first.reader.status(db)['status']['live_database_read_ok'])
            args.access_file=None
            self.assertTrue(first.connect(args)['reused_existing_configuration'])
            other=self.home/'another/db_storage';other.mkdir(parents=True)
            args.database_root=str(other)
            with self.assertRaisesRegex(first.access.AccessError,'different_database'):first.connect(args)
            self.assertEqual(config.stat().st_mode & 0o777,0o600)
        finally:f.tearDown()

    def test_errors_do_not_echo_private_exception(self):
        with mock.patch.object(first,'connect',side_effect=ValueError('SECRET-MATERIAL')), contextlib.redirect_stdout(io.StringIO()) as output:
            code=first.main(['--name','personal'])
        self.assertEqual(code,2);self.assertNotIn('SECRET-MATERIAL',output.getvalue())

    def test_noninteractive_discovery_has_no_persistent_effect(self):
        with mock.patch.object(first,'discover',return_value={'state':'needs_database_location'}),contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(first.main([]),1)
        self.assertFalse((self.home/'app').exists())

    def test_unconfigured_status_cannot_fall_back_to_other_accounts(self):
        with mock.patch.object(first.access,'access_status',side_effect=AssertionError('must not discover another account')),contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(first.main(['--name','unknown','--status']),1)
        self.assertEqual(json.loads(out.getvalue())['data']['state'],'profile_not_configured')

    def test_failed_first_attempt_still_reports_recovery_before_profile_exists(self):
        parent = self.home/'.local/share/wechat-reader-access/access-runs'
        parent.mkdir(parents=True)
        (parent/'recovery-required.lock').write_text('pending')
        with mock.patch.object(first.access,'access_status',side_effect=AssertionError('no account discovery')), \
             mock.patch.object(first.access,'recovery_process_check',return_value={'state':'unavailable'}), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(first.main(['--name','personal','--status']),1)
        data=json.loads(out.getvalue())['data']
        self.assertTrue(data['recovery_review_required'])
        self.assertEqual(data['next_step_code'],'review_wechat_recovery')


if __name__=='__main__':unittest.main()
