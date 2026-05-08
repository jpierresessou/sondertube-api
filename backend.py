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

@app.get("/")
def root():
    return {"status": "online", "app": "SonderTube", "version": "2.1.0"}

@app.get("/api/info")
def get_info(url: str = Query(...)):
    try:
        opts = {'quiet': True, 'no_warnings': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Recherche YouTube
            if url.startswith('ytsearch'):
                info = ydl.extract_info(url, download=False)
                entries = info.get('entries', [])[:10]
                results = []
                for entry in entries:
                    formats = get_formats(entry)
                    results.append({
                        'title': entry.get('title', 'Sans titre')[:100],
                        'duration': entry.get('duration', 0),
                        'thumbnail': entry.get('thumbnail', ''),
                        'uploader': entry.get('uploader', ''),
                        'webpage_url': entry.get('webpage_url', ''),
                        'url': entry.get('webpage_url', ''),
                        'formats': formats
                    })
                return {'success': True, 'entries': results, 'is_search': True}
            else:
                info = ydl.extract_info(url, download=False)
                formats = get_formats(info)
                return {
                    'success': True,
                    'title': info.get('title', 'Sans titre')[:100],
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'uploader': info.get('uploader', ''),
                    'formats': formats,
                    'is_search': False
                }
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}

def get_formats(info):
    """Extrait les formats vidéo ET audio pour chaque lien"""
    formats = []
    raw_formats = info.get('formats', [])
    seen_video = set()
    has_audio_option = False

    # Formats vidéo (mp4 avec hauteur)
    for f in raw_formats:
        if f.get('ext') == 'mp4' and f.get('height') and f['height'] not in seen_video:
            seen_video.add(f['height'])
            formats.append({
                'format_id': f['format_id'],
                'quality': f'{f["height"]}p',
                'type': 'video',
                'label': f'{f["height"]}p MP4',
                'filesize': f.get('filesize', 0)
            })

    # Format audio (toujours proposé, peu importe le type de lien)
    if not has_audio_option:
        # Chercher le meilleur format audio
        for f in raw_formats:
            if f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                formats.append({
                    'format_id': f['format_id'],
                    'quality': 'Audio',
                    'type': 'audio',
                    'label': 'MP3 Audio',
                    'filesize': f.get('filesize', 0)
                })
                break
        
        # Si aucun format audio pur trouvé, prendre le best audio
        if not any(f['type'] == 'audio' for f in formats):
            for f in raw_formats:
                if f.get('acodec') != 'none':
                    formats.append({
                        'format_id': f['format_id'],
                        'quality': 'Audio',
                        'type': 'audio',
                        'label': 'MP3 Audio',
                        'filesize': f.get('filesize', 0)
                    })
                    break

    return formats[:10]


@app.get("/api/download")
def download(url: str = Query(...), format_id: str = Query(...), type: str = Query("video")):
    try:
        tmpdir = tempfile.mkdtemp()
        out = os.path.join(tmpdir, '%(title)s.%(ext)s')
        
        if type == 'audio':
            # Télécharger le meilleur format audio + convertir en MP3
            opts = {
                'format': 'bestaudio/best',
                'outtmpl': out,
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            }
        else:
            # Télécharger vidéo + audio et fusionner
            opts = {
                'format': f'{format_id}+bestaudio/best',
                'outtmpl': out,
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4',
            }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            fname = ydl.prepare_filename(info)
            
            if type == 'audio':
                fname = fname.rsplit('.', 1)[0] + '.mp3'
            
            if not os.path.exists(fname):
                # Fallback : chercher le fichier
                for root, dirs, files in os.walk(tmpdir):
                    for file in files:
                        if file.endswith('.mp3') or file.endswith('.mp4'):
                            fname = os.path.join(root, file)
                            break
            
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
                headers={'Content-Disposition': f'attachment; filename="{safe}.{ext}"'}
            )
    except Exception as e:
        return {'success': False, 'error': str(e)[:200]}