"""Exact-account voice reads; bounded local SILK decoding and optional offline ASR."""
from pathlib import Path
import difflib,hashlib,json,math,os,re,struct,subprocess,tempfile,unicodedata
import xml.etree.ElementTree as ET

import sys
ASR_PYTHON=Path(sys.executable)
WORKER=Path(__file__).resolve().with_name('voice_worker.py')
MAX_BYTES=4*1024*1024
class VoiceError(Exception):
    def __init__(self,code):self.code=code;super().__init__(code)

def account_root(db):
    session=db.session_db.resolve() if db.session_db else None
    storage=next((p for p in session.parents if p.name=='db_storage'),None) if session else None
    if not storage or storage.parent.parent.name!='xwechat_files':raise VoiceError('voice_account_layout_unverified')
    account=storage.parent
    if not db.self_username or account.name.rsplit('_',1)[0]!=db.self_username:raise VoiceError('voice_account_identity_mismatch')
    if not db.message_dbs or not all(p.expanduser().resolve().is_relative_to(storage) for p in db.message_dbs):raise VoiceError('voice_account_paths_mixed')
    return account,storage

def media_inventory(db):
    account,storage=account_root(db);folder=storage/'message'
    if folder.resolve()!=folder:raise VoiceError('voice_media_path_redirected')
    paths=sorted(p for p in folder.glob('media_*.db') if re.fullmatch(r'media_\d+\.db',p.name))
    if len(paths)>64:raise VoiceError('voice_media_shard_limit')
    if any(p.is_symlink() or p.resolve().parent!=folder for p in paths):raise VoiceError('voice_media_path_redirected')
    return paths

def worker(mode,source=None,target=None,language='zh',model='turbo'):
    if not ASR_PYTHON.is_file() or not WORKER.is_file():raise VoiceError('voice_runtime_unavailable')
    cmd=[str(ASR_PYTHON),'-I',str(WORKER),mode]
    if mode=='decode':cmd += [str(source),str(target)]
    elif mode=='transcribe':cmd += [str(source),language,model]
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTHON','HF_','TRANSFORMERS_'))}
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=180 if mode=='transcribe' else 30,env=env)
        value=json.loads(p.stdout)
        if p.returncode or not value.get('ok'):raise VoiceError(value.get('code','voice_worker_failed'))
        return value
    except subprocess.TimeoutExpired:raise VoiceError('voice_processing_timeout') from None
    except (ValueError,OSError):raise VoiceError('voice_runtime_failed') from None

def validate_silk(data):
    if not 10<len(data)<=MAX_BYTES:raise VoiceError('invalid_voice_size')
    offset=10 if data.startswith(b'\x02#!SILK_V3') else 9 if data.startswith(b'#!SILK_V3') else 0
    if not offset:raise VoiceError('unsupported_voice_codec')
    packets=0
    while offset<len(data):
        if offset+2>len(data):raise VoiceError('truncated_voice_packet')
        size=struct.unpack_from('<h',data,offset)[0];offset+=2
        if size==-1 and offset==len(data):break
        if size<=0 or offset+size>len(data):raise VoiceError('truncated_voice_packet')
        offset+=size;packets+=1
        if packets>9000:raise VoiceError('voice_duration_limit')
    if not packets:raise VoiceError('empty_voice_audio')
    return packets

def protobuf_fields(raw):
    if len(raw)>1024*1024:raise ValueError('oversized_protobuf')
    pos=0;out={}
    def integer():
        nonlocal pos
        value=0
        for shift in range(0,70,7):
            if pos>=len(raw):raise ValueError('truncated')
            b=raw[pos];pos+=1;value|=(b&127)<<shift
            if not b&128:return value
        raise ValueError('varint')
    while pos<len(raw):
        tag=integer();field=tag>>3;wire=tag&7
        if not field:raise ValueError('field')
        if wire==0:value=integer()
        elif wire in [1,5]:
            n=8 if wire==1 else 4;value=raw[pos:pos+n];pos+=n
            if len(value)!=n:raise ValueError('truncated')
        elif wire==2:
            n=integer();value=raw[pos:pos+n];pos+=n
            if len(value)!=n:raise ValueError('truncated')
        else:raise ValueError('wire')
        out.setdefault(field,[]).append(value)
        if sum(map(len,out.values()))>10000:raise ValueError('fields')
    return out

def stored_text(raw):
    try:
        outer=protobuf_fields(raw or b'');inner=protobuf_fields(outer[5][0]);text=inner[2][0].decode('utf-8')
        return text if 0<len(text.strip())<=20000 else None
    except (ValueError,TypeError,KeyError,IndexError,AttributeError):return None

