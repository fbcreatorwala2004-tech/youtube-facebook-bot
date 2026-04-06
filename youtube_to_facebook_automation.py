#!/usr/bin/env python3

import os
import json
import feedparser
import requests
from datetime import datetime, timedelta
from pathlib import Path
import yt_dlp
import time


class YouTubeToFacebookBot:
    def __init__(self):
        self.youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        self.facebook_access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.hashtags = os.getenv('HASHTAGS', '#reels #viral #video')

        if not all([self.youtube_channel_id, self.facebook_page_id, self.facebook_access_token]):
            raise Exception("❌ Missing environment variables")

        self.download_path = './downloads'
        Path(self.download_path).mkdir(exist_ok=True)

        self.posted_file = 'posted_videos.json'
        self.posted = self.load_posted()

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

    def get_feed(self):
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={self.youtube_channel_id}"
        return feedparser.parse(url)

    def get_videos(self):
        feed = self.get_feed()
        videos = []

        for entry in feed.entries:
            videos.append({
                "id": entry.yt_videoid,
                "title": entry.title,
                "url": entry.link
            })

        return videos

    def get_videos_to_post(self):
        videos = self.get_videos()

        if not self.posted:
            return videos[::-1]

        return [v for v in videos if v["id"] not in self.posted]

    # ---------------- ANTI-SPAM ----------------

    def can_post_now(self):
        if not self.posted:
            return True

        last_time = max(
            datetime.fromisoformat(v["time"])
            for v in self.posted.values()
        )

        if datetime.now() < last_time + timedelta(hours=1):
            print("⏳ Waiting to avoid spam")
            return False

        return True

    # ---------------- DOWNLOAD ----------------

    def download_video(self, url, vid):
        print("⬇️ Downloading video...")

        path = os.path.join(self.download_path, f"{vid}.mp4")

        ydl_opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best',
            'outtmpl': path,
            'merge_output_format': 'mp4',
            'quiet': True,
            'noplaylist': True
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            return path

        except Exception as e:
            print("❌ Download error:", e)
            return None

    # ---------------- CAPTION ----------------

    def create_caption(self, title):
        return f"🔥 {title}\n\n{self.hashtags}"

    # ---------------- FACEBOOK UPLOAD ----------------

    def upload_video(self, path, title):
        print("📤 Uploading to Facebook...")

        url = f"https://graph.facebook.com/v19.0/{self.facebook_page_id}/videos"

        caption = self.create_caption(title)

        files = {
            'source': open(path, 'rb')
        }

        data = {
            'access_token': self.facebook_access_token,
            'description': caption
        }

        for attempt in range(3):
            try:
                response = requests.post(url, files=files, data=data)
                result = response.json()

                print("📩 Response:", result)

                if 'id' in result:
                    print("✅ Upload success")
                    return result['id']
                else:
                    raise Exception(result)

            except Exception as e:
                print(f"⚠️ Retry {attempt+1} failed:", e)
                time.sleep(5)

        return None

    # ---------------- PROCESS ----------------

    def process(self, video):
        vid = video["id"]

        file = self.download_video(video["url"], vid)
        if not file:
            return

        post_id = self.upload_video(file, video["title"])

        if post_id:
            self.posted[vid] = {
                "title": video["title"],
                "time": datetime.now().isoformat()
            }

            self.save_posted()

            os.remove(file)
            print("🗑️ File cleaned")

        else:
            print("❌ Upload failed")

    # ---------------- MAIN RUN ----------------

    def run(self):
        if not self.can_post_now():
            return

        videos = self.get_videos_to_post()

        if not videos:
            print("ℹ️ No new videos")
            return

        print(f"📊 {len(videos)} videos found")

        self.process(videos[0])


if __name__ == "__main__":
    bot = YouTubeToFacebookBot()
    bot.run()
