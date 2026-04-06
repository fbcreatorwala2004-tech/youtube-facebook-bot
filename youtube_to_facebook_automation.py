#!/usr/bin/env python3

import os
import json
import requests
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

        # convert to set for FAST lookup (prevents duplicates perfectly)
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

        try:
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

        except Exception as e:
            print("❌ YouTube API error:", e)
            return []

    def get_videos_to_post(self):
        videos = self.get_videos()

        new_videos = []

        for v in videos:
            if v["id"] not in self.posted_ids:
                new_videos.append(v)

        return new_videos

    # ---------------- CAPTION ----------------

    def create_caption(self, title):
        return f"🔥 {title}\n\n{self.hashtags}"

    # ---------------- FACEBOOK UPLOAD (STREAMING) ----------------

    def upload_video(self, video_url, title):
        print("📤 Uploading (streaming)...")

        url = f"https://graph.facebook.com/v19.0/{self.facebook_page_id}/videos"

        try:
            with requests.get(video_url, stream=True) as r:
                r.raise_for_status()

                files = {
                    'source': ('video.mp4', r.raw, 'video/mp4')
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

                print("❌ Upload failed")
                return None

        except Exception as e:
            print("❌ Upload error:", e)
            return None

    # ---------------- PROCESS ----------------

    def process(self, video):
        vid = video["id"]

        # 🚨 duplicate protection (FAST)
        if vid in self.posted_ids:
            print(f"⏭️ Skipping duplicate: {vid}")
            return

        post_id = self.upload_video(video["url"], video["title"])

        if post_id:
            self.posted[vid] = {
                "title": video["title"],
                "time": datetime.now().isoformat()
            }

            self.posted_ids.add(vid)  # keep in memory

            self.save_posted()

            print("✅ Saved to posted list")

        else:
            print("❌ Upload failed")

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
