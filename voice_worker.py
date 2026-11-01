"""Fixed local codec/ASR worker; no DB/key access, network, or arbitrary command hooks."""
from pathlib import Path
import contextlib,json,os,sys,subprocess,wave,ctypes

sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime_paths import model_path
MODEL=model_path('turbo')
MODELS={name:model_path(name) for name in ('turbo','large-v3')}
def cached(model):
    return (model/'config.json').is_file() and any((model/name).is_file() for name in ['weights.safetensors','weights.npz'])
def finish(data):
    print(json.dumps(data,ensure_ascii=False,allow_nan=False));return 0

def main():
    os.umask(0o077)
    os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_DATASETS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1')
    mode=sys.argv[1]
    if mode=='status':
        import importlib.metadata as m
        versions={}
        for name in ['pilk','mlx-whisper','mlx']:
            try:versions[name]=m.version(name)
            except m.PackageNotFoundError:versions[name]=None
        return finish({'ok':True,'packages':versions,'model_cached':cached(MODEL),'model':'whisper-large-v3-turbo','models_cached':{name:cached(path) for name,path in MODELS.items()},'ffmpeg_available':bool(__import__('importlib').util.find_spec('av'))})
    src=Path(sys.argv[2]);dest=Path(sys.argv[3]) if mode=='decode' else None
    if mode=='decode':
        import pilk
        pcm=dest.with_suffix('.pcm')
        # The codec uses C stdio; Python redirect_stdout alone cannot isolate it.
        log=dest.with_suffix('.codec.log')
        stdout_fd=os.dup(1);stderr_fd=os.dup(2)
        try:
            with log.open('wb') as stream:
                sys.stdout.flush();sys.stderr.flush();ctypes.CDLL(None).fflush(None)
                os.dup2(stream.fileno(),1);os.dup2(stream.fileno(),2)
                pilk.decode(str(src),str(pcm),pcm_rate=24000)
                ctypes.CDLL(None).fflush(None)
        finally:
            os.dup2(stdout_fd,1);os.dup2(stderr_fd,2);os.close(stdout_fd);os.close(stderr_fd)
        diagnostic=log.read_text(errors='replace');log.unlink()
        if 'returned -' in diagnostic or 'error' in diagnostic.lower():raise ValueError('codec_decode_failed')
        size=pcm.stat().st_size
        if not 0<size<=180*48000 or size%2:raise ValueError('invalid_pcm')
        data=pcm.read_bytes()
        with wave.open(str(dest),'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(24000);f.writeframes(data)
        pcm.unlink()
        import array,math
        values=array.array('h',data);rms=math.sqrt(sum(float(x)*x for x in values)/len(values))/32768
        return finish({'ok':True,'duration_seconds':size/48000,'sample_rate':24000,'channels':1,'rms':rms,'decoded_samples':len(values)})
    if mode!='transcribe':raise ValueError('invalid_mode')
    model_name=sys.argv[4] if len(sys.argv)>4 else 'turbo'
    if model_name not in MODELS:raise ValueError('invalid_model')
    model=MODELS[model_name]
    if not cached(model):
        return finish({'ok':False,'code':'voice_model_unavailable'})
    language=sys.argv[3]
    if language not in ['auto','zh','en']:raise ValueError('invalid_language')
    # Input is the private WAV produced by decode, not an untrusted external URL.
    import numpy as np
    import av
    chunks=[]
    with av.open(str(src)) as container:
        resampler=av.AudioResampler(format='s16',layout='mono',rate=16000)
        total=0
        for frame in container.decode(audio=0):
            for out in resampler.resample(frame):
                total+=out.samples
                if total>180*16000:raise ValueError('audio_duration_limit')
                chunks.append(out.to_ndarray().reshape(-1))
        for out in resampler.resample(None):
            total+=out.samples
            if total>180*16000:raise ValueError('audio_duration_limit')
            chunks.append(out.to_ndarray().reshape(-1))
    if not chunks:raise ValueError('empty_audio')
    audio=np.concatenate(chunks).astype(np.float32)/32768.0
    if float(np.sqrt(np.mean(audio*audio)))<0.001:
        return finish({'ok':True,'text':'','segments':[],'language':language,'no_speech':True})
    with contextlib.redirect_stdout(sys.stderr):
        import mlx_whisper
        r=mlx_whisper.transcribe(audio,path_or_hf_repo=str(model),language=None if language=='auto' else language,
             temperature=0,condition_on_previous_text=False,verbose=None)
    segments=[{k:s.get(k) for k in ['start','end','text','avg_logprob','no_speech_prob','compression_ratio']} for s in r.get('segments',[])]
    return finish({'ok':True,'text':r.get('text',''),'segments':segments,'language':r.get('language',language),'model':'whisper-large-v3-turbo' if model_name=='turbo' else 'whisper-large-v3'})
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as exc:
        finish({'ok':False,'code':'voice_worker_failed','error_type':type(exc).__name__})
        raise SystemExit(1)
