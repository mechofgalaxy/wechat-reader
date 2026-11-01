"""Portable application contracts using isolated, fictional state."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import reader_app
import runtime_paths

class PortableTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='reader test ')
        self.root=Path(self.temp.name)
        self.env={**os.environ,'WECHAT_READER_HOME':str(self.root/'state with spaces')}
    def tearDown(self):self.temp.cleanup()
    def cli(self,*args):
        return subprocess.run([sys.executable,str(ROOT/'reader_app.py'),*args],env=self.env,capture_output=True,text=True)
    def test_demo_works_without_account_or_persistent_state(self):
        r=self.cli('demo');self.assertEqual(r.returncode,0,r.stderr)
        d=json.loads(r.stdout);self.assertEqual(d['data']['messages'][0]['text'],'This is a fictional demo message.')
        self.assertFalse((self.root/'state with spaces').exists())
    def test_demo_ignores_legacy_account_environment(self):
        poison=self.root/'unrelated-account-keys.json';poison.write_text('invalid unrelated private material')
        self.env.update(RION_WECHAT_READER_KEYS=str(poison),RION_WECHAT_READER_CONFIG=str(poison))
        r=self.cli('demo');self.assertEqual(r.returncode,0,r.stderr+r.stdout)
        self.assertEqual(json.loads(r.stdout)['data']['messages'][0]['text'],'This is a fictional demo message.')
        self.assertEqual(poison.read_text(),'invalid unrelated private material')
    def test_config_without_keys_stays_with_its_own_directory(self):
        config=self.root/'reader.json';config.write_text('{}')
        own_keys=self.root/'keys.json';own_keys.write_text('{"keys":{}}')
        with mock.patch.dict(os.environ,{'RION_WECHAT_READER_KEYS':str(self.root/'other.json')}):
            db=reader_app.reader.DatabaseSet(config)
        self.assertEqual(db.keys_path,own_keys);self.assertEqual(db.keys,{'keys':{}})
    def test_helper_launch_failure_is_not_ready(self):
        helper=self.root/'image_native';helper.write_text('fixture')
        with mock.patch.object(reader_app.platform,'system',return_value='Darwin'),mock.patch.object(reader_app.subprocess,'run',side_effect=[mock.Mock(returncode=0,stdout=b''),mock.Mock(returncode=-9,stdout=b'')]):
            state=reader_app.image_runtime_status(helper)
        self.assertTrue(state['present']);self.assertTrue(state['execution_tested']);self.assertFalse(state['ready'])
    def test_quarantined_helper_is_reported_without_execution(self):
        helper=self.root/'image_native';helper.write_text('fixture')
        with mock.patch.object(reader_app.platform,'system',return_value='Darwin'),mock.patch.object(reader_app.subprocess,'run',return_value=mock.Mock(returncode=0,stdout=b'com.apple.quarantine\n')) as run:
            state=reader_app.image_runtime_status(helper)
        run.assert_called_once();self.assertEqual(run.call_args.args[0][0],'/usr/bin/xattr')
        self.assertEqual(state['status'],'macos_security_review_required');self.assertFalse(state['ready'])
    def test_runtime_does_not_claim_account_access(self):
        r=self.cli('runtime-status');self.assertEqual(r.returncode,0,r.stderr)
        d=json.loads(r.stdout);self.assertEqual(d['account_access'],'not_checked');self.assertFalse(d['network_used'])
    def test_read_requires_account(self):
        r=self.cli('search','anything');self.assertEqual(r.returncode,2);self.assertIn('Select an account',r.stderr)
    def test_unknown_profile_never_falls_back(self):
        r=self.cli('--profile','missing','sessions');self.assertEqual(r.returncode,2);self.assertIn('not ready',r.stderr)
    def test_profile_traversal_rejected(self):
        r=self.cli('--profile','../other','sessions');self.assertEqual(r.returncode,2)
    def test_noninteractive_onboarding_requires_explicit_inputs(self):
        r=self.cli('onboard');self.assertEqual(r.returncode,2);self.assertFalse((self.root/'state with spaces').exists())
    def test_existing_profile_is_never_overwritten(self):
        profile=self.root/'state with spaces/profiles/demo';profile.mkdir(parents=True)
        sentinel=profile/'reader.json';sentinel.write_text('original')
        source=self.root/'access.json';source.write_text('{}');source.chmod(0o600)
        r=self.cli('onboard','--name','demo','--database-root',str(self.root),'--access-file',str(source))
        self.assertEqual(r.returncode,2);self.assertEqual(sentinel.read_text(),'original')
    def test_runtime_paths_are_per_user(self):
        with mock.patch.dict(os.environ,{'WECHAT_READER_HOME':str(self.root/'alternate')}):
            self.assertTrue(runtime_paths.model_path('turbo').is_relative_to((self.root/'alternate').resolve()))
            self.assertNotIn('snapshots',str(runtime_paths.model_path('turbo')))
    def test_unknown_model_has_clear_error(self):
        r=self.cli('models','install','arbitrary');self.assertEqual(r.returncode,2)
    def test_media_worker_rejects_nonmedia(self):
        r=subprocess.run([sys.executable,'-I',str(ROOT/'media_worker.py')],input=b'not-media',capture_output=True)
        self.assertNotEqual(r.returncode,0);self.assertEqual(r.stdout,b'')
    def test_installer_help_does_not_create_prefix(self):
        r=subprocess.run(['sh',str(ROOT/'install.sh'),'--help'],env=self.env,capture_output=True,text=True)
        self.assertEqual(r.returncode,0);self.assertFalse((self.root/'state with spaces').exists())

if __name__=='__main__':unittest.main()
