import hashlib,json,os
from pathlib import Path
import subprocess,sys,tempfile,unittest
from unittest import mock
from test_images import images,png,encrypted

class DiskImageAccessTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.docs=self.root/'container'/'Documents';self.account=self.docs/'xwechat_files'/'demo_1234'
        self.storage=self.account/'db_storage';self.media=self.account/'msg';self.media.mkdir(parents=True)
        self.session=self.storage/'session'/'session.db';self.session.parent.mkdir(parents=True);self.session.touch()
        self.message=self.storage/'message'/'message_0.db';self.message.parent.mkdir();self.message.touch()
        self.profile=self.root/'reader.json'
        self.config={'self_username':'demo','session_db':str(self.session),'message_dbs':[str(self.message)],'resource_roots':[str(self.media)]}
        self.profile.write_text(json.dumps(self.config));self.roots=[self.media]
        self.stats=self.docs/'app_data'/'net'/'kvcomm';self.stats.mkdir(parents=True)
        (self.stats/'key_123456_test.statistic').write_bytes(b'contents must not be read')
        (self.stats/'key_654321_other.statistic').touch()
        self.key=hashlib.md5(b'123456demo').hexdigest()[:16].encode()
        self.samples=[]
        for i in range(2):
            p=self.media/f'sample{i}.dat';raw=encrypted(png(32+i,24),self.key)
            # test_images.encrypted uses 0x38; synthetic UIN 123456 has XOR 0x40.
            n=int.from_bytes(raw[10:14],'little');raw=raw[:-n]+bytes(x^0x38^0x40 for x in raw[-n:])
            p.write_bytes(raw);self.samples.append(p)
    def tearDown(self):self.temp.cleanup()
    def access(self,**kw):return images.image_access(self.config,self.roots,self.profile,self.samples,**kw)
    def test_disk_candidates_verified_without_writing(self):
        before={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.samples}
        r=self.access();self.assertTrue(r['ready'],r);self.assertEqual(r['candidate_count'],2)
        self.assertEqual(len(r['validated_samples']),2);self.assertFalse(r['material_written'])
        self.assertFalse(images.access_path(self.profile).exists())
        self.assertNotIn(self.key.decode(),json.dumps(r));self.assertNotIn('123456',json.dumps(r))
        self.assertEqual(before,{p:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.samples})
    def test_save_private_bound_material_and_ordinary_image_read(self):
        original=self.profile.read_bytes();r=self.access(save=True);self.assertTrue(r['material_written'],r)
        path=images.access_path(self.profile);self.assertEqual(path.stat().st_mode&0o777,0o600)
        cfg=images.profile_image_config(self.config,self.roots,self.profile)
        r=images.process_image(self.samples[0],self.roots,cfg,{})
        self.assertTrue(r['ready'],r);self.assertEqual(self.profile.read_bytes(),original)
        before=path.read_bytes();r=self.access(save=True)
        self.assertEqual(r['status'],'image_access_already_exists');self.assertEqual(path.read_bytes(),before)
    def test_cross_profile_sidecar_cannot_be_reused(self):
        self.access(save=True);p=images.access_path(self.profile);v=json.loads(p.read_text());v['account_binding']='wrong';p.write_text(json.dumps(v))
        cfg=images.profile_image_config(self.config,self.roots,self.profile)
        r=images.process_image(self.samples[0],self.roots,cfg,{})
        self.assertEqual(r['status'],'image_access_profile_mismatch')
    def test_duplicate_or_single_sample_rejected(self):
        self.samples=[self.samples[0]];self.assertEqual(self.access()['status'],'image_setup_requires_2_to_6_samples')
        self.samples*=2;self.assertEqual(self.access()['status'],'image_setup_requires_distinct_samples')
    def test_wrong_candidate_does_not_save(self):
        (self.stats/'key_123456_test.statistic').unlink();r=self.access(save=True)
        self.assertEqual(r['status'],'image_key_not_verified');self.assertFalse(images.access_path(self.profile).exists())
    def test_one_corrupt_sample_rejects_candidate(self):
        self.samples[1].write_bytes(encrypted(png(),b'wrongkey12345678'))
        r=self.access(save=True);self.assertEqual(r['status'],'image_key_not_verified')
    def test_account_identity_and_mixed_paths_rejected(self):
        self.config['self_username']='other';self.assertEqual(self.access()['status'],'image_account_identity_mismatch')
        self.config['self_username']='demo';self.config['message_dbs']=[str(self.root/'other.db')]
        self.assertEqual(self.access()['status'],'image_account_paths_mixed')
    def test_stats_symlink_and_saved_symlink_rejected(self):
        self.stats.rename(self.stats.with_name('renamed'));self.stats.symlink_to(self.stats.with_name('renamed'))
        self.assertEqual(self.access()['status'],'image_statistics_path_redirected')
        self.stats.unlink();self.stats.with_name('renamed').rename(self.stats)
        p=images.access_path(self.profile);p.symlink_to(self.root/'nonexistent')
        self.assertEqual(self.access(save=True)['status'],'image_access_already_exists')
    def test_statistic_contents_never_opened(self):
        original=Path.open
        def guarded(p,*a,**kw):
            if p.suffix=='.statistic':raise AssertionError('must read filenames only')
            return original(p,*a,**kw)
        with mock.patch.object(Path,'open',guarded):self.assertTrue(self.access()['ready'])
    def test_cli_setup_contract(self):
        cli=Path(__file__).resolve().parents[1]/'rion_wechat_reader.py'
        proc=subprocess.run([sys.executable,str(cli),'--config',str(self.profile),'image-setup','--sample',str(self.samples[0]),'--sample',str(self.samples[1]),'--save'],capture_output=True,text=True)
        r=json.loads(proc.stdout);self.assertTrue(r['ok'],r);self.assertTrue(r['data']['image_access']['material_written'],r)
    def test_strict_read_only_rejects_material_save_and_image_output(self):
        cli=Path(__file__).resolve().parents[1]/'rion_wechat_reader.py'
        for args in [
            ['image-setup','--sample',str(self.samples[0]),'--sample',str(self.samples[1]),'--save'],
            ['image',str(self.samples[0]),'--output',str(self.root/'out.png')],
        ]:
            p=subprocess.run([sys.executable,str(cli),'--config',str(self.profile),'--strict-read-only',*args],capture_output=True,text=True)
            r=json.loads(p.stdout);self.assertFalse(r['ok']);self.assertEqual(r['error']['code'],'strict_read_only_local_write')
        self.assertFalse(images.access_path(self.profile).exists());self.assertFalse((self.root/'out.png').exists())
    def test_discovery_reports_local_side_effects(self):
        cli=Path(__file__).resolve().parents[1]/'rion_wechat_reader.py'
        for name in ['image','image-setup']:
            p=subprocess.run([sys.executable,str(cli),'--config',str(self.profile),'tool-schema',name],capture_output=True,text=True)
            r=json.loads(p.stdout)['data']['tool'];self.assertFalse(r['read_only']);self.assertTrue(r['wechat_read_only'])


