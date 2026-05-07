from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import urllib.parse

app = FastAPI(title="SonderTube API")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"status": "online", "app": "SonderTube"}

@app.get("/api/info")
def get_info(url: str = Query(...)):
    try:
        opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            for f in info.get('formats', []):
                if f.get('ext') == 'mp4' and f.get('height'):
                    formats.append({'format_id': f['format_id'], 'quality': f'{f["height"]}p', 'type': 'video', 'label': f'🎬 {f["height"]}p MP4'})
                if f.get('acodec') != 'none' and f.get('ext') == 'm4a' and not any(x['type']=='audio' for x in formats):
                    formats.append({'format_id': f['format_id'], 'quality': 'Audio', 'type': 'audio', 'label': '🎵 MP3 Audio'})
            return {'success': True, 'title': info.get('title','')[:100], 'duration': info.get('duration',0), 'thumbnail': info.get('thumbnail',''), 'uploader': info.get('uploader',''), 'formats': formats[:8]}
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}

@app.get("/api/download")
def download(url: str = Query(...), format_id: str = Query(...), type: str = Query("video")):
    try:
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, '%(title)s.%(ext)s')
        opts = {'format': format_id, 'outtmpl': out, 'quiet': True, 'merge_output_format': 'mp4'}
        if type == 'audio':
            opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)
            if type == 'audio': fname = fname.rsplit('.', 1)[0] + '.mp3'
            def iterfile():
                with open(fname, 'rb') as f:
                    while chunk := f.read(1024*1024): yield chunk
                try: os.remove(fname); os.rmdir(tmpdir)
                except: pass
            safe = urllib.parse.quote(info.get('title','video')[:40])
            return StreamingResponse(iterfile(), media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename="{safe}.{"mp3" if type=="audio" else "mp4"}"'})
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}