def assess_asr(value,duration):
    text=str(value.get('text') or '').strip();segments=value.get('segments',[]);warnings=[]
    if not text:return {'status':'no_speech_detected','text':'','segments':[],'usable':False,'review_required':True}
    if len(text)>20000 or not segments or len(segments)>1000:warnings.append('invalid_segment_count_or_length')
    last_start=-1;phrases=[]
    for s in segments:
        start,end=s.get('start'),s.get('end')
        nums=[s.get(k) for k in ['start','end','avg_logprob','no_speech_prob','compression_ratio']]
        if any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in nums):warnings.append('invalid_segment_metrics');continue
        if not (0<=start<end<=duration+0.6) or start<last_start:warnings.append('invalid_segment_timing')
        last_start=start
        if s['avg_logprob'] < -1.2 or s['no_speech_prob']>.6 or s['compression_ratio']>2.4:warnings.append('low_confidence_or_repetition')
        compact=''.join(c for c in str(s.get('text') or '') if c.isalnum());phrases.append(compact)
        if len(compact)>12 and len(set(compact))<=2:warnings.append('repetitive_text')
    if any(phrases[i] and len(set(phrases[i:i+4]))==1 for i in range(max(0,len(phrases)-3))):warnings.append('repeated_segments')
    return {'status':'needs_review' if warnings else 'ready','text':text,'segments':segments,'language':value.get('language'),
            'usable':not warnings,'review_required':True,'warnings':sorted(set(warnings)),
            'source':'local_mlx_whisper','model':value.get('model','whisper-large-v3-turbo'),'machine_transcript':True}

def compare_stored(transcript,stored):
    """A second machine transcript is corroboration, never ground truth."""
    if not stored or not transcript.get('text'):return
    def normalize(text):return ''.join(c for c in unicodedata.normalize('NFKC',text).casefold() if c.isalnum())
    local=normalize(transcript['text']);reference=normalize(stored)
    ratio=difflib.SequenceMatcher(None,local[:2048],reference[:2048],autojunk=False).ratio()
    uncertain=ratio<0.9 or max(len(local),len(reference))>2048
    transcript['wechat_comparison']={'normalized_similarity':round(ratio,4),'status':'differs' if uncertain else 'similar','reference_is_machine_transcript':True,'ground_truth_verified':False}
    if uncertain:
        transcript['warnings']=sorted(set(transcript.get('warnings',[])+['differs_from_wechat_transcript']))
        transcript.update(status='needs_review',usable=False)

def resolve_message(db,username,sid,decode_content):
    table='Msg_'+hashlib.md5(username.encode()).hexdigest();found=[];gaps=[]
    for path in db.message_dbs:
        try:
            with db.connect(path) as conn:
                if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone():continue
                cols={str(r[1]) for r in conn.execute(f'PRAGMA table_info("{table}")')}
                if not {'server_id','local_type','local_id','create_time'}<=cols:raise VoiceError('incompatible_voice_message_schema')
                fields=['server_id','local_type','local_id','create_time']+[x for x in ['message_content','compress_content','WCDB_CT_message_content','packed_info_data'] if x in cols]
                rows=conn.execute('SELECT '+','.join('"'+x+'"' for x in fields)+f' FROM "{table}" WHERE server_id=? LIMIT 3',(sid,)).fetchall()
                for row in rows:found.append(dict(row))
        except Exception:gaps.append(path.name)
    if gaps:raise VoiceError('voice_message_shards_unreadable')
    if not found:raise VoiceError('voice_message_not_found')
    if len(found)!=1:raise VoiceError('voice_message_ambiguous')
    row=found[0]
    if (int(row['local_type']) & 0xffffffff) != 34:raise VoiceError('message_is_not_voice')
    content=decode_content(row);declared=None
    try:
        xml=content[content.index('<'):]
        if len(xml)>1024*1024 or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():raise ValueError()
        node=ET.fromstring(xml).find('.//voicemsg');declared=int(node.get('voicelength')) if node is not None else None
        if declared is not None and not 0<declared<=180000:raise VoiceError('voice_duration_limit')
    except (ValueError,ET.ParseError,TypeError):declared=None
    return row,declared,stored_text(row.get('packed_info_data'))

def voice_status(db):
    result={'ready':False,'status':'unverified','media_shards':[],'key_acquisition':False}
    try:
        paths=media_inventory(db);gaps=[]
        for p in paths:
            try:
                with db.connect(p) as conn:
                    cols={str(r[1]) for r in conn.execute('PRAGMA table_info("VoiceInfo")')}
                    names={str(r[1]) for r in conn.execute('PRAGMA table_info("Name2Id")')}
                    valid={'svr_id','chat_name_id','voice_data'}<=cols and 'user_name' in names
                    if not valid:raise VoiceError('incompatible_voice_schema')
                result['media_shards'].append({'file':p.name,'readable':True})
            except Exception:gaps.append(p.name);result['media_shards'].append({'file':p.name,'readable':False})
        runtime=worker('status');result['runtime']=runtime
        result.update(ready=bool(paths) and not gaps and all(runtime['packages'].values()) and runtime['model_cached'] and runtime.get('ffmpeg_available',False),
                      status='ready' if paths and not gaps and all(runtime['packages'].values()) and runtime['model_cached'] and runtime.get('ffmpeg_available',False) else 'voice_not_ready')
    except VoiceError as e:result['status']=e.code
    return result

