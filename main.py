import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands
from reactions.reactions import handle_reactions

# Load environment variables from a .env file.
load_dotenv()
# Configure logging with an info level
logging.basicConfig(level=logging.INFO)

# Set up Discord intents for the bot.
intents = discord.Intents.default()
intents.typing = False
intents.members = True
intents.message_content = True
intents.guilds = True

# Initialize the bot with a command prefix and the specified intents.
bot = commands.Bot(command_prefix="/", intents=intents)

# Print the list of guilds the bot is a member of.
print(bot.guilds)

# Coroutine to change the bot's status periodically.
async def change_status():
    await bot.wait_until_ready()

    while not bot.is_closed():
        server_count = len(bot.guilds)
        total_member_count = sum(guild.member_count for guild in bot.guilds)
        statuses = [
            discord.Game(name=f"in {server_count} servers"),
            discord.Game(name=f"with {total_member_count} members"),
        ]

        # Cycle through the statuses and set the bot's presence.
        for status in statuses:
            await bot.change_presence(activity=status)
            await asyncio.sleep(10)

# Event handler for any errors that occur.
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"An error occurred: {event}")


# Event handler for when the bot is ready and has started.
@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected !!')
    bot.heartbeat_interval = 360
    bot.loop.create_task(change_status())

    # Print total members and servers.
    server_count = len(bot.guilds)
    total_member_count = sum(guild.member_count for guild in bot.guilds)
    print(f'Total members: {total_member_count}, total servers {server_count}')
    print("Cozy Bot's servers")
    for guild in bot.guilds:
        print(f"{guild.name}")

# Event handler for processing messages.
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

    await handle_reactions(message)

# Function to run the bot.
async def run_bot():
    try:
        # Load extensions for the bot.
        bot.load_extension('commands.rain')
        bot.load_extension('commands.sparkles')
        # bot.load_extension('commands.ambient')

    except Exception as e:
        print(f"Error loading extension: {e}")

    # Start the bot with the token from the environment variable.
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    await bot.start(bot_token)


# Main entry point of the script.
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        print("---> Bot stopped by user.")
    finally:
        loop.close()
