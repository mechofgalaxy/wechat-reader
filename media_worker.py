"""Bounded static HEVC -> PNG worker. Receives bytes only, never URLs or paths."""
import io
import sys

def main():
    try:
        import av
        import PIL.Image
    except ImportError:
        return 3
    data=sys.stdin.buffer.read(64*1024*1024+1)
    if not data or len(data)>64*1024*1024:return 2
    try:
        with av.open(io.BytesIO(data),format='hevc',options={'probesize':'1048576','analyzeduration':'1000000'}) as container:
            if len(container.streams.video)!=1:return 2
            stream=container.streams.video[0]
            w,h=stream.width,stream.height
            if not 0<w<=50000 or not 0<h<=50000 or w*h>40000000:return 2
            stream.thread_type='NONE'
            for frame in container.decode(stream):
                if frame.width!=w or frame.height!=h:return 2
                out=io.BytesIO();frame.to_image().save(out,format='PNG')
                value=out.getvalue()
                if len(value)>64*1024*1024:return 2
                sys.stdout.buffer.write(value)
                return 0
    except Exception:
        return 2
    return 2

if __name__=='__main__':raise SystemExit(main())
