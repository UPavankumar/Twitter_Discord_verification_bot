import discord
from discord.ext import commands, tasks
import tweepy
import os
import tempfile
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import asyncio

# Load environment variables from the .env file
load_dotenv()

# Initialize the Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Twitter API keys
consumer_key = os.getenv('TWITTER_CONSUMER_KEY')
consumer_secret = os.getenv('TWITTER_CONSUMER_SECRET')

# Discord bot token
discord_bot_token = os.getenv('DISCORD_BOT_TOKEN')

# Create a temporary file to store the OAuth verifier
temp_oauth_verifier_file = tempfile.NamedTemporaryFile(delete=False)

# OAuth initialization
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)

# Get the Twitter verified role ID from the .env file
ROLE_ID = int(os.getenv('TWITTER_VERIFIED_ROLE_ID'))

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    print("Use !twitter_login to initiate Twitter authentication on this server.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.content.lower() in ['hi', 'hello']:
        await message.channel.send(f"Hello! I am the Twitter bot. Use !twitter_login to initiate Twitter authentication.")

    await bot.process_commands(message)

@bot.command(
    name='twitter_login',
    brief='Initiate Twitter authentication',
    description='Generates a Twitter authorization URL. Click the link to log in to Twitter and start the authentication process.'
)
async def twitter_login(ctx):
    try:
        user_name = ctx.author.name
        redirect_url = auth.get_authorization_url()
        await ctx.send(f"{user_name}, click this link to log in to Twitter: {redirect_url}")

        # Instruct the user to copy the URL and use !verify
        await asyncio.sleep(2)
        await ctx.send(f"Copy the URL and type `!verify \"{redirect_url}\"` to complete the authentication.")

        server_name = ctx.guild.name
        print(f"{user_name} has started Twitter verification on the '{server_name}' server.")
    except tweepy.TweepError as e:
        await ctx.send(f"Error generating authorization URL: {str(e)}")

class TwitterCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global temp_oauth_verifier_file
        try:
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)
            oauth_verifier = query_params.get('oauth_verifier', [''])[0]

            if not oauth_verifier:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid OAuth URL. Make sure it contains the OAuth verifier.")
                return

            temp_oauth_verifier_file.write(oauth_verifier.encode())
            temp_oauth_verifier_file.close()

            user_name = self.headers.get('X-Discord-User', 'Unknown')

            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Twitter authentication successful. You can close this page.")

            print(f"{user_name} has completed Twitter authentication with OAuth verifier.")

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())
            print(f"Error during Twitter authentication callback: {str(e)}")

@bot.command()
async def verify(ctx, oauth_url):
    global temp_oauth_verifier_file
    try:
        parsed_url = urlparse(oauth_url)
        query_params = parse_qs(parsed_url.query)
        oauth_verifier = query_params.get('oauth_verifier', [''])[0]

        if not oauth_verifier:
            await ctx.send("Invalid OAuth URL. Make sure it contains the OAuth verifier.")
            return

        temp_oauth_verifier_file.write(oauth_verifier.encode())
        temp_oauth_verifier_file.close()

        user_name = ctx.author.name

        await ctx.send(f"Twitter authentication successful, {user_name}. You can now use Twitter features.")

        print(f"{user_name} has completed Twitter authentication with OAuth verifier.")

        twitter_verified_role = ctx.guild.get_role(ROLE_ID)
        if twitter_verified_role:
            await ctx.author.add_roles(twitter_verified_role)
            await ctx.send(f"{user_name}, you have been granted the 'Twitter_verified' role.")
        else:
            await ctx.send("The 'Twitter_verified' role is not properly configured.")

    except Exception as e:
        await ctx.send(f"Error completing Twitter authentication: {str(e)}")
        print(f"Error during Twitter authentication: {str(e)}")

def run_server():
    server_address = ('', 8080)
    httpd = HTTPServer(server_address, TwitterCallbackHandler)
    print(f"Started HTTP server on port 8080 for {httpd.server_name}...")
    httpd.serve_forever()

import threading
server_thread = threading.Thread(target=run_server)
server_thread.start()

bot.run(discord_bot_token)
