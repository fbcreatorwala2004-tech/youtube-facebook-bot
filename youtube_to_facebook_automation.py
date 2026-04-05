#!/usr/bin/env python3
import os
import json
import time
import feedparser
from datetime import datetime
from pathlib import Path
import yt_dlp
from facebook import GraphAPI


class YouTubeToFacebookBot:
    def __init__(self):
        self.load_config()
        self.posted_videos_file = 'posted_videos.json'
        self.posted_videos = self.load_posted_videos()

    def load_config(self):
        # Load from GitHub Secrets
        self.youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        self.facebook_access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.hashtags = os.getenv('HASHTAGS', '#video #trending')

        if not all([self.youtube_channel_id, self.facebook_page_id, self.facebook_access_token]):
            raise Exception("❌ Missing environment variables")

        self.youtube_channel_url = f"https://www.youtube.com/channel/{self.youtube_channel_id}"
        self.download_path = './downloads'

        # Create folder (IMPORTANT)
        Path(self.download_path).mkdir(exist_ok=True)

        print("✅ Running in GitHub Actions mode")

    def load_posted_videos(self):
        if os.path.exists(self.posted_videos_file):
            with open(self.posted_videos_file, 'r') as f:
                return json.load(f)
        return {}

    def save_posted_videos(self):
        with open(self.posted_videos_file, 'w') as f:
            json.dump(self.posted_videos, f, indent=2)

    def get_rss_url(self):
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.youtube_channel_id}"

    def check_new_videos(self):
        print("🔍 Checking for new videos...")
        feed = feedparser.parse(self.get_rss_url())

        new_videos = []

        for entry in feed.entries:
            video_id = entry.yt_videoid

            if video_id not in self.posted_videos:
                new_videos.append({
                    "id": video_id,
                    "url": entry.link,
                    "title": entry.title
                })
                print(f"📹 New video: {entry.title}")

        return new_videos

    def download_video(self, url, video_id):
        print("⬇️ Downloading video...")

        path = os.path.join(self.download_path, f"{video_id}.mp4")

        ydl_opts = {
            'format': 'mp4',
            'outtmpl': path,
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

    def upload_to_facebook(self, video_path, title):
        print("📤 Uploading to Facebook...")

        try:
            graph = GraphAPI(access_token=self.facebook_access_token)

            description = f"{title}\n\n{self.hashtags}"

            with open(video_path, 'rb') as video:
                res = graph.put_video(video=video, description=description)

            print("✅ Uploaded successfully")
            return res.get("id")

        except Exception as e:
            print("❌ Upload error:", e)
            return None

    def process_video(self, video):
        vid = video["id"]

        video_path = self.download_video(video["url"], vid)

        if not video_path:
            return

        post_id = self.upload_to_facebook(video_path, video["title"])

        if post_id:
            self.posted_videos[vid] = True
            self.save_posted_videos()
            os.remove(video_path)

    def run(self):
        videos = self.check_new_videos()

        if not videos:
            print("ℹ️ No new videos")
            return

        for video in videos:
            self.process_video(video)


def main():
    bot = YouTubeToFacebookBot()
    bot.run()


if __name__ == "__main__":
    main()
