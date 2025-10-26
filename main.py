import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands
from cogs.reactions.reactions import handle_reactions
from datetime import datetime
import json
import asyncio
import fcntl

# Load environment variables from configuration file
load_dotenv()

# Configure enhanced logging system with visual formatting
import sys
class FancyFormatter(logging.Formatter):
    # ANSI terminal color codes for log formatting
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green  
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
        'RESET': '\033[0m'      # Reset
    }
    
    EMOJIS = {
        'DEBUG': '🔍',
        'INFO': '✅', 
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }
    
    def format(self, record):
        # Apply visual formatting to log record
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '📝')
        reset = self.COLORS['RESET']
        
        # Apply context-specific formatting based on logger namespace
        if 'discord.gateway' in record.name:
            emoji = '🌐'
        elif 'discord.voice' in record.name:
            emoji = '🎵'
        elif 'discord.player' in record.name:
            emoji = '🎶'
        elif 'discord.client' in record.name:
            emoji = '🤖'
            
        # Format timestamp for log entry
        timestamp = self.formatTime(record, '%H:%M:%S')
        
        # Generate formatted log message
        return f"{color}{emoji} [{timestamp}] {record.levelname:<8} {reset}{record.getMessage()}"

# Initialize enhanced logging system
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clear existing log handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Install custom log formatter
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(FancyFormatter())
logger.addHandler(handler)

# Configure Discord Gateway intents for bot permissions
intents = discord.Intents.default()
intents.typing = False
intents.members = False
intents.message_content = True
intents.guilds = True

# Initialize Discord bot instance with configuration
bot = commands.Bot(command_prefix="/", intents=intents)

# Debug: Display connected guilds (development only)
print(bot.guilds)

# Persist voice channel usage statistics to storage
def save_voice_time_data():
    data_file = 'data/voice_time_data.json'
    temp_file = data_file + '.tmp'
    
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    try:
        # Write to temporary file with exclusive lock
        with open(temp_file, 'w') as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            json.dump(guild_voice_time, file, indent=2)
            file.flush()
            os.fsync(file.fileno())
        
        # Atomic rename to final file
        os.rename(temp_file, data_file)
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_file):
            os.remove(temp_file)
        logging.error(f'Failed to save voice time data: {e}')

# Load voice channel usage statistics from persistent storage
def load_voice_time_data():
    data_file = 'data/voice_time_data.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        # Initialize with empty data if file doesn't exist
        return {}

# Initialize guild-specific voice channel usage tracking
guild_voice_time = load_voice_time_data()

# Background task for dynamic bot presence updates
async def change_status():
    await bot.wait_until_ready()

    while not bot.is_closed():
        server_count = len(bot.guilds)
        total_member_count = sum(guild.member_count for guild in bot.guilds)
        statuses = [
            discord.Game(name=f"in {server_count} servers"),
            discord.Game(name=f"with {total_member_count} members"),
        ]

        # Rotate through presence states with configured interval
        for status in statuses:
            await bot.change_presence(activity=status)
            await asyncio.sleep(10)

# Background task for periodic data backup
async def periodic_backup():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        # Save data every 5 minutes
        await asyncio.sleep(300)
        if guild_voice_time:
            save_voice_time_data()
            logging.info('💾 Periodic voice data backup completed')
        
        # Also save gamification data periodically
        try:
            from cogs.stats.gamification import cozy_gamification
            cozy_gamification.save_user_data()
            logging.info('💾 Periodic gamification data backup completed')
        except Exception as e:
            logging.error(f'💾 Failed to backup gamification data: {e}')

# Background task for periodic points update
async def periodic_points_update():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        # Update listening time points every 2 minutes
        await asyncio.sleep(120)
        
        # Update points for all active voice sessions
        for guild in bot.guilds:
            if guild.voice_client and guild.voice_client.is_playing():
                # Find the sound cog to update listening time
                for cog_name in ['RainCog', 'SeaCog', 'SparklesCog', 'BackgroundMusicCog']:
                    cog = bot.get_cog(cog_name)
                    if cog and hasattr(cog, 'update_listening_time'):
                        await cog.update_listening_time(guild.id)
                        break

