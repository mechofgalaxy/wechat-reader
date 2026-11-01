"""Synthetic-account tests: never open real WeChat databases."""
import hashlib,importlib.util,json,shutil,sqlite3,struct,unittest,wave,os,tempfile
from pathlib import Path
from unittest import mock
import test_reader_upstream as fixtures
from test_local_upgrade import reader
ROOT=fixtures.ROOT
spec=importlib.util.spec_from_file_location('voice',ROOT/'wechat_voice.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
SID=9007199254740993
SILK=(ROOT/'tests/fixtures/voice.silk').read_bytes()

def good_asr():
    return {'text':'这是测试。','language':'zh','segments':[{'start':0.,'end':1.,'text':'这是测试。','avg_logprob':-.2,'no_speech_prob':.01,'compression_ratio':1.} ]}

class VoiceTest(unittest.TestCase):
    tearDown=fixtures.ReaderContractTest.tearDown
    _build_fixtures=fixtures.ReaderContractTest._build_fixtures
    run_cli=fixtures.ReaderContractTest.run_cli
    run_with_config=fixtures.ReaderContractTest.run_with_config
    def setUp(self):
        fixtures.ReaderContractTest.setUp(self)
        self.account=self.data_root/'xwechat_files/wxid_me_1234';storage=self.account/'db_storage'
        for attr,sub in [('session','session'),('contact','contact'),('message','message')]:
            src=getattr(self,attr);dest=storage/sub/src.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest);setattr(self,attr,dest)
        cfg=json.loads(self.config.read_text());cfg.update(session_db=str(self.session),contact_db=str(self.contact),message_dbs=[str(self.message)])
        self.config.write_text(json.dumps(cfg));self.media=self.message.with_name('media_0.db')
        self.table='Msg_'+hashlib.md5(b'wxid_alice').hexdigest()
        with sqlite3.connect(self.message) as c:
            c.execute(f'INSERT INTO "{self.table}" VALUES(3,?,34,3,1,210,0,?,?)',(SID,'<msg><voicemsg voicelength="1000"/></msg>',''))
        with sqlite3.connect(self.media) as c:
            c.executescript('CREATE TABLE Name2Id(user_name TEXT); INSERT INTO Name2Id VALUES ("wxid_alice"),("wxid_other"); CREATE TABLE VoiceInfo(chat_name_id INTEGER,svr_id INTEGER,voice_data BLOB);')
            c.execute('INSERT INTO VoiceInfo VALUES(1,?,?)',(SID,SILK))
        self.db=reader.DatabaseSet(self.config)
    def fake_worker(self,mode,source=None,target=None,language='zh',model='turbo'):
        if mode=='status':return {'ok':True,'packages':{'pilk':'test'},'model_cached':True,'ffmpeg_available':True}
        if mode=='decode':
            with wave.open(str(target),'wb') as f:f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(b'\0\0'*24000)
            return {'ok':True,'duration_seconds':1.,'sample_rate':24000,'channels':1,'rms':.2}
        return good_asr()
    def read(self,**kw):
        with mock.patch.object(v,'worker',side_effect=self.fake_worker):return v.read_voice(self.db,'wxid_alice',str(SID),reader.decode_message_content,reader.source_version,**kw)
    def execute(self,sql,args=(),path=None):
        with sqlite3.connect(path or self.media) as c:c.execute(sql,args)
    def test_exact_id_and_full_pipeline(self):
        before=hashlib.sha256(self.media.read_bytes()).hexdigest();out=self.data_root/'audio.wav';r=self.read(output=out,transcribe=True)
        self.assertTrue(r['ready'],r);self.assertEqual(r['server_id'],str(SID));self.assertTrue(r['duration_matches_message']);self.assertTrue(r['transcript']['usable']);self.assertTrue(r['source_snapshot_stable'])
        self.assertEqual(hashlib.sha256(self.media.read_bytes()).hexdigest(),before);self.assertEqual(out.stat().st_mode&0o777,0o600)
    def test_wrong_chat_same_server_id_cannot_match(self):
        self.execute('UPDATE VoiceInfo SET chat_name_id=2');self.assertEqual(self.read()['status'],'voice_not_downloaded')
    def test_conflicting_audio_rejected(self):
        self.execute('INSERT INTO VoiceInfo VALUES(1,?,?)',(SID,SILK+b'x'));self.assertEqual(self.read()['status'],'voice_data_ambiguous')
    def test_bounded_duplicate_scan(self):
        for _ in range(4):self.execute('INSERT INTO VoiceInfo VALUES(1,?,?)',(SID,SILK))
        self.assertEqual(self.read()['status'],'voice_duplicate_limit')
    def test_identical_copies_are_deduplicated(self):
        self.execute('INSERT INTO VoiceInfo VALUES(1,?,?)',(SID,SILK));r=self.read();self.assertTrue(r['ready']);self.assertEqual(r['matching_copies'],2)
    def test_missing_download(self):
        self.execute('DELETE FROM VoiceInfo');self.assertEqual(self.read()['status'],'voice_not_downloaded')
    def test_unreadable_shard_prevents_partial_success(self):
        self.media.with_name('media_1.db').write_bytes(b'invalid');r=self.read();self.assertEqual(r['status'],'voice_media_shards_unreadable')
    def test_message_shard_gap_prevents_partial_success(self):
        bad=self.message.with_name('message_1.db');bad.write_bytes(b'invalid');self.db.message_dbs.append(bad);self.assertEqual(self.read()['status'],'voice_message_shards_unreadable')
    def test_account_identity_must_match(self):
        self.db.self_username='another';self.assertEqual(self.read()['status'],'voice_account_identity_mismatch')
    def test_mixed_account_paths_rejected(self):
        self.db.message_dbs.append(self.data_root/'other.db');self.assertEqual(self.read()['status'],'voice_account_paths_mixed')
    def test_redirected_media_rejected(self):
        self.media.with_name('media_1.db').symlink_to(self.media);self.assertEqual(self.read()['status'],'voice_media_path_redirected')
    def test_duration_mismatch_rejected(self):
        self.execute(f'UPDATE "{self.table}" SET message_content=? WHERE server_id=?',('<msg><voicemsg voicelength="5000"/></msg>',SID),self.message)
        self.assertEqual(self.read()['status'],'voice_duration_mismatch')
    def test_non_voice_message_rejected(self):
        self.execute(f'UPDATE "{self.table}" SET local_type=1 WHERE server_id=?',(SID,),self.message);self.assertEqual(self.read()['status'],'message_is_not_voice')
    def test_ambiguous_message_rejected(self):
        self.execute(f'INSERT INTO "{self.table}" VALUES(4,?,34,4,1,220,0,"","")',(SID,),self.message);self.assertEqual(self.read()['status'],'voice_message_ambiguous')
    def test_no_overwrite(self):
        p=self.data_root/'audio.wav';p.write_bytes(b'old');self.assertEqual(self.read(output=p)['status'],'voice_output_exists');self.assertEqual(p.read_bytes(),b'old')
    def test_no_source_export(self):
        p=self.account/'audio.wav';self.assertEqual(self.read(output=p)['status'],'voice_output_inside_wechat_source');self.assertFalse(p.exists())
    def test_unknown_codec(self):
        self.execute('UPDATE VoiceInfo SET voice_data=?',(b'0'*100,));self.assertEqual(self.read()['status'],'unsupported_voice_codec')
    def test_oversized_blob(self):
        self.execute('UPDATE VoiceInfo SET voice_data=zeroblob(4194305)');self.assertEqual(self.read()['status'],'invalid_voice_size')
    def test_quality_warnings_preserve_audio(self):
        a=good_asr();a['segments'][0]['avg_logprob']=-4
        original=self.fake_worker
        with mock.patch.object(self,'fake_worker',side_effect=lambda mode,*a_,**kw:a if mode=='transcribe' else original(mode,*a_,**kw)):
            r=self.read(transcribe=True)
        self.assertTrue(r['audio_ready']);self.assertFalse(r['transcript']['usable']);self.assertEqual(r['status'],'audio_ready_transcript_needs_review')
    def test_strict_mode_blocks_persistent_output(self):
        r=self.run_with_config(self.config,'--strict-read-only','voice','wxid_alice','--server-id',str(SID),'--output',str(self.data_root/'out.wav'),expected=1)
        self.assertEqual(r['error']['code'],'strict_read_only_local_write')
    @unittest.skipUnless(importlib.util.find_spec("pilk"), "Optional voice codec not installed")
    def test_actual_codec_and_cli(self):
        self.execute(f'UPDATE "{self.table}" SET message_content="<msg><voicemsg/></msg>" WHERE server_id=?',(SID,),self.message)
        out=self.data_root/'actual.wav';r=self.run_cli('voice','wxid_alice','--server-id',str(SID),'--output',str(out))['data']
        self.assertTrue(r['voice']['ready'],r);self.assertGreater(r['voice']['audio']['duration_seconds'],3);self.assertIn('freshness',r)
        with wave.open(str(out)) as f:self.assertEqual(f.getframerate(),24000)
    @unittest.skipUnless(os.environ.get("WECHAT_READER_TEST_ASR")=="1", "Explicit ASR model test not enabled")
    def test_actual_local_asr_cli(self):
        self.execute(f'UPDATE "{self.table}" SET message_content="<msg><voicemsg/></msg>" WHERE server_id=?',(SID,),self.message)
        r=self.run_cli('voice','wxid_alice','--server-id',str(SID),'--transcribe')['data']['voice']
        self.assertTrue(r['audio_ready'],r);self.assertTrue(r['transcript']['usable'],r)
        actual=''.join(c for c in r['transcript']['text'] if c.isalnum())
        self.assertEqual(actual,'这是语音读取测试明天下午三点开会请带上资料')
        self.assertTrue(r['transcript']['review_required'])
    def test_invalid_ids(self):
        for sid in ['0','-1','1.1','9223372036854775808','1;DROP']:
            r=v.read_voice(self.db,'wxid_alice',sid,reader.decode_message_content,reader.source_version);self.assertEqual(r['status'],'invalid_voice_server_id')

