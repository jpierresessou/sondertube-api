from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import urllib.parse

app = FastAPI(title="SonderTube API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Options communes pour contourner la détection bot
BASE_OPTS = {
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'force_generic_extractor': False,
    'ignoreerrors': True,
    'no_color': True,
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'extractor_args': {
        'youtube': {
            'skip': ['hls', 'dash'],
            'player_skip': ['configs', 'webpage'],
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'fr,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate',
    }
}

@app.get("/")
def root():
    return {"status": "online", "app": "SonderTube", "version": "2.1.0"}

@app.get("/api/info")
def get_info(url: str = Query(...)):
    try:
        opts = BASE_OPTS.copy()
        opts['skip_download'] = True
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Recherche YouTube
            if url.startswith('ytsearch'):
                entries = info.get('entries', [])[:10]
                results = []
                for entry in entries:
                    if not entry: continue
                    formats = []
                    for f in entry.get('formats', []) or []:
                        if f.get('ext') == 'mp4' and f.get('height'):
                            formats.append({
                                'format_id': f['format_id'],
                                'quality': f'{f["height"]}p',
                                'type': 'video',
                                'label': f'🎬 {f["height"]}p MP4',
                                'filesize': f.get('filesize', 0)
                            })
                    # Audio
                    for f in entry.get('formats', []) or []:
                        if f.get('acodec') != 'none' and f.get('ext') == 'm4a':
                            formats.append({
                                'format_id': f['format_id'],
                                'quality': 'Audio',
                                'type': 'audio',
                                'label': '🎵 MP3 Audio',
                                'filesize': f.get('filesize', 0)
                            })
                            break
                    results.append({
                        'title': (entry.get('title') or 'Sans titre')[:100],
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', ''),
                        'webpage_url': entry.get('webpage_url', ''),
                        'url': entry.get('webpage_url', ''),
                        'formats': formats[:8]
                    })
                return {'success': True, 'entries': results, 'is_search': True}
            
            # Lien direct
            else:
                formats = []
                for f in info.get('formats', []) or []:
                    if f.get('ext') == 'mp4' and f.get('height'):
                        formats.append({
                            'format_id': f['format_id'],
                            'quality': f'{f["height"]}p',
                            'type': 'video',
                            'label': f'🎬 {f["height"]}p MP4',
                            'filesize': f.get('filesize', 0)
                        })
                for f in info.get('formats', []) or []:
                    if f.get('acodec') != 'none' and f.get('ext') == 'm4a':
                        formats.append({
                            'format_id': f['format_id'],
                            'quality': 'Audio',
                            'type': 'audio',
                            'label': '🎵 MP3 Audio',
                            'filesize': f.get('filesize', 0)
                        })
                        break
                
                return {
                    'success': True,
                    'title': (info.get('title') or 'Sans titre')[:100],
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', ''),
                    'formats': formats[:8],
                    'is_search': False
                }
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}

@app.get("/api/download")
def download(url: str = Query(...), format_id: str = Query(...), type: str = Query("video")):
    try:
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, '%(title)s.%(ext)s')
        opts = BASE_OPTS.copy()
        opts['format'] = format_id
        opts['outtmpl'] = out
        opts['merge_output_format'] = 'mp4'
        
        if type == 'audio':
            opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)
            if type == 'audio':
                fname = fname.rsplit('.', 1)[0] + '.mp3'
            
            def iterfile():
                with open(fname, 'rb') as f:
                    while chunk := f.read(1024*1024):
                        yield chunk
                try: os.remove(fname); os.rmdir(tmpdir)
                except: pass
            
            safe = urllib.parse.quote((info.get('title') or 'video')[:40])
            ext = 'mp3' if type == 'audio' else 'mp4'
            
            return StreamingResponse(
                iterfile(),
                media_type='application/octet-stream',
                headers={'Content-Disposition': f'attachment; filename="{safe}.{ext}"'}
            )
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}