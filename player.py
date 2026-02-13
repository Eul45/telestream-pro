import asyncio
import os
import webbrowser
import subprocess
from telethon import TelegramClient
from aiohttp import web

# --- CONFIG ---
API_ID = 12345678           # Replace with your API ID (e.g number 12345678  )
API_HASH = 'your_api_hash'  # Replace with your API HASH (it is text)
client = TelegramClient('my_player_session', API_ID, API_HASH)
global_message = None

# --- VLC DETECTION ---
def launch_vlc(url):
    # Common paths where VLC is installed on Windows
    vlc_paths = [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"
    ]
    vlc_path = next((p for p in vlc_paths if os.path.exists(p)), None)
    
    if vlc_path:
        # Launch VLC with the stream URL
        subprocess.Popen([vlc_path, url])
        return True
    return False

# --- UI DESIGN (Modern Dark Theme) ---
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>TeleStream Pro</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root { --primary: #0088cc; --bg: #0f172a; --card: #1e293b; --text: #f8fafc; }
        body { background: var(--bg); color: var(--text); font-family: 'Inter', sans-serif; margin: 0; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
        .app-card { background: var(--card); padding: 2rem; border-radius: 1rem; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.3); width: 90%; max-width: 600px; margin-top: 50px; text-align: center; }
        h1 { font-weight: 800; margin-bottom: 1.5rem; letter-spacing: -0.025em; color: white; }
        .input-group { display: flex; gap: 10px; margin-bottom: 20px; }
        input { flex: 1; padding: 12px 16px; border-radius: 8px; border: 1px solid #334155; background: #0f172a; color: white; outline: none; transition: 0.2s; }
        input:focus { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(0,136,204,0.2); }
        button { padding: 12px 24px; background: var(--primary); border: none; color: white; border-radius: 8px; cursor: pointer; font-weight: 600; transition: 0.2s; }
        button:hover { filter: brightness(1.1); transform: translateY(-1px); }
        .vlc-btn { background: #ff8800; margin-top: 10px; display: none; width: 100%; }
        video { width: 100%; border-radius: 8px; margin-top: 20px; display: none; background: black; }
        .status { margin-top: 15px; font-size: 14px; color: #94a3b8; }
        .badge { background: #10b981; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="app-card">
        <h1>TeleStream <span style="color:var(--primary)">Pro</span></h1>
        <div class="input-group">
            <input type="text" id="linkInput" placeholder="Paste Telegram link here...">
            <button onclick="loadVideo()">Load</button>
        </div>
        <p class="status" id="statusText">Ready to stream</p>
        
        <button id="vlcBtn" class="vlc-btn" onclick="openVLC()">🚀 Open in VLC Player (Subtitles & Audio)</button>
        <video id="videoPlayer" controls></video>
    </div>

    <script>
        async function loadVideo() {
            const link = document.getElementById('linkInput').value;
            const status = document.getElementById('statusText');
            const vlcBtn = document.getElementById('vlcBtn');
            const video = document.getElementById('videoPlayer');
            
            status.innerHTML = "🔍 Searching Telegram...";
            const response = await fetch('/set_link?link=' + encodeURIComponent(link));
            const data = await response.text();
            
            if (response.status === 200) {
                status.innerHTML = '<span class="badge">Connected</span> ' + data;
                vlcBtn.style.display = "block";
                video.style.display = "block";
                video.src = "/stream";
            } else {
                status.innerText = "❌ " + data;
            }
        }

        async function openVLC() {
            await fetch('/open_vlc');
        }
    </script>
</body>
</html>
"""

# --- BACKEND LOGIC ---
async def handle_home(request): return web.Response(text=HTML_PAGE, content_type='text/html')

async def handle_set_link(request):
    global global_message
    link = request.query.get('link')
    try:
        parts = link.strip().split('/')
        msg_id = int(parts[-1])
        username = parts[-2]
        global_message = await client.get_messages(username, ids=msg_id)
        if not global_message or not global_message.media or not hasattr(global_message, 'file'):
             return web.Response(text="No video file found", status=400)
        return web.Response(text=getattr(global_message.file, 'name', 'Video Stream') or 'Video Stream')
    except: return web.Response(text="Invalid Link Format", status=400)

async def handle_stream(request):
    if not global_message: return web.Response(status=404)
    file_size = global_message.file.size
    offset = 0
    range_header = request.headers.get('Range')
    if range_header:
        offset = int(range_header.replace('bytes=', '').split('-')[0])
    
    headers = {
        'Content-Type': global_message.file.mime_type,
        'Content-Range': f'bytes {offset}-{file_size-1}/{file_size}',
        'Accept-Ranges': 'bytes',
    }
    res = web.StreamResponse(status=206 if range_header else 200, headers=headers)
    await res.prepare(request)
    async for chunk in client.iter_download(global_message.media, offset=offset):
        await res.write(chunk)
    return res

async def handle_vlc(request):
    success = launch_vlc("http://localhost:8080/stream")
    if success: return web.Response(text="OK")
    return web.Response(text="VLC not found", status=404)

async def main():
    await client.start()
    app = web.Application()
    app.router.add_get('/', handle_home)
    app.router.add_get('/set_link', handle_set_link)
    app.router.add_get('/stream', handle_stream)
    app.router.add_get('/open_vlc', handle_vlc)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, 'localhost', 8080).start()
    webbrowser.open('http://localhost:8080')
    await asyncio.Event().wait()

if __name__ == '__main__':
    client.loop.run_until_complete(main())