import requests
import subprocess
import json
import os

# --- SETTINGS ---
SERVER_IP = "192.168.0.52"
API_KEY = "56a4e3689ab14822ab2e72a312e4d2bc"
ITEM_ID = "276d92972aec1bf7a143191bbe3c527b" # Can be passed as sys.argv[1]
DEVICE_ID = "pi4_headless_client"

TARGET_BITRATE = 4000000

def get_smart_url():
    # 1. Fetch User ID (Needed for PlaybackInfo permissions)
    user_url = f"http://{SERVER_IP}/Users?api_key={API_KEY}"
    user_id = requests.get(user_url).json()[0]['Id']

    # 2. Define exactly what the Pi 4 hardware can do
    # DirectPlayProfiles = Files the Pi can play natively (H.264/H.265)
    # TranscodingProfiles = What to convert to if the file is AV1
    payload = {
        "UserId": user_id,
        "DeviceProfile": {
            "Name": "Pi4-LowBitrate",
            "MaxStaticBitrate": TARGET_BITRATE,
            "MaxStreamingBitrate": TARGET_BITRATE,
            "DirectPlayProfiles": [
                {
                    "Container": "mkv,mp4,webm,mov",
                    "Type": "Video",
                    "VideoCodec": "h264,hevc,h265",
                    "AudioCodec": "aac,mp3,opus,flac"
                }
            ],
            "TranscodingProfiles": [
                {
                    "Container": "ts",
                    "Type": "Video",
                    "VideoCodec": "h264",
                    "AudioCodec": "aac",
                    "Protocol": "Http",
                    "MaxAudioChannels": "2",
                    # This forces the server to cap the bitrate
                    "Bitrate": TARGET_BITRATE 
                }
            ],
            "SubtitleProfiles": [
                { "Format": "srt", "Method": "External" }
            ]
        }
    }

    # 3. Ask Jellyfin for the best way to play this specific file
    pb_url = f"http://{SERVER_IP}/Items/{ITEM_ID}/PlaybackInfo?api_key={API_KEY}"
    response = requests.post(pb_url, json=payload)
    data = response.json()

    media_source = data['MediaSources'][0]
    
    # 4. Check if we can bypass the transcoder
    if media_source.get('SupportsDirectPlay'):
        print(">>> [MATCH] Native H.264/H.265 detected. Direct Playing...")
        return f"http://{SERVER_IP}/Videos/{ITEM_ID}/stream?static=true&api_key={API_KEY}"
    
    else:
        print(">>> [MISMATCH] AV1/Unsupported codec detected. Requesting Transcode...")
        # Grab the transcoding URL provided by the server
        # Python's requests handles the \u0026 ampersands automatically
        trans_url = media_source.get('TranscodingUrl')
        return f"http://{SERVER_IP}{trans_url}"

def play_video():
    try:
        stream_url = get_smart_url()
        
        # 5. Execute MPV with Raspberry Pi Hardware Acceleration
        # --vo=drm: Direct Rendering Manager (bypasses X11/Wayland)
        # --hwdec=v4l2m2m-copy: Pi 4 specific hardware decoding
        mpv_cmd = [
            "mpv",
            "--vo=drm",
            "--hwdec=v4l2m2m-copy",
            "--drm-connector=1", # Use 1 or 2 depending on your HDMI port
            "--cache=yes",
            "--cache-secs=30",
            stream_url
        ]

        print(f"Starting playback: {stream_url}")
        subprocess.run(mpv_cmd)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    play_video()