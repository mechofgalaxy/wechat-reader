import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib
import test_reader_upstream as fixtures

spec=importlib.util.spec_from_file_location('images_under_test',fixtures.ROOT/'wechat_images.py')
images=importlib.util.module_from_spec(spec);spec.loader.exec_module(images)

def png(width=32,height=24):
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    pixels=b''.join(b'\x00'+b''.join(bytes([x*7%256,y*9%256,120]) for x in range(width)) for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')

def encrypted(data,key,version=2,prefix=64,tail=32):
    prefix=min(prefix,len(data));tail=min(tail,len(data)-prefix)
    pad=16-prefix%16
    first=images.aes_ecb(data[:prefix]+bytes([pad])*pad,key,decrypt=False)
    mid=data[prefix:len(data)-tail] if tail else data[prefix:]
    end=bytes(v^0x38 for v in data[-tail:]) if tail else b''
    return (images.V2 if version==2 else images.V1)+struct.pack('<II',prefix,tail)+b'\x01'+first+mid+end

class ImageUnitTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.source=self.root/'media';self.source.mkdir()
        self.input=self.source/'image_t.dat';self.input.write_bytes(png())
        self.output=self.root/'result.png'
    def tearDown(self):self.temp.cleanup()
    def process(self,**kw):
        return images.process_image(self.input,[self.source],kw.pop('config',{}),{},**kw)
    def test_plain_image_full_pixel_decode_and_export(self):
        before=hashlib.sha256(self.input.read_bytes()).hexdigest()
        result=self.process(output=self.output)
        self.assertTrue(result['ready'],result)
        self.assertEqual((result['width'],result['height']),(32,24))
        self.assertEqual(result['variant'],'thumbnail')
        self.assertTrue(result['pixel_decode_verified'])
        self.assertEqual(self.output.stat().st_mode&0o777,0o600)
        self.assertEqual(images.image_format(self.output.read_bytes()),'png')
        self.assertEqual(hashlib.sha256(self.input.read_bytes()).hexdigest(),before)
    def test_output_case_alias_cannot_enter_source(self):
        alias=self.source.with_name(self.source.name.upper())
        if not alias.exists() or not alias.samefile(self.source):self.skipTest('Case-sensitive test filesystem')
        output=alias/'case-output.png';result=self.process(output=output)
        self.assertEqual(result['status'],'output_inside_wechat_source');self.assertFalse(output.exists())
    def test_xor_image_roundtrip_and_pixel_decode(self):
        original=png();self.input.write_bytes(bytes(v^0xa7 for v in original))
        result=self.process(output=self.output,expected_md5=hashlib.md5(original).hexdigest())
        self.assertTrue(result['ready'],result)
        self.assertEqual(result['encoding'],'wechat_xor')
        self.assertTrue(result['resource_digest_verified'])
    def test_v1_known_format_key_and_explicit_tail(self):
        original=png();self.input.write_bytes(encrypted(original,b'cfcd208495d565ef',1))
        result=self.process(config={'image_xor_key':0x38},output=self.output,expected_md5=hashlib.md5(original).hexdigest())
        self.assertTrue(result['ready'],result)
        self.assertEqual(result['encoding'],'wechat_v1')
    def test_v2_explicit_material_full_roundtrip(self):
        original=png();key=b'1234567890abcdef';self.input.write_bytes(encrypted(original,key))
        result=self.process(config={'image_aes_key':key.decode(),'image_xor_key':0x38},output=self.output,expected_md5=hashlib.md5(original).hexdigest())
        self.assertTrue(result['ready'],result)
        self.assertEqual(result['encoding'],'wechat_v2')
        self.assertNotIn(key.decode(),json.dumps(result))
    def test_v2_missing_key_returns_precise_state_no_output(self):
        self.input.write_bytes(encrypted(png(),b'1234567890abcdef'))
        result=self.process(output=self.output)
        self.assertEqual(result['status'],'image_key_required')
        self.assertFalse(result['ready']);self.assertFalse(self.output.exists())
    def test_missing_xor_is_not_guessed_for_png(self):
        self.input.write_bytes(encrypted(png(),b'1234567890abcdef'))
        result=self.process(config={'image_aes_key':'1234567890abcdef'})
        self.assertEqual(result['status'],'image_xor_key_required')
    def test_wrong_key_no_output_or_sensitive_error(self):
        self.input.write_bytes(encrypted(png(),b'1234567890abcdef'))
        result=self.process(config={'image_aes_key':'wrong-secret-key','image_xor_key':0x38},output=self.output)
        self.assertEqual(result['status'],'image_key_or_data_invalid')
        self.assertNotIn('wrong-secret-key',json.dumps(result));self.assertFalse(self.output.exists())
    def test_nist_aes_known_answer(self):
        key=bytes.fromhex('000102030405060708090a0b0c0d0e0f');plain=bytes.fromhex('00112233445566778899aabbccddeeff')
        encrypted_block=bytes.fromhex('69c4e0d86a7b0430d8cdb78070b4c55a')
        self.assertEqual(images.aes_ecb(plain,key,False),encrypted_block)
        self.assertEqual(images.aes_ecb(encrypted_block,key),plain)
    def test_invalid_encrypted_lengths_and_padding_rejected(self):
        for data in [images.V2+b'\x00',images.V2+struct.pack('<II',2**32-1,0)+b'\x01',images.V2+struct.pack('<II',0,10000)+b'\x01'+b'x']:
            with self.subTest(data=data):
                with self.assertRaises(images.ImageError) as c:images.decode_bytes(data,b'1234567890abcdef',0x38)
                self.assertEqual(c.exception.code,'invalid_encrypted_layout')
        with self.assertRaises(images.ImageError):images.unpad(b'abc\x03\x04\x03')
    def test_truncated_png_not_accepted_from_header_only(self):
        self.input.write_bytes(png()[:40])
        result=self.process(output=self.output)
        self.assertFalse(result['ready']);self.assertFalse(self.output.exists())
    def test_digest_mismatch_leaves_no_output(self):
        result=self.process(output=self.output,expected_md5='0'*32)
        self.assertEqual(result['status'],'image_digest_mismatch');self.assertFalse(self.output.exists())
    def test_no_overwrite_and_no_output_to_wechat(self):
        self.output.write_bytes(b'existing')
        result=self.process(output=self.output)
        self.assertEqual(result['status'],'output_exists');self.assertEqual(self.output.read_bytes(),b'existing')
        result=self.process(output=self.source/'new.png')
        self.assertEqual(result['status'],'output_inside_wechat_source')
    def test_other_account_path_and_symlink_escape_rejected(self):
        outside=self.root/'other.png';outside.write_bytes(png())
        r=images.process_image(outside,[self.source],{},{});self.assertEqual(r['status'],'image_outside_selected_profile')
        link=self.source/'escape.dat';link.symlink_to(outside)
        r=images.process_image(link,[self.source],{},{});self.assertEqual(r['status'],'image_outside_selected_profile')
    def test_not_downloaded_and_oversize_are_explicit(self):
        self.input.unlink();self.assertEqual(self.process()['status'],'image_not_downloaded')
        with self.input.open('wb') as f:f.truncate(images.MAX_BYTES+1)
        self.assertEqual(self.process()['status'],'invalid_image_size')
    def test_key_file_permissions_and_hex_format(self):
        p=self.root/'image-access.json';p.write_text(json.dumps({'image_aes_key':'hex:'+b'1234567890abcdef'.hex(),'image_xor_key':0x38}));p.chmod(0o644)
        with self.assertRaises(images.ImageError) as c:images.key_material({'image_key_file':str(p)},{})
        self.assertEqual(c.exception.code,'unsafe_image_key_file')
        p.chmod(0o600);key,xor=images.key_material({'image_key_file':str(p)},{});self.assertEqual(key,b'1234567890abcdef');self.assertEqual(xor,0x38)
    def test_unknown_codec_and_runtime_missing_not_ready(self):
        self.input.write_bytes(b'wxgf'+b'\x00'*40)
        self.assertEqual(self.process()['status'],'wxgf_bitstream_not_found')
        self.input.write_bytes(png())
        with mock.patch.object(images,'NATIVE',self.root/'absent'):
            self.assertEqual(self.process()['status'],'image_runtime_unavailable')
    def test_local_ocr_fixture(self):
        fixture=Path(__file__).parent/'fixtures'/'ocr.png'
        self.assertTrue(fixture.exists(),'synthetic OCR fixture must be generated before tests')
        self.input.write_bytes(fixture.read_bytes())
        result=self.process(ocr=True,output=self.output)
        self.assertTrue(result['ready'],result)
        self.assertEqual(result['ocr']['status'],'ok',result)
        joined=' '.join(line['text'] for line in result['ocr']['lines'])
        self.assertIn('OCR TEST 2026',joined)
        self.assertIn('图片',joined)
    def test_v2_jpeg_tail_inference_and_full_digest(self):
        original=(Path(__file__).parent/'fixtures'/'ocr.jpg').read_bytes()
        self.input.write_bytes(encrypted(original,b'1234567890abcdef'))
        result=self.process(config={'image_aes_key':'1234567890abcdef'},expected_md5=hashlib.md5(original).hexdigest())
        self.assertTrue(result['ready'],result)
        self.assertEqual(result['format'],'jpeg')
        self.assertTrue(result['resource_digest_verified'])
    def test_inspection_without_output_writes_no_file(self):
        before=set(self.root.rglob('*'));result=self.process()
        self.assertTrue(result['ready'],result);self.assertEqual(before,set(self.root.rglob('*')))

class ImageCLITest(unittest.TestCase):
    setUp=fixtures.ReaderContractTest.setUp
    tearDown=fixtures.ReaderContractTest.tearDown
    _build_fixtures=fixtures.ReaderContractTest._build_fixtures
    run_cli=fixtures.ReaderContractTest.run_cli
    def test_existing_entrypoint_contract_and_image_output(self):
        source=self.resource_root/'sample_h.dat';source.write_bytes(png())
        output=self.config.parent/'preview.png'
        d=self.run_cli('image',str(source),'--output',str(output))['data']
        self.assertTrue(d['image']['ready'],d)
        self.assertEqual(d['image']['variant'],'high_definition')
        self.assertIn('freshness',d)
        self.assertEqual(self.run_cli('tool-schema','image')['data']['command']['name'],'image')
    def test_missing_image_command_remains_json(self):
        d=self.run_cli('image',str(self.resource_root/'absent.dat'))['data']
        self.assertEqual(d['image']['status'],'image_not_downloaded')

if __name__=='__main__':unittest.main()


def setUpModule():
    import platform
    if platform.system() != "Darwin":
        raise unittest.SkipTest("Apple ImageIO/Vision integration requires macOS")
