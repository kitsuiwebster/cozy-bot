import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands
from reactions.reactions import handle_reactions
from datetime import datetime
import json

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

# Function to save voice channel time data to a file
def save_voice_time_data():
    with open('voice_time_data.json', 'w') as file:
        json.dump(guild_voice_time, file)

# Function to load voice channel time data from a file
def load_voice_time_data():
    try:
        with open('voice_time_data.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Initialize a dictionary to store voice channel time for each guild
guild_voice_time = load_voice_time_data()

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

# Event handler for voice state updates
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return

    guild_id = str(member.guild.id)  # Convert to string for JSON compatibility

    # Check if the bot has joined a voice channel
    if before.channel is None and after.channel is not None:
        # Record the start time
        guild_voice_time[guild_id] = [datetime.now().isoformat(), guild_voice_time.get(guild_id, [None, 0])[1]]

    # Check if the bot has left a voice channel
    elif before.channel is not None and after.channel is None:
        if guild_id in guild_voice_time and guild_voice_time[guild_id][0] is not None:
            start_time = datetime.fromisoformat(guild_voice_time[guild_id][0])
            accumulated_time = guild_voice_time[guild_id][1]
            time_spent = datetime.now() - start_time
            total_time = accumulated_time + time_spent.total_seconds()
            guild_voice_time[guild_id] = [None, total_time]
            print(f"Time spent in {before.channel.guild.name}: {total_time} seconds")
            save_voice_time_data() 

bot_alone_time = {}

# Coroutine to check if the bot is alone in a voice channel
async def leave_voice_channel_if_alone():
    await bot.wait_until_ready()
    while not bot.is_closed():
        for vc in bot.voice_clients:
            if vc.guild.id not in bot_alone_time:
                # If the bot is alone in the voice channel, start tracking
                if len(vc.channel.members) == 1:
                    bot_alone_time[vc.guild.id] = datetime.now()
            else:
                # Check if the bot has been alone for more than 30 minutes
                if len(vc.channel.members) == 1
                    alone_since = bot_alone_time[vc.guild.id]
                    if (datetime.now() - alone_since).total_seconds() > 1800:
                        await vc.disconnect()
                        del bot_alone_time[vc.guild.id]  
                        print(f"Left voice channel in {vc.guild.name} due to being alone for 30 minutes.")
                else:
                    # If not alone anymore, stop tracking
                    if vc.guild.id in bot_alone_time:
                        del bot_alone_time[vc.guild.id]
        await asyncio.sleep(60) 


# Event handler for when the bot is ready and has started.
@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected !!')
    bot.heartbeat_interval = 360
    bot.loop.create_task(change_status())
    bot.loop.create_task(leave_voice_channel_if_alone())

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
        bot.load_extension('commands.top')

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
        save_voice_time_data()
    finally:
        loop.close()
