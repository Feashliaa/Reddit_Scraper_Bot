# Description:
# This file contains the core logic for the Reddit scraper bot.
# This one specifically just uses web scraping to get the posts from Reddit, doesn't use the Reddit API.
# So this one doesn't work as well as the other one, but it's still functional usually.
# It uses Selenium to scrape posts from Reddit and sends the results to a Discord channel using webhooks.
# The bot can be run in the CLI or as a Discord bot.
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
from urllib.parse import urlparse, urljoin
from azure.keyvault.secrets import SecretClient
from azure.identity import ManagedIdentityCredential, DefaultAzureCredential
from selenium_stealth import stealth
import logging
import sys
import asyncio
import time
import requests
import re
import os
import discord
import logging
import subprocess
import undetected_chromedriver as uc
import praw
import random

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# check if being ran by a docker container
if os.getenv("CHECK_ENV"):
    # Running in a CLI or local environment

    # Load environment variables from a .env file
    load_dotenv()

    # Discord token and webhook URLs from local environment variables
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    WEBHOOK = os.getenv("WEBHOOK")
    
    print("DISCORD_TOKEN FROM CLI:", DISCORD_TOKEN)
    print("WEBHOOK FROM CLI:", WEBHOOK)
    
else:
    # Running in a web server environment (e.g., Azure App Service, Heroku)

    # Azure Key Vault URL
    vault_url = "https://FeashDiscordBot.vault.azure.net"

    # Create a secret client
    logger = logging.getLogger("azure.identity")
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter("[%(levelname)s %(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    credential = DefaultAzureCredential()  # ManagedIdentityCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)

    # Retrieve secrets from Azure Key Vault
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    WEBHOOK = os.getenv("WEBHOOK")

    print("DISCORD_TOKEN:", DISCORD_TOKEN)
    print("WEBHOOK:", WEBHOOK)

# Function to sanitize the filename of the image or video scraped from Reddit
def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "_", filename)

