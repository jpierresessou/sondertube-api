from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import yt_dlp
import tempfile
import os
import urllib.parse

app = FastAPI(title="SonderTube API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "online", "app": "SonderTube", "version": "2.0.0"}

@app.get("/api/info")
def get_info(url: str = Query(...)):
    """Récupère les infos d'une vidéo OU fait une recherche YouTube"""
    try:
        opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Détecter si c'est une recherche (ytsearch:)
            if url.startswith('ytsearch'):
                info = ydl.extract_info(url, download=False)
                entries = info.get('entries', [])[:10]
                
                results = []
                for entry in entries:
                    formats = []
                    video_formats = entry.get('formats', [])
                    seen = set()
                    
                    for f in video_formats:
                        if f.get('ext') == 'mp4' and f.get('height') and f['height'] not in seen:
                            seen.add(f['height'])
                            formats.append({
                                'format_id': f['format_id'],
                                'quality': f'{f["height"]}p',
                                'type': 'video',
                                'label': f'🎬 {f["height"]}p MP4',
                                'filesize': f.get('filesize', 0)
                            })
                    
                    if 'audio' not in seen:
                        for f in video_formats:
                            if f.get('acodec') != 'none' and f.get('ext') == 'm4a':
                                formats.append({
                                    'format_id': f['format_id'],
                                    'quality': 'Audio',
                                    'type': 'audio',
                                    'label': '🎵 MP3 Audio',
                                    'filesize': f.get('filesize', 0)
                                })
                                seen.add('audio')
                                break
                    
                    results.append({
                        'title': entry.get('title', 'Sans titre')[:100],
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', ''),
                        'webpage_url': entry.get('webpage_url', ''),
                        'url': entry.get('webpage_url', ''),
                        'formats': formats[:8]
                    })
                
                return {
                    'success': True,
                    'entries': results,
                    'is_search': True
                }
            
            else:
                # Comportement normal pour un lien direct
                info = ydl.extract_info(url, download=False)
                formats = []
                seen = set()
                
                for f in info.get('formats', []):
                    if f.get('ext') == 'mp4' and f.get('height') and f['height'] not in seen:
                        seen.add(f['height'])
                        formats.append({
                            'format_id': f['format_id'],
                            'quality': f'{f["height"]}p',
                            'type': 'video',
                            'label': f'🎬 {f["height"]}p MP4',
                            'filesize': f.get('filesize', 0)
                        })
                
                if 'audio' not in seen:
                    for f in info.get('formats', []):
                        if f.get('acodec') != 'none' and f.get('ext') == 'm4a':
                            formats.append({
                                'format_id': f['format_id'],
                                'quality': 'Audio',
                                'type': 'audio',
                                'label': '🎵 MP3 Audio',
                                'filesize': f.get('filesize', 0)
                            })
                            seen.add('audio')
                            break
                
                return {
                    'success': True,
                    'title': info.get('title', 'Sans titre')[:100],
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
    """Télécharge et stream le fichier"""
    try:
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, '%(title)s.%(ext)s')
        
        opts = {
            'format': format_id,
            'outtmpl': out,
            'quiet': True,
            'merge_output_format': 'mp4',
            'no_warnings': True,
        }
        
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
                    while chunk := f.read(1024 * 1024):
                        yield chunk
                try:
                    os.remove(fname)
                    os.rmdir(tmpdir)
                except:
                    pass
            
            safe = urllib.parse.quote(info.get('title', 'video')[:40])
            ext = 'mp3' if type == 'audio' else 'mp4'
            
            return StreamingResponse(
                iterfile(),
                media_type='application/octet-stream',
                headers={
                    'Content-Disposition': f'attachment; filename="{safe}.{ext}"'
                }
            )
            
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}