class FormatTest(unittest.TestCase):
    def test_output_case_alias_cannot_enter_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);account=root/'AccountMedia';account.mkdir();alias=root/'aCCOUNTmEDIA'
            if not alias.exists() or not alias.samefile(account):self.skipTest('Case-sensitive test filesystem')
            source=root/'fictional.wav';source.write_bytes(b'fictional');output=alias/'voice.wav'
            with self.assertRaisesRegex(v.VoiceError,'voice_output_inside_wechat_source'):v.export_exclusive(source,output,account)
            self.assertFalse(output.exists())
    def test_silk_framing_valid(self):self.assertGreater(v.validate_silk(SILK),1)
    def test_silk_truncation(self):
        with self.assertRaises(v.VoiceError):v.validate_silk(SILK[:-1])
    def test_stored_transcript_bounded_parser(self):
        inner=b'\x12\x06'+ '测试'.encode();raw=b'\x2a'+bytes([len(inner)])+inner
        self.assertEqual(v.stored_text(raw),'测试');self.assertIsNone(v.stored_text(raw[:-1]));self.assertIsNone(v.stored_text(b'\xff'*100))
    def test_bad_timing_and_nan(self):
        a=good_asr();a['segments'][0]['end']=100;self.assertFalse(v.assess_asr(a,1)['usable'])
        a=good_asr();a['segments'][0]['avg_logprob']=float('nan');self.assertFalse(v.assess_asr(a,1)['usable'])
    def test_silence_has_no_usable_text(self):self.assertFalse(v.assess_asr({'text':'','segments':[]},1)['usable'])
    def test_worker_offline_and_fixed_paths(self):
        with mock.patch.object(v.subprocess,'run',return_value=mock.Mock(stdout='{"ok":true}',returncode=0)) as run:
            v.worker('transcribe',Path('/tmp/test.wav'))
        args,kw=run.call_args;self.assertEqual(args[0][1],'-I');self.assertEqual(kw['env']['HF_HUB_OFFLINE'],'1');self.assertNotIn('PYTHONPATH',kw['env'])
    def test_timeout_is_explicit(self):
        with mock.patch.object(v.subprocess,'run',side_effect=v.subprocess.TimeoutExpired('x',1)):
            with self.assertRaisesRegex(v.VoiceError,'voice_processing_timeout'):v.worker('status')

