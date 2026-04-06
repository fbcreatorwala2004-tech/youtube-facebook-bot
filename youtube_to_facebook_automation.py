#!/usr/bin/env python3
"""
YouTube to Facebook Video Automation - ACTUAL VIDEO UPLOAD
Downloads videos from YouTube and uploads them to Facebook (not just links!)
"""

import os
import json
import time
import feedparser
from datetime import datetime, timedelta
from pathlib import Path
import yt_dlp
from facebook import GraphAPI


class YouTubeToFacebookBot:
    def __init__(self):
        # Get credentials from environment variables
        self.youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        self.facebook_access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.hashtags = os.getenv('HASHTAGS', '#video #viral')

        # Validate all required credentials
        if not all([self.youtube_channel_id, self.facebook_page_id, self.facebook_access_token]):
            raise Exception("❌ Missing environment variables!")

        # Setup
        self.download_path = './downloads'
        Path(self.download_path).mkdir(exist_ok=True)

        self.posted_file = 'posted_videos.json'
        self.posted = self.load_posted()

        print("🚀 YouTube to Facebook Bot Started!")
        print(f"📺 Channel ID: {self.youtube_channel_id[:10]}...")
        print(f"📱 Page ID: {self.facebook_page_id}")
        print(f"#️⃣  Hashtags: {self.hashtags}")
        print("=" * 60)

    def load_posted(self):
        """Load previously posted video IDs"""
        if os.path.exists(self.posted_file):
            with open(self.posted_file, 'r') as f:
                return json.load(f)
        return {}

    def save_posted(self):
        """Save posted video IDs"""
        with open(self.posted_file, 'w') as f:
            json.dump(self.posted, f, indent=2)

    def get_feed(self):
        """Get YouTube RSS feed"""
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={self.youtube_channel_id}"
        print(f"🔍 Fetching feed from YouTube...")
        return feedparser.parse(url)

    def get_videos(self):
        """Get all videos from feed"""
        feed = self.get_feed()
        videos = []

        if not feed.entries:
            print("⚠️  No videos found in feed. Check your channel ID!")
            return videos

        print(f"📊 Found {len(feed.entries)} total videos in feed")

        for entry in feed.entries:
            videos.append({
                "id": entry.yt_videoid,
                "title": entry.title,
                "url": entry.link,
                "published": entry.published
            })

        return videos

    def get_videos_to_post(self):
        """Get videos that haven't been posted yet"""
        all_videos = self.get_videos()

        if not all_videos:
            return []

        # First run: Post old videos one by one (oldest first)
        if not self.posted:
            print("📂 First run detected - will post videos gradually")
            return all_videos[::-1]  # Reverse to start with oldest

        # Normal operation: Only post NEW videos
        new_videos = []
        for video in all_videos:
            if video["id"] not in self.posted:
                new_videos.append(video)
                print(f"  🆕 New video detected: {video['title']}")

        return new_videos

    def can_post_now(self):
        """Anti-spam: Ensure at least 1 hour between posts"""
        if not self.posted:
            return True  # First run, OK to post

        # Get the most recent post time
        post_times = [
            datetime.fromisoformat(v["time"])
            for v in self.posted.values()
            if "time" in v
        ]

        if not post_times:
            return True

        last_post_time = max(post_times)
        next_allowed = last_post_time + timedelta(hours=1)
        now = datetime.now()

        if now < next_allowed:
            wait_minutes = int((next_allowed - now).total_seconds() / 60)
            print(f"⏳ Anti-spam: Waiting {wait_minutes} minutes before next post")
            print(f"   Last post: {last_post_time.strftime('%H:%M:%S')}")
            print(f"   Next allowed: {next_allowed.strftime('%H:%M:%S')}")
            return False

        return True

    def download_video(self, url, video_id):
        """Download video from YouTube using yt-dlp"""
        print(f"⬇️  Downloading video from YouTube...")
        print(f"   URL: {url}")

        output_path = os.path.join(self.download_path, f"{video_id}.mp4")

        # yt-dlp options for best quality that Facebook accepts
        ydl_opts = {
            'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best',
            'outtmpl': output_path,
            'merge_output_format': 'mp4',
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print("   Extracting video info...")
                info = ydl.extract_info(url, download=True)
                
                # Get video duration
                duration = info.get('duration', 0)
                filesize = info.get('filesize', 0) or info.get('filesize_approx', 0)
                
                print(f"   ✅ Downloaded successfully!")
                print(f"   Duration: {duration // 60}m {duration % 60}s")
                if filesize:
                    print(f"   Size: {filesize / (1024*1024):.1f} MB")
                
                return output_path

        except Exception as e:
            print(f"   ❌ Download failed: {e}")
            return None

    def create_caption(self, title):
        """Create Facebook post caption with title and hashtags"""
        return f"{title}\n\n{self.hashtags}"

    def upload_to_facebook(self, video_path, title):
        """Upload actual VIDEO file to Facebook (not just a link!)"""
        print(f"📤 Uploading VIDEO to Facebook...")
        print(f"   File: {video_path}")
        print(f"   Size: {os.path.getsize(video_path) / (1024*1024):.1f} MB")

        # Check file size (Facebook limit is ~1GB)
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        if file_size_mb > 1000:
            print(f"   ⚠️  Warning: File is {file_size_mb:.1f}MB (Facebook limit is ~1GB)")

        graph = GraphAPI(access_token=self.facebook_access_token)
        caption = self.create_caption(title)

        # Retry logic (Facebook uploads can be flaky)
        for attempt in range(3):
            try:
                print(f"   Attempt {attempt + 1}/3...")
                
                with open(video_path, 'rb') as video_file:
                    # This actually uploads the VIDEO file (not a text post!)
                    response = graph.put_video(
                        video=video_file,
                        description=caption,
                        title=title
                    )

                post_id = response.get("id")
                print(f"   ✅ Upload successful! Post ID: {post_id}")
                return post_id

            except Exception as e:
                print(f"   ⚠️  Attempt {attempt + 1} failed: {e}")
                if attempt < 2:  # Don't sleep on last attempt
                    print(f"   Retrying in 5 seconds...")
                    time.sleep(5)

        print(f"   ❌ All upload attempts failed!")
        return None

    def process_video(self, video):
        """Process one video: download and upload"""
        video_id = video["id"]
        video_title = video["title"]
        video_url = video["url"]

        print("\n" + "=" * 60)
        print(f"🎬 Processing: {video_title}")
        print("=" * 60)

        # Step 1: Download from YouTube
        video_path = self.download_video(video_url, video_id)

        if not video_path or not os.path.exists(video_path):
            print("❌ Download failed, skipping this video")
            return False

        # Step 2: Upload to Facebook
        post_id = self.upload_to_facebook(video_path, video_title)

        if post_id:
            # Step 3: Mark as posted
            self.posted[video_id] = {
                "title": video_title,
                "time": datetime.now().isoformat(),
                "facebook_post_id": post_id,
                "url": video_url
            }
            self.save_posted()
            print(f"💾 Saved to posted videos log")

            # Step 4: Clean up downloaded file
            try:
                os.remove(video_path)
                print(f"🗑️  Deleted temporary file")
            except Exception as e:
                print(f"⚠️  Could not delete file: {e}")

            print(f"✅ SUCCESS! Video posted to Facebook")
            return True
        else:
            print(f"❌ FAILED! Could not upload to Facebook")
            # Keep the file for manual troubleshooting
            print(f"   Video saved at: {video_path}")
            return False

    def run(self):
        """Main execution: check for videos and post if needed"""
        print(f"\n⏰ Run started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Check anti-spam timer
        if not self.can_post_now():
            print("⏸️  Skipping this run (anti-spam active)")
            return

        # Get videos to post
        videos_to_post = self.get_videos_to_post()

        if not videos_to_post:
            print("ℹ️  No new videos to post")
            print("   All caught up! Waiting for new uploads...")
            return

        print(f"📋 Videos pending: {len(videos_to_post)}")

        # Post only ONE video per run (anti-spam)
        video = videos_to_post[0]
        print(f"📌 Will post: {video['title']}")
        
        self.process_video(video)

        remaining = len(videos_to_post) - 1
        if remaining > 0:
            print(f"\n📊 Status: {remaining} more video(s) in queue")
            print(f"   Next post in ~1 hour (anti-spam delay)")


def main():
    """Entry point"""
    try:
        bot = YouTubeToFacebookBot()
        bot.run()
        print("\n✅ Bot run completed!")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
