import os
import json
import time
import requests
from googleapiclient.discovery import build

# =========================
# CONFIG
# =========================
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")
FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
HASHTAGS = os.getenv("HASHTAGS", "")

POSTED_FILE = "posted_videos.json"

# =========================
# VALIDATION
# =========================
if not all([YOUTUBE_API_KEY, YOUTUBE_CHANNEL_ID, FACEBOOK_PAGE_ID, FACEBOOK_ACCESS_TOKEN]):
    raise Exception("❌ Missing environment variables")

# =========================
# INIT YOUTUBE
# =========================
youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

# =========================
# LOAD POSTED VIDEOS
# =========================
def load_posted():
    if not os.path.exists(POSTED_FILE):
        return set()
    with open(POSTED_FILE, "r") as f:
        return set(json.load(f))

def save_posted(posted):
    with open(POSTED_FILE, "w") as f:
        json.dump(list(posted), f)

# =========================
# GET VIDEOS
# =========================
def get_latest_videos():
    request = youtube.search().list(
        part="snippet",
        channelId=YOUTUBE_CHANNEL_ID,
        maxResults=10,
        order="date"
    )
    response = request.execute()

    videos = []

    for item in response.get("items", []):
        if item["id"]["kind"] == "youtube#video":
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            videos.append((video_id, title))

    return videos

# =========================
# FACEBOOK UPLOAD (TEXT POST)
# =========================
def post_to_facebook(title, video_id):
    url = f"https://graph.facebook.com/{FACEBOOK_PAGE_ID}/feed"

    message = f"{title}\n\nhttps://www.youtube.com/watch?v={video_id}\n\n{HASHTAGS}"

    payload = {
        "message": message,
        "access_token": FACEBOOK_ACCESS_TOKEN
    }

    for attempt in range(3):
        try:
            print(f"📤 Upload attempt {attempt+1}")

            res = requests.post(url, data=payload)
            data = res.json()

            if res.status_code == 200:
                print(f"✅ Posted: {data}")
                return True
            else:
                print("❌ Error:", data)

        except Exception as e:
            print("❌ Exception:", e)

        time.sleep(5)

    return False

# =========================
# MAIN LOGIC
# =========================
def main():
    print("🔥 Bot Started Successfully")

    posted = load_posted()
    videos = get_latest_videos()

    print(f"📊 {len(videos)} videos found")

    new_videos = []

    for vid, title in videos:
        if vid not in posted:
            new_videos.append((vid, title))

    print(f"🆕 New videos: {len(new_videos)}")

    for vid, title in new_videos:
        success = post_to_facebook(title, vid)

        if success:
            posted.add(vid)
            save_posted(posted)

        print("⏳ Waiting before next upload...")
        time.sleep(10)

    print("✅ Done")

if __name__ == "__main__":
    main()