def export_exclusive(source,dest,account):
    dest=dest.expanduser().absolute();parent=dest.parent.resolve()
    if dest.suffix.lower()!='.wav':raise VoiceError('voice_output_must_be_wav')
    if not parent.is_dir():raise VoiceError('voice_output_directory_missing')
    from runtime_paths import path_within
    if path_within(account,parent):raise VoiceError('voice_output_inside_wechat_source')
    with tempfile.TemporaryDirectory(prefix='.voice-export-',dir=parent) as temp:
        stage=Path(temp)/'audio.wav';stage.write_bytes(source.read_bytes());stage.chmod(0o600)
        try:os.link(stage,parent/dest.name)
        except FileExistsError:raise VoiceError('voice_output_exists') from None
    return str(parent/dest.name)

def read_voice(db,username,server_id,decode_content,source_version,output=None,transcribe=False,language='zh',model='turbo'):
    result={'ready':False,'status':'unverified','source_modified':False,'network_used':False,'key_acquisition':False,
            'audio_ready':False,'transcript':None}
    try:
        if not re.fullmatch(r'[1-9][0-9]{0,18}',str(server_id)) or int(server_id)>2**63-1:raise VoiceError('invalid_voice_server_id')
        sid=int(server_id);account,_=account_root(db);paths=media_inventory(db)
        if not paths:raise VoiceError('voice_media_not_configured')
        versions={p:source_version(p) for p in [*db.message_dbs,*paths]}
        row,declared,stored=resolve_message(db,username,sid,decode_content)
        result.update(server_id=str(sid),local_id=row['local_id'],declared_ms=declared,
                      wechat_transcript={'text':stored,'source':'wechat_stored','machine_transcript':True} if stored else None)
        found=[];gaps=[]
        for p in paths:
            try:
                with db.connect(p) as conn:
                    rows=conn.execute('SELECT length(v.voice_data) AS byte_length, CASE WHEN length(v.voice_data)<=4194304 THEN v.voice_data END AS voice_data FROM VoiceInfo v JOIN Name2Id n ON n.rowid=v.chat_name_id WHERE n.user_name=? AND v.svr_id=? LIMIT 5',(username,sid)).fetchall()
                if len(rows)>=5:raise VoiceError('voice_duplicate_limit')
                for x in rows:
                    if (x['byte_length'] or 0)>MAX_BYTES:raise VoiceError('invalid_voice_size')
                    if x['voice_data']:found.append((p.name,bytes(x['voice_data'])))
            except VoiceError:raise
            except Exception:gaps.append(p.name)
        result['media_shards_checked']=[p.name for p in paths];result['unreadable_media_shards']=gaps
        if gaps:raise VoiceError('voice_media_shards_unreadable')
        if not found:raise VoiceError('voice_not_downloaded')
        digests={hashlib.sha256(data).hexdigest() for _,data in found}
        if len(digests)!=1:raise VoiceError('voice_data_ambiguous')
        data=found[0][1];packets=validate_silk(data)
        result.update(source_sha256=next(iter(digests)),source_bytes=len(data),silk_packets=packets,
                      matching_copies=len(found),matched_media_shards=sorted({n for n,_ in found}))
        with tempfile.TemporaryDirectory(prefix='rion-voice-') as temp:
            root=Path(temp);root.chmod(0o700);src=root/'source.silk';wav=root/'audio.wav';src.write_bytes(data);src.chmod(0o600)
            audio=worker('decode',src,wav);wav.chmod(0o600)
            result['audio']={k:v for k,v in audio.items() if k!='ok'}
            duration=audio['duration_seconds'];match=declared is not None and abs(duration-declared/1000)<=0.6
            result['duration_matches_message']=match if declared is not None else None
            if declared is not None and not match:raise VoiceError('voice_duration_mismatch')
            result.update(audio_ready=True,ready=True,status='ready')
            if output:result['output_path']=export_exclusive(wav,output,account)
            if transcribe:
                value=worker('transcribe',wav,language=language,model=model);result['transcript']=assess_asr(value,duration)
                compare_stored(result['transcript'],stored)
                if not result['transcript']['usable']:result['status']='audio_ready_transcript_needs_review'
        changed=[p.name for p,v in versions.items() if source_version(p)!=v]
        result['changed_sources']=changed;result['source_snapshot_stable']=not changed
        if sorted(p.name for p in media_inventory(db))!=sorted(p.name for p in paths):
            result.update(status='voice_media_inventory_changed',ready=False)
    except VoiceError as e:result.update(status=e.code,ready=False)
    except (OSError,ValueError,TypeError):result.update(status='voice_io_failed',ready=False)
    return result
