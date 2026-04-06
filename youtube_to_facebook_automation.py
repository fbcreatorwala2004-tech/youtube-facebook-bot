#!/usr/bin/env python3

import os
import json
import requests
import time
from datetime import datetime


class YouTubeToFacebookBot:
    def __init__(self):
        self.youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        self.api_key = os.getenv('YOUTUBE_API_KEY')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        self.facebook_access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.hashtags = os.getenv('HASHTAGS', '#reels #viral #video')

        if not all([self.youtube_channel_id, self.api_key, self.facebook_page_id, self.facebook_access_token]):
            raise Exception("❌ Missing environment variables")

        self.posted_file = 'posted_videos.json'
        self.posted = self.load_posted()
        self.posted_ids = set(self.posted.keys())

        print("🔥 Bot Started Successfully")

    # ---------------- LOAD / SAVE ----------------

    def load_posted(self):
        if os.path.exists(self.posted_file):
            with open(self.posted_file, 'r') as f:
                return json.load(f)
        return {}

    def save_posted(self):
        with open(self.posted_file, 'w') as f:
            json.dump(self.posted, f, indent=2)

    # ---------------- YOUTUBE ----------------

    def get_videos(self):
        url = (
            "https://www.googleapis.com/youtube/v3/search"
            f"?key={self.api_key}"
            f"&channelId={self.youtube_channel_id}"
            "&part=snippet,id"
            "&order=date"
            "&maxResults=10"
        )

        data = requests.get(url).json()

        videos = []

        for item in data.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                vid = item["id"]["videoId"]

                videos.append({
                    "id": vid,
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={vid}"
                })

        return videos

    def get_videos_to_post(self):
        videos = self.get_videos()
        return [v for v in videos if v["id"] not in self.posted_ids]

    # ---------------- CAPTION ----------------

    def create_caption(self, title):
        return f"🔥 {title}\n\n{self.hashtags}"

    # ---------------- PROGRESS UPLOAD ----------------

    def upload_video_with_progress(self, video_url, title):
        url = f"https://graph.facebook.com/v19.0/{self.facebook_page_id}/videos"

        retries = 3

        for attempt in range(1, retries + 1):
            print(f"📤 Upload attempt {attempt}...")

            try:
                with requests.get(video_url, stream=True) as r:
                    r.raise_for_status()

                    total = int(r.headers.get('content-length', 0))
                    uploaded = 0

                    def generate():
                        nonlocal uploaded
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                uploaded += len(chunk)
                                yield chunk

                                if total:
                                    percent = int((uploaded / total) * 100)
                                    print(f"⏳ Uploading... {percent}%")

                    files = {
                        'source': ('video.mp4', generate(), 'video/mp4')
                    }

                    data = {
                        'access_token': self.facebook_access_token,
                        'description': self.create_caption(title)
                    }

                    response = requests.post(url, files=files, data=data)
                    result = response.json()

                    print("📩 Response:", result)

                    if 'id' in result:
                        print("✅ Upload success")
                        return result['id']

                    else:
                        print("❌ Upload failed")

            except Exception as e:
                print("❌ Error:", e)

            # Retry delay
            print("🔁 Retrying in 5 seconds...")
            time.sleep(5)

        print("❌ All retry attempts failed")
        return None

    # ---------------- PROCESS ----------------

    def process(self, video):
        vid = video["id"]

        if vid in self.posted_ids:
            print(f"⏭️ Skipping duplicate: {vid}")
            return

        post_id = self.upload_video_with_progress(video["url"], video["title"])

        if post_id:
            self.posted[vid] = {
                "title": video["title"],
                "time": datetime.now().isoformat()
            }

            self.posted_ids.add(vid)
            self.save_posted()

    # ---------------- RUN ----------------

    def run(self):
        videos = self.get_videos_to_post()

        if not videos:
            print("ℹ️ No new videos")
            return

        print(f"📊 {len(videos)} new videos found")

        for video in videos:
            self.process(video)


if __name__ == "__main__":
    bot = YouTubeToFacebookBot()
    bot.run()
