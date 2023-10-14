import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands

# Load environment variables from .env file
load_dotenv()
logging.basicConfig(level=logging.INFO)

# Define the intents you need for your bot
intents = discord.Intents.default()
intents.typing = False
# intents.message_content = True

# Initialize Poof Poof
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected !!')
    bot.heartbeat_interval = 360

@bot.event
async def on_message(message):
    # Avoid responding to the bot's own messages
    if message.author == bot.user:
        return
    await bot.process_commands(message)

async def change_status():
    await bot.wait_until_ready()

    while not bot.is_closed():
        discord.Game("🌧️"),

async def run_bot():
    try:
        bot.load_extension('commands.rain')

    except Exception as e:
        print(f"Error loading extension: {e}")

    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    await bot.start(bot_token)


if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        print("---> Bot stopped by user.")
    finally:
        loop.close()
