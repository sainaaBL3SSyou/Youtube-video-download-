import os
import threading
import wave
import contextlib
from flask import Flask, request, render_template_string, jsonify
import yt_dlp

app = Flask(__name__)

# Track the download status to update the UI
download_status = {"message": "Ready to download.", "is_active": False}

class MyLogger(object):
    def debug(self, msg):
        global download_status
        print(msg) 
        if "has already been recorded in the archive" in msg or "has already been downloaded" in msg:
            download_status["message"] = "⚠️ This video has already been downloaded!"
            
    def warning(self, msg):
        print(f"WARNING: {msg}")
        
    def error(self, msg):
        global download_status
        print(f"ERROR: {msg}")
        download_status["message"] = f"❌ Error: {msg}"

def download_audio_worker(url, base_dir, new_dir):
    global download_status
    download_status["is_active"] = True
    download_status["message"] = "Fetching video info, audio, and subtitles..."
    
    expanded_base_dir = os.path.expanduser(base_dir) 
    full_target_dir = os.path.join(expanded_base_dir, new_dir)
    os.makedirs(full_target_dir, exist_ok=True)
    
    archive_file = os.path.join(expanded_base_dir, "download_archive.txt")

    ydl_opts = {
        'format': '251',                    
        'cookiefile': 'cookies.txt',        
        'outtmpl': os.path.join(full_target_dir, '%(title)s.%(ext)s'),
        'download_archive': archive_file,   
        
        'writeautomaticsub': True,        
        'writesubtitles': True,           
        'subtitleslangs': ['mn.*', 'mn'], 
        
        'logger': MyLogger(),
        'postprocessors': [
            {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',    
            },
            {
                'key': 'FFmpegSubtitlesConvertor',
                'format': 'srt',            
            }
        ],
        'ignoreerrors': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if "already been downloaded" not in download_status["message"]:
            download_status["message"] = f"✅ Success! Saved WAV and SRT to: {full_target_dir}"
    except Exception as e:
        download_status["message"] = f"❌ Script Error: {str(e)}"
    finally:
        download_status["is_active"] = False


# HTML/CSS for localhost UI
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>YT Audio & Subs Downloader</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 700px; margin: 50px auto; padding: 20px; border: 1px solid #ccc; border-radius: 10px; background-color: #f4f4f9; }
        h2 { color: #333; margin-bottom: 10px;}
        .input-group { margin-bottom: 15px; }
        label { font-weight: bold; display: block; margin-bottom: 5px;}
        input[type=text] { width: 100%; padding: 10px; box-sizing: border-box; border: 1px solid #ccc; border-radius: 4px;}
        button { background-color: #28a745; color: white; padding: 12px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; width: 100%; font-weight: bold;}
        button:hover { background-color: #218838; }
        button:disabled { background-color: #cccccc; cursor: not-allowed; }
        .calc-btn { background-color: #007bff; margin-top: 10px; }
        .calc-btn:hover { background-color: #0056b3; }
        #status-box, #calc-box { margin-top: 20px; padding: 15px; background-color: #fff; border: 1px solid #ddd; border-radius: 5px; line-height: 1.5;}
        hr { border: 0; height: 1px; background: #ddd; margin: 30px 0; }
        
        /* Excel-like Table Styles */
        table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 14px; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #f2f2f2; font-weight: bold; color: #333; }
        tr:nth-child(even) { background-color: #fafafa; }
        tr:hover { background-color: #f1f1f1; }
        .grand-total { font-weight: bold; background-color: #e9ecef !important; font-size: 15px; }
    </style>
</head>
<body>
    <h2>🎧 YT to WAV & SRT Downloader</h2>
    
    <div class="input-group">
        <label>YouTube Video or Channel URL:</label>
        <input type="text" id="url" placeholder="https://www.youtube.com/watch?v=dSizy1I7ATQ">
    </div>

    <div class="input-group">
        <label>Base Directory (Home):</label>
        <input type="text" id="base_dir" placeholder="~/tts_data/ytdatas" value="~/tts_data/ytdatas">
    </div>

    <div class="input-group">
        <label>New Directory (Folder Name):</label>
        <input type="text" id="new_dir" placeholder="GalzuuKINO">
    </div>
    
    <button id="dl-btn" onclick="startDownload()">Download Audio & Subs</button>
    
    <div id="status-box">
        <strong>Download Status:</strong> <span id="status" style="color: #0056b3;">Ready to download.</span>
    </div>

    <hr>

    <h2>📊 Dataset Table View</h2>
    <p style="font-size: 14px; color: #666;">Enter your main folder (e.g., ~/tts_data/ytdatas) to generate a breakdown of all subfolders.</p>
    
    <div class="input-group">
        <label>Main Folder Path:</label>
        <input type="text" id="calc_dir" placeholder="~/tts_data/ytdatas" value="~/tts_data/ytdatas">
    </div>

    <button class="calc-btn" id="calc-btn" onclick="calculateDuration()">Generate Excel-like Table</button>

    <div id="calc-box">
        <strong>Result:</strong> <span id="calc-result" style="color: #0056b3;">Waiting for input...</span>
    </div>

    <script>
        let statusInterval;

        function startDownload() {
            let url = document.getElementById('url').value;
            let base_dir = document.getElementById('base_dir').value;
            let new_dir = document.getElementById('new_dir').value;
            
            if (!url || !base_dir || !new_dir) {
                alert("Please fill in all 3 fields.");
                return;
            }

            document.getElementById('dl-btn').disabled = true;
            document.getElementById('status').innerText = "Initializing download...";

            fetch('/download', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url, base_dir: base_dir, new_dir: new_dir})
            });
            
            statusInterval = setInterval(checkStatus, 1500);
        }

        function checkStatus() {
            fetch('/status')
            .then(res => res.json())
            .then(data => {
                document.getElementById('status').innerText = data.message;
                
                if (!data.is_active && data.message !== "Initializing download...") {
                    document.getElementById('dl-btn').disabled = false;
                    clearInterval(statusInterval);
                }
            });
        }

        function calculateDuration() {
            let calc_dir = document.getElementById('calc_dir').value;
            
            if (!calc_dir) {
                alert("Please enter a folder path.");
                return;
            }

            document.getElementById('calc-btn').disabled = true;
            document.getElementById('calc-result').innerText = "Scanning folders and calculating times... please wait.";

            fetch('/calculate_duration', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({folder: calc_dir})
            })
            .then(res => res.json())
            .then(data => {
                document.getElementById('calc-btn').disabled = false;
                
                if (data.error) {
                    document.getElementById('calc-result').innerHTML = `<span style="color:red;">❌ ${data.error}</span>`;
                } else {
                    // Build the HTML Table dynamically
                    let tableHTML = `
                        <table>
                            <tr>
                                <th>📁 Channel Folder</th>
                                <th>🎵 .wav Files</th>
                                <th>⏱️ Total Duration</th>
                            </tr>
                    `;
                    
                    // Loop through each folder data
                    data.folders.forEach(folder => {
                        tableHTML += `
                            <tr>
                                <td>${folder.name}</td>
                                <td>${folder.file_count}</td>
                                <td>${folder.time_str}</td>
                            </tr>
                        `;
                    });

                    // Add Grand Total row at the bottom
                    tableHTML += `
                            <tr class="grand-total">
                                <td>TOTAL DATASET</td>
                                <td>${data.grand_total_files}</td>
                                <td>${data.grand_total_time}</td>
                            </tr>
                        </table>
                    `;
                    
                    document.getElementById('calc-result').innerHTML = tableHTML;
                }
            })
            .catch(err => {
                document.getElementById('calc-btn').disabled = false;
                document.getElementById('calc-result').innerText = "Error calculating duration.";
            });
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/download', methods=['POST'])
def start_download_route():
    data = request.json
    if not download_status["is_active"]:
        thread = threading.Thread(
            target=download_audio_worker, 
            args=(data['url'], data['base_dir'], data['new_dir'])
        )
        thread.start()
        return jsonify({"status": "started"})
    return jsonify({"status": "already_running"})

@app.route('/status')
def get_status_route():
    return jsonify(download_status)

@app.route('/calculate_duration', methods=['POST'])
def calc_duration_route():
    folder_path = request.json.get('folder', '')
    expanded_path = os.path.expanduser(folder_path)
    
    if not os.path.exists(expanded_path):
        return jsonify({"error": "Folder does not exist. Please check the path."})

    folder_stats = []
    grand_total_seconds = 0.0
    grand_total_files = 0

    try:
        # 1. Get a list of everything in the parent folder (e.g., ytdatas)
        entries = os.listdir(expanded_path)
    except Exception as e:
        return jsonify({"error": f"Could not read directory: {str(e)}"})

    # 2. Iterate through each item
    for entry in entries:
        entry_path = os.path.join(expanded_path, entry)
        
        # Only process sub-directories (ignore the download_archive.txt file here)
        if os.path.isdir(entry_path):
            folder_seconds = 0.0
            folder_files = 0
            
            # Walk inside the sub-directory to find .wav files
            for root, dirs, files in os.walk(entry_path):
                for file in files:
                    if file.lower().endswith('.wav'):
                        file_path = os.path.join(root, file)
                        try:
                            with contextlib.closing(wave.open(file_path, 'r')) as f:
                                frames = f.getnframes()
                                rate = f.getframerate()
                                duration = frames / float(rate)
                                folder_seconds += duration
                                folder_files += 1
                        except Exception as e:
                            pass # Skip files that are corrupted or unreadable

            # Only add to the table if there is actually audio inside it
            if folder_files > 0:
                h = int(folder_seconds // 3600)
                m = int((folder_seconds % 3600) // 60)
                s = int(folder_seconds % 60)
                
                folder_stats.append({
                    "name": entry,
                    "file_count": folder_files,
                    "time_str": f"{h}h {m}m {s}s"
                })
                
                grand_total_seconds += folder_seconds
                grand_total_files += folder_files

    # 3. Sort the list alphabetically by folder name for a clean look
    folder_stats = sorted(folder_stats, key=lambda x: x['name'])

    # 4. Format the Grand Total
    gh = int(grand_total_seconds // 3600)
    gm = int((grand_total_seconds % 3600) // 60)
    gs = int(grand_total_seconds % 60)

    return jsonify({
        "folders": folder_stats,
        "grand_total_files": grand_total_files,
        "grand_total_time": f"{gh}h {gm}m {gs}s"
    })

if __name__ == '__main__':
    print("Server started!")
    print("Open http://127.0.0.1:5001 in your web browser.")
    app.run(host='127.0.0.1', port=5001)