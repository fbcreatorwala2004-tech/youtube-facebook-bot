#!/usr/bin/env python3
"""
YouTube to Facebook Video Automation
Monitors a YouTube channel and automatically posts new videos to Facebook
"""

import os
import json
import time
import feedparser
import requests
from datetime import datetime
from pathlib import Path
import hashlib

# For video downloading
import yt_dlp

# For Facebook API
from facebook import GraphAPI


class YouTubeToFacebookBot:
    def __init__(self, config_file='config.json'):
        """Initialize the bot with configuration"""
        self.config_file = config_file
        self.load_config()
        self.posted_videos_file = 'posted_videos.json'
        self.posted_videos = self.load_posted_videos()
        
    def load_config(self):
        """Load configuration from environment variables or JSON file"""
        # Try environment variables first (for GitHub Actions)
        self.youtube_channel_id = os.getenv('YOUTUBE_CHANNEL_ID')
        self.facebook_page_id = os.getenv('FACEBOOK_PAGE_ID')
        self.facebook_access_token = os.getenv('FACEBOOK_ACCESS_TOKEN')
        self.hashtags = os.getenv('HASHTAGS', '#video #trending')
        
        # If env vars exist, we're in GitHub Actions
        if self.youtube_channel_id and self.facebook_page_id and self.facebook_access_token:
            self.youtube_channel_url = f"https://www.youtube.com/channel/{self.youtube_channel_id}"
            self.check_interval = 900  # 15 minutes for GitHub Actions
            self.download_path = './downloads'
            print("✅ Running in GitHub Actions mode")
            return
        
        # Otherwise, try config file (for local use)
        if not os.path.exists(self.config_file):
            print(f"❌ Config file '{self.config_file}' not found!")
            print("Creating template config file...")
            self.create_template_config()
            raise Exception("Please fill in the config.json file with your details")
        
        with open(self.config_file, 'r') as f:
            config = json.load(f)
        
        self.youtube_channel_url = config.get('youtube_channel_url')
        self.youtube_channel_id = config.get('youtube_channel_id')
        self.facebook_page_id = config.get('facebook_page_id')
        self.facebook_access_token = config.get('facebook_access_token')
        self.hashtags = config.get('hashtags', '#video #trending')
        self.check_interval = config.get('check_interval_seconds', 300)
        self.download_path = config.get('download_path', './downloads')
        
        # Create download directory
        Path(self.download_path).mkdir(exist_ok=True)
        
    def create_template_config(self):
        """Create a template configuration file"""
        template = {
            "youtube_channel_url": "https://www.youtube.com/@channelname",
            "youtube_channel_id": "UC...",
            "facebook_page_id": "your-page-id",
            "facebook_access_token": "your-page-access-token",
            "hashtags": "#video #trending #viral #youtube #content",
            "check_interval_seconds": 300,
            "download_path": "./downloads"
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(template, f, indent=2)
        
        print(f"✅ Template config file created: {self.config_file}")
        
    def load_posted_videos(self):
        """Load the list of already posted videos"""
        if os.path.exists(self.posted_videos_file):
            with open(self.posted_videos_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_posted_videos(self):
        """Save the list of posted videos"""
        with open(self.posted_videos_file, 'w') as f:
            json.dump(self.posted_videos, f, indent=2)
    
    def get_channel_rss_url(self):
        """Get the RSS feed URL for the YouTube channel"""
        if self.youtube_channel_id:
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={self.youtube_channel_id}"
        else:
            raise Exception("YouTube channel ID is required in config")
    
    def check_for_new_videos(self):
        """Check YouTube RSS feed for new videos"""
        print(f"🔍 Checking for new videos at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        rss_url = self.get_channel_rss_url()
        feed = feedparser.parse(rss_url)
        
        new_videos = []
        
        for entry in feed.entries:
            video_id = entry.yt_videoid
            video_url = entry.link
            video_title = entry.title
            published = entry.published
            
            # Check if already posted
            if video_id not in self.posted_videos:
                new_videos.append({
                    'video_id': video_id,
                    'url': video_url,
                    'title': video_title,
                    'published': published
                })
                print(f"  📹 New video found: {video_title}")
        
        return new_videos
    
    def download_video_and_thumbnail(self, video_url, video_id):
        """Download video and thumbnail using yt-dlp"""
        print(f"⬇️  Downloading video: {video_url}")
        
        video_path = os.path.join(self.download_path, f"{video_id}.mp4")
        thumbnail_path = os.path.join(self.download_path, f"{video_id}_thumb.jpg")
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': video_path.replace('.mp4', '.%(ext)s'),
            'writethumbnail': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'quiet': False,
            'no_warnings': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                
                # Find the downloaded thumbnail
                for ext in ['.jpg', '.webp', '.png']:
                    temp_thumb = video_path.replace('.mp4', ext)
                    if os.path.exists(temp_thumb):
                        os.rename(temp_thumb, thumbnail_path)
                        break
                
                # Ensure video has .mp4 extension
                if not os.path.exists(video_path):
                    # Check for the actual downloaded file
                    base = video_path.replace('.mp4', '')
                    for ext in ['.mp4', '.mkv', '.webm']:
                        if os.path.exists(base + ext):
                            if ext != '.mp4':
                                os.rename(base + ext, video_path)
                            break
                
                return video_path, thumbnail_path, info
                
        except Exception as e:
            print(f"❌ Error downloading video: {e}")
            return None, None, None
    
    def upload_to_facebook(self, video_path, thumbnail_path, title):
        """Upload video to Facebook page"""
        print(f"📤 Uploading to Facebook...")
        
        try:
            graph = GraphAPI(access_token=self.facebook_access_token)
            
            # Create the description with title and hashtags from config
            description = f"{title}\n\n{self.hashtags}"
            
            print(f"  📝 Using hashtags: {self.hashtags}")
            
            # Upload video
            with open(video_path, 'rb') as video_file:
                response = graph.put_video(
                    video=video_file,
                    description=description,
                    title=title
                )
            
            post_id = response.get('id')
            print(f"  ✅ Video uploaded successfully! Post ID: {post_id}")
            
            return post_id
            
        except Exception as e:
            print(f"❌ Error uploading to Facebook: {e}")
            return None
    
    def process_video(self, video_info):
        """Process a single video: download and upload"""
        video_id = video_info['video_id']
        video_url = video_info['url']
        video_title = video_info['title']
        
        print(f"\n{'='*60}")
        print(f"Processing: {video_title}")
        print(f"{'='*60}")
        
        # Download video and thumbnail
        video_path, thumbnail_path, yt_info = self.download_video_and_thumbnail(video_url, video_id)
        
        if not video_path:
            print("❌ Failed to download video, skipping...")
            return False
        
        # Upload to Facebook with static hashtags
        post_id = self.upload_to_facebook(video_path, thumbnail_path, video_title)
        
        if post_id:
            # Mark as posted
            self.posted_videos[video_id] = {
                'title': video_title,
                'posted_at': datetime.now().isoformat(),
                'facebook_post_id': post_id,
                'url': video_url
            }
            self.save_posted_videos()
            
            # Clean up downloaded files
            try:
                os.remove(video_path)
                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
                print("🗑️  Cleaned up downloaded files")
            except Exception as e:
                print(f"⚠️  Could not delete files: {e}")
            
            print(f"✅ Successfully processed and posted: {video_title}\n")
            return True
        else:
            print(f"❌ Failed to post video to Facebook\n")
            return False
    
    def run_once(self):
        """Run one check cycle"""
        try:
            new_videos = self.check_for_new_videos()
            
            if not new_videos:
                print("  ℹ️  No new videos found")
                return
            
            print(f"  📹 Found {len(new_videos)} new video(s)")
            
            # Process each new video
            for video_info in new_videos:
                self.process_video(video_info)
                
        except Exception as e:
            print(f"❌ Error in run cycle: {e}")
    
    def run_forever(self):
        """Run the bot continuously"""
        print("🤖 YouTube to Facebook Automation Bot Started!")
        print(f"📺 Monitoring: {self.youtube_channel_url}")
        print(f"📱 Posting to Facebook Page: {self.facebook_page_id}")
        print(f"⏱️  Check interval: {self.check_interval} seconds")
        print(f"{'='*60}\n")
        
        while True:
            try:
                self.run_once()
                print(f"\n⏳ Waiting {self.check_interval} seconds until next check...\n")
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                print("\n\n👋 Bot stopped by user")
                break
            except Exception as e:
                print(f"❌ Unexpected error: {e}")
                print(f"⏳ Waiting {self.check_interval} seconds before retry...\n")
                time.sleep(self.check_interval)


def main():
    """Main entry point"""
    bot = YouTubeToFacebookBot()
    # For GitHub Actions, run once per execution
    if os.getenv('GITHUB_ACTIONS'):
        bot.run_once()
    else:
        # For local/server deployment, run forever
        bot.run_forever()


if __name__ == "__main__":
    main()