# Global error handler for unhandled exceptions
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"An error occurred: {event}")

# Voice state change event handler for usage tracking
@bot.event
async def on_voice_state_update(member, before, after):
    if member.id != bot.user.id:
        return

    guild_id = str(member.guild.id)  # Convert to string for JSON compatibility

    # Track bot voice channel connection events
    if before.channel is None and after.channel is not None:
        # Initialize session timing for current connection
        guild_voice_time[guild_id] = [datetime.now().isoformat(), guild_voice_time.get(guild_id, [None, 0])[1]]

    # Process bot voice channel disconnection events
    elif before.channel is not None and after.channel is None:
        if guild_id in guild_voice_time and guild_voice_time[guild_id][0] is not None:
            start_time = datetime.fromisoformat(guild_voice_time[guild_id][0])
            accumulated_time = guild_voice_time[guild_id][1]
            time_spent = datetime.now() - start_time
            total_time = accumulated_time + time_spent.total_seconds()
            guild_voice_time[guild_id] = [None, total_time]
            print(f"Time spent in {before.channel.guild.name}: {total_time} seconds")
            save_voice_time_data() 

# Bot ready event handler - initialization complete
@bot.event
async def on_ready():
    logging.info(f'🎉 {bot.user.name} is ready and connected!')
    
    # Synchronize application commands with Discord API
    try:
        logging.info('🔄 Syncing application commands...')
        synced = await bot.tree.sync()
        logging.info(f'✅ Synced {len(synced)} application commands!')
    except Exception as e:
        logging.error(f'💥 Error syncing commands: {e}')
    
    logging.info('🚀 Bot startup complete - All systems operational')
    
    bot.heartbeat_interval = 360
    bot.loop.create_task(change_status())
    bot.loop.create_task(periodic_backup())
    bot.loop.create_task(periodic_points_update())

    # Log bot deployment statistics and connected guilds
    server_count = len(bot.guilds)
    total_member_count = sum(guild.member_count for guild in bot.guilds)
    logging.info(f'📊 Serving {total_member_count:,} members across {server_count} servers')
    logging.info('🏠 Connected servers:')
    for guild in bot.guilds:
        logging.info(f'   └─ {guild.name} ({guild.member_count:,} members)')

# Message processing event handler
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

    await handle_reactions(message)

# Bot initialization and startup routine
async def run_bot():
    try:
        # Load bot command modules and register extensions
        extensions = [
            ('cogs.audio.rain.rain', '🌧️'),
            ('cogs.audio.sea.sea', '🌊'), 
            ('cogs.audio.sparkles.sparkles', '✨'),
            ('cogs.audio.background_music.background-music', '🎵'),
            ('cogs.audio.stop', '🛑'),
            ('cogs.stats.profile', '🏅'),
            ('cogs.stats.tops', '🏆'),
            ('cogs.stats.total', '📊')
        ]
        
        logging.info('🔧 Loading bot extensions...')
        for ext_name, emoji in extensions:
            await bot.load_extension(ext_name)
            # Add extra space for emojis that take 2 characters
            space = '  ' if emoji == '🌧️' else ' '
            logging.info(f'   {emoji}{space} {ext_name} loaded successfully')
        
    except Exception as e:
        logging.error(f'💥 Error loading extension: {e}')

    # Initialize bot connection using authentication token
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    await bot.start(bot_token)

# Application entry point - bot startup sequence
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        print("---> Bot stopped by user.")
        # Save all data on graceful shutdown
        save_voice_time_data()
        try:
            from cogs.stats.gamification import cozy_gamification
            cozy_gamification.save_user_data()
            logging.info('💾 Gamification data saved on shutdown')
        except Exception as e:
            logging.error(f'💾 Failed to save gamification data on shutdown: {e}')
    finally:
        loop.close()