class WXGFTest(unittest.TestCase):
    def test_static_hevc_wrapping_pixel_decode_and_payload_digest(self):
        data=b'wxgf'+b'\x00'*24+(Path(__file__).parent/'fixtures'/'synthetic.hevc').read_bytes()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);srcdir=root/'src';srcdir.mkdir();p=srcdir/'test.dat';p.write_bytes(data)
            r=images.process_image(p,[srcdir],{},{},output=root/'out.png',expected_md5=hashlib.md5(data).hexdigest())
            self.assertTrue(r['ready'],r);self.assertTrue(r['wxgf_first_frame_only']);self.assertIsNone(r['frame_count'])
            self.assertTrue(r['resource_digest_verified']);self.assertEqual((r['width'],r['height']),(64,48))
    def test_malformed_wxgf_and_missing_converter_fail_closed(self):
        with self.assertRaises(images.ImageError):images.pixel_payload(b'wxgfxxx','wxgf')
        data=b'wxgf'+(Path(__file__).parent/'fixtures'/'synthetic.hevc').read_bytes()
        with mock.patch.object(images,'MEDIA_WORKER',Path('/nonexistent-media-worker')):
            with self.assertRaises(images.ImageError) as c:images.pixel_payload(data,'wxgf')
            self.assertEqual(c.exception.code,'wxgf_converter_required')
if __name__=='__main__':unittest.main()


def setUpModule():
    import platform
    if platform.system() != "Darwin":
        raise unittest.SkipTest("Apple ImageIO/Vision integration requires macOS")
