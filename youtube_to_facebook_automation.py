#!/usr/bin/env python3
import os
import json
import feedparser
from datetime import datetime, timedelta
from pathlib import Path
import yt_dlp
from facebook import GraphAPI
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

        print("🔥 Smart Bot Started (Anti-Spam Enabled)")

    def load_posted(self):
        if os.path.exists(self.posted_file):
            with open(self.posted_file, 'r') as f:
                return json.load(f)
        return {}

    def save_posted(self):
        with open(self.posted_file, 'w') as f:
            json.dump(self.posted, f, indent=2)

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
        all_videos = self.get_videos()

        # First run → upload old videos
        if not self.posted:
            print("📂 First run → scheduling old videos")
            return all_videos[::-1]

        # Otherwise new videos only
        new = []
        for v in all_videos:
            if v["id"] not in self.posted:
                new.append(v)

        return new

    def can_post_now(self):
        """Ensure 1 post per hour"""
        if not self.posted:
            return True

        last_post_time = max(
            datetime.fromisoformat(v["time"])
            for v in self.posted.values()
            if "time" in v
        )

        next_allowed = last_post_time + timedelta(hours=1)

        if datetime.now() < next_allowed:
            wait = (next_allowed - datetime.now()).seconds // 60
            print(f"⏳ Waiting {wait} minutes (anti-spam)")
            return False

        return True

    def download_video(self, url, vid):
        print("⬇️ Downloading 1080p...")

        path = os.path.join(self.download_path, f"{vid}.mp4")

        opts = {
            'format': 'bestvideo[height<=1080]+bestaudio/best',
            'outtmpl': path,
            'merge_output_format': 'mp4',
            'quiet': True,
            'noplaylist': True
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
            return path
        except Exception as e:
            print("❌ Download error:", e)
            return None

    def create_caption(self, title):
        return f"🔥 {title}\n\n{self.hashtags}"

    def upload_video(self, path, title):
        print("📤 Uploading...")

        graph = GraphAPI(access_token=self.facebook_access_token)
        caption = self.create_caption(title)

        for attempt in range(3):
            try:
                with open(path, 'rb') as video:
                    res = graph.put_video(video=video, description=caption)

                print("✅ Uploaded successfully")
                return res.get("id")

            except Exception as e:
                print(f"⚠️ Retry {attempt+1}: {e}")
                time.sleep(5)

        return None

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
            print("🗑️ Cleaned")
        else:
            print("❌ Upload failed")

    def run(self):
        if not self.can_post_now():
            return

        videos = self.get_videos_to_post()

        if not videos:
            print("ℹ️ No videos to post")
            return

        print(f"📊 {len(videos)} videos pending")

        # Post only ONE video per run (anti-spam)
        self.process(videos[0])


if __name__ == "__main__":
    bot = YouTubeToFacebookBot()
    bot.run()