class ComparisonTest(unittest.TestCase):
    def test_realistic_word_errors_request_review(self):
        t=v.assess_asr(good_asr(),1);t['text']='我感觉它不是在这个机队里应该在维修口里'
        v.compare_stored(t,'我感觉这几个应该不在机柜里它应该在音箱就近的维修口里')
        self.assertFalse(t['usable']);self.assertIn('differs_from_wechat_transcript',t['warnings'])
        self.assertFalse(t['wechat_comparison']['ground_truth_verified'])
    def test_punctuation_differences_are_not_content_errors(self):
        t=v.assess_asr(good_asr(),1);v.compare_stored(t,'这是测试！');self.assertTrue(t['usable']);self.assertEqual(t['wechat_comparison']['normalized_similarity'],1)
    def test_model_name_is_reported(self):
        a=good_asr();a['model']='whisper-large-v3';self.assertEqual(v.assess_asr(a,1)['model'],'whisper-large-v3')
    def test_changed_source_during_processing_is_visible(self):
        case=VoiceTest();case.setUp()
        try:
            ticks=iter([0,0,1,1])
            with mock.patch.object(v,'worker',side_effect=case.fake_worker):
                r=v.read_voice(case.db,'wxid_alice',str(SID),reader.decode_message_content,lambda p:next(ticks))
            self.assertTrue(r['ready']);self.assertFalse(r['source_snapshot_stable']);self.assertEqual(len(r['changed_sources']),2)
        finally:case.tearDown()
