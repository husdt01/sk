from flask import Flask, render_template, request, jsonify, Response
import yt_dlp
import requests
import os

app = Flask(__name__)

def get_stream_url(sc_url):
    """Получает прямой URL аудио-потока с SoundCloud"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(sc_url, download=False)
        
        # Если это плейлист, берем первый трек
        if 'entries' in info:
            if info['entries']:
                info = info['entries'][0]
            else:
                return None, None
        
        # Получаем URL потока
        if 'url' in info:
            return info['url'], info.get('title', 'Unknown')
        
        # Альтернативный вариант
        formats = info.get('formats', [])
        if formats:
            # Берем лучший аудио-формат
            audio_formats = [f for f in formats if f.get('acodec') != 'none']
            if audio_formats:
                return audio_formats[-1]['url'], info.get('title', 'Unknown')
        
        return None, None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/stream")
def stream():
    """Стримит трек по URL SoundCloud"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    
    stream_url, title = get_stream_url(url)
    if not stream_url:
        return jsonify({"error": "Could not extract stream"}), 400
    
    # Проксируем поток
    def generate():
        with requests.get(stream_url, stream=True) as r:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    yield chunk
    
    return Response(
        generate(),
        mimetype='audio/mpeg',
        headers={
            'Accept-Ranges': 'bytes',
            'Content-Disposition': f'inline; filename="{title}.mp3"'
        }
    )

@app.route("/api/info")
def info():
    """Получает инфо о треке/плейлисте"""
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "No URL"}), 400
    
    ydl_opts = {'quiet': True, 'extract_flat': True}
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
        if 'entries' in info:
            # Это плейлист
            tracks = []
            for entry in info['entries']:
                if entry:
                    tracks.append({
                        'title': entry.get('title', 'Unknown'),
                        'url': entry.get('url') or entry.get('webpage_url'),
                        'duration': entry.get('duration'),
                    })
            return jsonify({
                'type': 'playlist',
                'title': info.get('title', 'Playlist'),
                'tracks': tracks
            })
        else:
            # Это один трек
            return jsonify({
                'type': 'track',
                'title': info.get('title', 'Unknown'),
                'url': info.get('webpage_url'),
                'duration': info.get('duration'),
            })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
