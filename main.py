import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands
from reactions import handle_reactions

load_dotenv()
logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.typing = False
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="/", intents=intents)
print(bot.guilds)

async def change_status():
    await bot.wait_until_ready()

    while not bot.is_closed():
        server_count = len(bot.guilds)
        total_member_count = sum(guild.member_count for guild in bot.guilds)
        statuses = [
            discord.Game(name=f"in {server_count} servers"),
            discord.Game(name=f"with {total_member_count} members"),
        ]

        for status in statuses:
            await bot.change_presence(activity=status)
            await asyncio.sleep(10)

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"An error occurred: {event}")



@bot.event
async def on_ready():
    print(f'{bot.user.name} is connected !!')
    bot.heartbeat_interval = 360
    bot.loop.create_task(change_status())

    server_count = len(bot.guilds)
    total_member_count = sum(guild.member_count for guild in bot.guilds)
    print(f'Total members: {total_member_count}, total servers {server_count}')
    print("Cozy Bot's servers")
    for guild in bot.guilds:
        print(f"{guild.name}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

    await handle_reactions(message)

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
