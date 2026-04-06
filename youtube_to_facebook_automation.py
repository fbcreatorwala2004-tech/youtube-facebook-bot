#!/usr/bin/env python3

import os
import json
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import yt_dlp


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
        feed = feedparser.parse(url)

        print("📡 Feed entries:", len(feed.entries))  # DEBUG

        return feed

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

        print("🎥 Total videos found:", len(videos))
        print("📦 Already posted:", len(self.posted))

        # Only videos not already posted
        new_videos = [v for v in videos if v["id"] not in self.posted]

        print("🆕 Videos to post:", len(new_videos))

        return new_videos

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

        try:
            with open(path, 'rb') as file:
                response = requests.post(
                    url,
                    files={'source': file},
                    data={
                        'access_token': self.facebook_access_token,
                        'description': caption
                    }
                )

            print("📩 Response:", response.text)

            result = response.json()

            if 'id' in result:
                print("✅ Upload success")
                return result['id']
            else:
                print("❌ Upload failed")
                return None

        except Exception as e:
            print("❌ Upload error:", e)
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
            print("🗑️ File deleted")

        else:
            print("❌ Upload failed")

    # ---------------- MAIN RUN ----------------

    def run(self):
        videos = self.get_videos_to_post()

        if not videos:
            print("ℹ️ No new videos found")
            return

        print(f"📊 Processing {len(videos)} videos")

        for video in videos:
            print("🚀 Processing:", video["title"])
            self.process(video)


if __name__ == "__main__":
    bot = YouTubeToFacebookBot()
    bot.run()