class ScraperBot:
    post_urls = {}  # Dictionary to store post URLs

    def __init__(self):
        
        
        # Fetch proxies
        http_proxies_response = requests.get('https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=10000&country=all&ssl=all&anonymity=all')
        http_proxies = http_proxies_response.text.split('\n')
        https_proxies_response = requests.get('https://api.proxyscrape.com/?request=getproxies&proxytype=https&timeout=10000&country=all&ssl=all&anonymity=all')
        https_proxies = https_proxies_response.text.split('\n')

        # Select a proxy
        selected_proxy = http_proxies[0].strip()

        # Set up proxy
        proxy = Proxy()
        proxy.proxy_type = ProxyType.MANUAL
        proxy.http_proxy = selected_proxy
        proxy.ssl_proxy = selected_proxy
        
        # original scraperbot code
        # set up selenium options for headless browsing
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-software-rasterizer")
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
        ]

        options.add_argument(f"user-agent={random.choice(user_agents)}")
        
        # Set up desired capabilities with proxy
        capabilities = DesiredCapabilities.CHROME.copy()
        capabilities['proxy'] = {
            "proxyType": "MANUAL",
            "httpProxy": selected_proxy,
            "sslProxy": selected_proxy,
        }
        
        # Initialize the undetected Chrome driver
        self.driver = uc.Chrome(options=options, desired_capabilities=capabilities)

        # Apply Selenium Stealth settings
        stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True
                )

        # Set up the Discord bot with specific intents
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.bot)

        # IMPORTANT: Change the subreddits to scrape here to whatever you want
        self.subreddits = {
            1: "https://www.reddit.com/r/memes/top/",
            2: "https://www.reddit.com/r/combatfootage/top/",
            3: "https://www.reddit.com/r/greentext/top/",
            4: "https://www.reddit.com/r/dankmemes/top/",
            5: "https://www.reddit.com/r/pics/top/",
        }

        self.setup_bot_commands()

    def setup_bot_commands(self):

        @app_commands.describe(
            subreddit_number="The number of the subreddit to scrape",
            num_posts="The number of posts to scrape (default: 1)",
        )

        # Define the scrape command
        @self.tree.command(name="scrape", description="Scrape posts from a subreddit")
        async def scrape_command(
            interaction: discord.Interaction, subreddit_number: int, num_posts: int = 1
        ):
            if subreddit_number in self.subreddits:
                subreddit_url = self.subreddits[subreddit_number]

                await interaction.response.defer()

                await interaction.followup.send(
                    f"Starting to scrape {num_posts} posts from: {subreddit_url}"
                )

                await self.scrape_subreddit(interaction, subreddit_url, num_posts)

            else:

                await interaction.response.send_message(
                    "Invalid subreddit number. Please choose a number between 1 and 5."
                )

        # Define the list_subreddits command
        @self.tree.command(
            name="list_subreddits", description="List available subreddits"
        )
        async def list_subreddits(interaction: discord.Interaction):
            subreddit_list = "\n".join(
                [f"{k}. {v.split('/')[4]}" for k, v in self.subreddits.items()]
            )
            await interaction.response.send_message(
                f"Available subreddits to scrape:\n{subreddit_list}"
            )

        # Define the scrape_custom command
        @self.tree.command(
            name="scrape_custom", description="Scrape posts from a custom subreddit"
        )
        async def scrape_custom_command(
            interaction: discord.Interaction, subreddit_name: str, num_posts: int = 1
        ):
            subreddit_url = f"https://www.reddit.com/r/{subreddit_name}/top/"
            subreddit_exists = False

            try:
                self.driver.get(subreddit_url)
                error_message_element = self.driver.find_element(
                    By.CLASS_NAME, "text-24"
                )
                error_message = error_message_element.text.strip()

                print(f"Error message found: '{error_message}'")

                if "community not found" in error_message.lower():
                    subreddit_exists = False  # Subreddit does not exist
                elif "is private" in error_message.lower():
                    subreddit_exists = False  # Subreddit is private
                elif "is banned" in error_message.lower():
                    subreddit_exists = False  # Subreddit is banned
                else:
                    subreddit_exists = True  # Subreddit exists

            except NoSuchElementException:
                print("Error message element not found.")
                subreddit_exists = (
                    True  # Assuming subreddit exists if error message element not found
                )
            except Exception as e:
                subreddit_exists = False
                print(f"Error checking subreddit existence: {e}")

            if not subreddit_exists:
                await interaction.response.send_message(
                    "Invalid subreddit name. Community not found. Please provide a valid subreddit name."
                )
                return
            try:
                modal = self.driver.find_element(By.ID, "wrapper")
                if modal.is_displayed():
                    secondary_button = modal.find_element(By.NAME, "secondaryButton")
                    if secondary_button:
                        secondary_button.click()
            except NoSuchElementException:
                pass  # No NSFW modal found or handled

            await interaction.response.defer()  # Acknowledge interaction

            await interaction.followup.send(
                f"Starting to scrape {num_posts} posts from: {subreddit_url}"
            )
            await self.scrape_subreddit(interaction, subreddit_url, num_posts)

    # Scrapes a subreddit and sends the results to the Discord channel
    async def scrape_subreddit(self, interaction, subreddit_url, num_posts):
        await self.get_top_posts(
            subreddit_url,
            num_posts,
            caller="discord_interaction",
            interaction=interaction,
        )

    # Function to get the subreddit from the user in the CLI
    def getSubredditCLI(self):
        print("Which subreddit would you like to scrape?")
        for key, value in self.subreddits.items():
            print(f"{key}. {value.split('/')[4]}")
        while True:
            subreddit = int(
                input("Enter the number of the subreddit you would like to scrape: ")
            )
            if subreddit in self.subreddits:
                return self.subreddits[subreddit]
            else:
                print("Invalid input. Please enter a valid choice.")

    # Navigate to the subreddit URL
    def go_to_subreddit(self, subreddit):
        self.driver.get(subreddit)
        # Random delay
        time.sleep(random.uniform(2, 5))

    # Scroll down the page to load more posts
    def scroll_down(self):
        try:
            print("Scrolling down...")
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            print("Waiting for posts to load...")
                   # Random delay
            time.sleep(random.uniform(2, 5))
        except Exception as e:
            print(f"Error scrolling down: {e}")

    # Select the number of posts to scrape from the subreddit
    def select_posts(self, num_posts):
        try:
            posts = []  # List to store post URLs

            while (
                len(posts) < num_posts
            ):  # Keep scrolling until we have the desired number of posts

                article_elements = self.driver.find_elements(By.TAG_NAME, "article")
                print(f"Found {len(article_elements)} articles so far.")
                
                # get the whole html of the page
                html = self.driver.page_source
                
                print(html)
            
                for post in article_elements:

                    if len(posts) >= num_posts:  # If we have enough posts,
                        break
                    try:  # else, try to find the post link
                        link = post.find_element(By.CSS_SELECTOR, 'a[href^="/r/"]')
                        post_url = link.get_attribute("href")
                        if (
                            post_url not in posts
                        ):  # If the post is not already in the list, add it
                            posts.append(post_url)
                            print(f"Post {len(posts)}: {post_url}")
                    except Exception as e:
                        print(f"Error finding post link: {e}")

                if (
                    len(posts) < num_posts
                ):  # If we still don't have enough posts, scroll down
                    self.scroll_down()

            return posts
        except Exception as e:
            print(f"Error: {e}")

    async def send_to_discord_channel(self, title_payload, files, interaction):
        # check the channel the command was called from,
        # and send the message to that channel
        text_channel = (
            interaction.channel
        )  # get the channel the command was called from

        print(f"Sending message to channel: {text_channel}")

        # send the message with the title payload
        await text_channel.send(content=title_payload["content"])

        # send the files if there are any
        if files:
            for key, value in files.items():
                await text_channel.send(file=discord.File(value))
                files[key].close()

        return

    # Get the top posts from the subreddit
    async def get_top_posts(
        self, subreddit, num_posts=1, caller=None, interaction=None
    ):

        self.go_to_subreddit(subreddit)

        post_urls = self.select_posts(num_posts)

        for i, url in enumerate(post_urls):  # Loop through the post URLs
            self.post_urls[i] = url
            await self.get_post_content(url, caller, interaction)

    # Get the content of a specific post
    async def get_post_content(self, post_url, caller=None, interaction=None):
        print("Getting post content for", post_url)
        self.driver.get(post_url)

        try:
            title = self.driver.find_element(By.CSS_SELECTOR, "h1").text
            # sanitize the title, remove all non-alphanumeric characters, but keep spaces
            title = re.sub(r"[^a-zA-Z0-9 ]", "", title)
        except Exception as e:
            print(f"Error finding title: {e}")
            title = "No title found"

        print("Title:", title)

        image = None  # Initialize image variable
        try:  # Try to find the image
            image = self.driver.find_element(
                By.CSS_SELECTOR, 'img[alt^="r/"]'
            ).get_attribute("src")
        except:
            print("No image found.")

        video = None  # Initialize video variable
        try:  # Try to find the video
            video = self.driver.find_element(
                By.CSS_SELECTOR, "shreddit-player"
            ).get_attribute("src")
        except:
            print("No video found.")

        if image and not video:  # If we found an image but no video, process the image
            await self.process_image(image, title, caller, interaction)
        elif video and not image:  # If we found a video but no image, process the video
            await self.process_video(video, title, caller, interaction)
        else:
            print("No image or video found.")

    # Process the image and send it to the Discord channel
    async def process_image(self, image_url, title, caller=None, interaction=None):
        print("Image URL:", image_url)
        self.driver.get(image_url)
        image_filename = sanitize_filename(f"{title}.png")
        self.driver.save_screenshot(image_filename)

        title_payload = {"content": title}
        files = {"file": open(image_filename, "rb")}

        if caller == "cli_interaction":
            requests.post(WEBHOOK, files=files, data=title_payload)
        else:
            # handle sending to the discord channel the command was called from
            await self.send_to_discord_channel(title_payload, files, interaction)

        files["file"].close()
        os.remove(image_filename)

    async def process_video(self, video_url, title, caller=None, interaction=None):
        print("Video URL:", video_url)
        video_response = requests.get(video_url, stream=True)

        # Determine if the content is a BLOB
        content_type = video_response.headers.get("Content-Type")
        if (
            "application/vnd.apple.mpegurl" in content_type
            or "application/x-mpegurl" in content_type
        ):
            # Handle M3U8 playlist
            video_filename = sanitize_filename(f"{title}.mp4")

            ffmpeg_cmd = [
                "ffmpeg",
                "-i",
                video_url,
                "-c:v",
                "libx264",  # Video codec
                "-crf",
                "45",  # Constant Rate Factor (0-51, lower is better quality)
                "-preset",
                "veryfast",  # Preset for encoding speed vs. compression ratio
                "-max_muxing_queue_size",
                "1024",  # Max demux queue size
                "-c:a",
                "aac",  # Audio codec
                "-b:a",
                "128k",  # Audio bitrate
                "-bsf:a",
                "aac_adtstoasc",
                video_filename,
            ]

            try:
                subprocess.run(ffmpeg_cmd, check=True, timeout=300)  # 5-minute timeout
                logger.info(
                    f"Successfully downloaded and processed video: {video_filename}"
                )

                # check file size
                file_size = os.path.getsize(video_filename)
                if file_size == 0:
                    logger.error("Downloaded video file is empty")
                    return
                # else if file size is greater than 25mb, it cannot be sent to discord
                elif file_size > 25 * 1024 * 1024:
                    logger.error(
                        "Downloaded video file is too large to send to Discord"
                    )
                    # post to discord the title, and the url of the video
                    title_payload = {"content": title}

                    if caller == "cli_interaction":
                        requests.post(WEBHOOK, data=title_payload)
                    else:
                        # handle sending to the discord channel the command was called from
                        await self.send_to_discord_channel(
                            title_payload, None, interaction
                        )

            except subprocess.TimeoutExpired:
                logger.error("FFmpeg process timed out")
                return
            except subprocess.CalledProcessError as e:
                logger.error(f"Error processing video: {e}")
                return

        else:
            # Handle direct video download
            extension = os.path.splitext(urlparse(video_url).path)[1] or ".mp4"
            video_filename = sanitize_filename(f"{title}{extension}")

            with open(video_filename, "wb") as video_file:
                for chunk in video_response.iter_content(chunk_size=1024):
                    video_file.write(chunk)

        # Send video to Discord
        title_payload = {"content": title}
        files = {"file": open(video_filename, "rb")}

        if caller == "cli_interaction":
            requests.post(WEBHOOK, files=files, data=title_payload)
        else:
            # handle sending to the discord channel the command was called from
            await self.send_to_discord_channel(title_payload, files, interaction)

        files["file"].close()
        os.remove(video_filename)

    # Run the CLI interface
    def run_cli(self):
        subreddit = self.getSubredditCLI()
        num_posts = int(input("How many posts would you like to scrape? "))

        # Define an async function to run the CLI
        async def cli_helper():
            await self.get_top_posts(subreddit, num_posts, caller="cli_interaction")

        # Run the async function
        asyncio.run(cli_helper())

    # async commands
    async def sync_commands(self):
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(f"Failed to sync commands: {e}")

    # Run the Discord bot
    def run_discord(self):
        # Define the on_ready event
        @self.bot.event
        async def on_ready():
            await self.sync_commands()
            print(f"{self.bot.user} has connected to Discord!")
            print(f"Bot is active in {len(self.bot.guilds)} servers.")
            print("Ready to receive commands!")

            # Send a call to the webhook that the bot is ready
            try:
                webhook_message = {
                    "content": f"{self.bot.user} is ready to receive commands!"
                }
                requests.post(WEBHOOK, json=webhook_message)
            except Exception as e:
                print(f"Failed to send webhook message: {e}")

        self.bot.run(DISCORD_TOKEN)
