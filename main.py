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
import aiohttp

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
        'DEBUG': '⚙️',
        'INFO': '✨', 
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }
    
    def format(self, record):
        # Apply visual formatting to log record
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '📝')
        reset = self.COLORS['RESET']
        
            
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
intents.voice_states = True  # Required to track user voice channel changes

# Initialize Discord bot instance with configuration
bot = commands.Bot(command_prefix="/", intents=intents)

# Debug: Display connected guilds (development only)
logging.debug(f"⚔️ Bot guilds: {bot.guilds}")

# Persist voice channel usage statistics to storage
def format_duration(seconds):
    """Format duration in seconds to human readable format"""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{minutes}m {secs}s"
        return f"{minutes}m"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        if secs > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{hours}h {minutes}m"
        return f"{hours}h"

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
        logging.info('✅ Voice time data saved successfully')
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_file):
            os.remove(temp_file)
        logging.error(f'❌ Failed to save voice time data: {e}')

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

# Initialize user voice session tracking - with accumulated time
user_voice_sessions = {}  # {guild_id: {bot_start_time: datetime, users: {user_id: {join_time: datetime, accumulated_time: float}}}}

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

# Background task for hourly data backup
async def periodic_backup():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        # Full backup every 10 minutes
        await asyncio.sleep(600)  # 10 minutes
        
        try:
            from cogs.stats.gamification import cozy_gamification
            
            logging.info("🕐 PERIODIC BACKUP: Starting complete data backup...")
            
            # Save voice time data for all servers
            if guild_voice_time:
                save_voice_time_data()
                logging.info("✅ Voice time data saved for all servers")
            
            # Save gamification data (users, points, achievements, etc.) with detailed logging
            cozy_gamification.save_user_data(force_detailed_log=True)
            
            logging.info("✅ PERIODIC BACKUP: Complete backup finished")
            
        except Exception as e:
            logging.error(f"❌ PERIODIC BACKUP FAILED: {e}")
        
        # Save current stats for API
        save_current_stats_for_api()
def save_current_stats_for_api():
    """Save current bot stats for API access"""
    try:
        total_people_with_bot = 0
        servers_with_bot = 0
        
        for guild in bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                servers_with_bot += 1
                for member in voice_state.channel.members:
                    if member != bot.user:
                        total_people_with_bot += 1
        
        stats = {
            'current_listeners': total_people_with_bot,
            'servers_with_bot': servers_with_bot,
            'total_servers': len(bot.guilds),
            'last_updated': datetime.now().isoformat()
        }
        
        os.makedirs('data', exist_ok=True)
        with open('data/current_stats.json', 'w') as f:
            json.dump(stats, f, indent=2)
            
    except Exception as e:
        logging.error(f'❌ Failed to save current stats: {e}')

# API endpoints health check function
async def check_api_endpoints():
    """Check all API endpoints health during bot initialization"""
    # Determine API base URL (try HTTPS first, fallback to HTTP)
    api_base = "https://localhost:8000"
    api_base_http = "http://localhost:8000"
    
    endpoints = [
        "/",
        "/health", 
        "/api/total",
        "/api/top-users",
        "/api/top-sounds", 
        "/api/top-servers"
    ]
    
    logging.info("⚙️ Checking API endpoints...")
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
        for endpoint in endpoints:
            try:
                # Try HTTPS first
                async with session.get(f"{api_base}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        logging.info(f"✨ {endpoint} - healthy")
                    else:
                        logging.error(f"🔥 {endpoint} - error (status: {response.status})")
            except:
                try:
                    # Fallback to HTTP
                    async with session.get(f"{api_base_http}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            logging.info(f"✅ {endpoint} - healthy")
                        else:
                            logging.error(f"❌ {endpoint} - error (status: {response.status})")
                except:
                    logging.error(f"❌ {endpoint} - error")


# Global error handler for unhandled exceptions
@bot.event
async def on_error(event, *args, **kwargs):
    logging.error(f"An error occurred: {event}")

# Voice state change event handler for usage tracking
@bot.event
async def on_voice_state_update(member, before, after):
    # Handle bot voice channel tracking (existing server functionality - keep unchanged)
    if member.id == bot.user.id:
        guild_id = str(member.guild.id)

        # Bot joined a voice channel
        if before.channel is None and after.channel is not None:
            # Initialize server session timing
            guild_voice_time[guild_id] = [datetime.now().isoformat(), guild_voice_time.get(guild_id, [None, 0])[1]]
            
            # Cache server name
            from cogs.stats.gamification import cozy_gamification
            cozy_gamification.update_servername(guild_id, member.guild.name)
            
            # Start user tracking session for this guild
            user_voice_sessions[guild_id] = {
                'bot_start_time': datetime.now(),
                'users': {}
            }
            
            # Note all users currently in the channel
            from cogs.stats.gamification import cozy_gamification
            current_users = [m for m in after.channel.members if not m.bot]
            logging.info(f"👉 BOT JOIN: Connected to {after.channel.name} in {member.guild.name} - {len(current_users)} users already present")
            for user in current_users:
                user_id = str(user.id)
                user_voice_sessions[guild_id]['users'][user_id] = {
                    'join_time': datetime.now(),
                    'accumulated_time': 0.0
                }
                # Award session join points - pass both username and display_name
                result = cozy_gamification.join_session(user_id, user.name)  # real username
                cozy_gamification.update_username(user_id, user.name, user.global_name or user.display_name)
                logging.info(f"👉 USER JOIN: {user.name} was already in channel when bot joined {after.channel.name} in {member.guild.name}")

        # Bot left a voice channel
        elif before.channel is not None and after.channel is None:
            # Handle server timing (existing)
            if guild_id in guild_voice_time and guild_voice_time[guild_id][0] is not None:
                start_time = datetime.fromisoformat(guild_voice_time[guild_id][0])
                accumulated_time = guild_voice_time[guild_id][1]
                time_spent = datetime.now() - start_time
                session_duration = time_spent.total_seconds()
                total_time = accumulated_time + session_duration
                guild_voice_time[guild_id] = [None, total_time]
                logging.info(f"👋 BOT DISCONNECT: Left {before.channel.guild.name} - session: +{format_duration(session_duration)}, server total: {format_duration(total_time)}")
                logging.info(f"🏠 +{format_duration(session_duration)} pour {before.channel.guild.name}")
                save_voice_time_data()
            
            # Calculate final listening time for all remaining users
            if guild_id in user_voice_sessions:
                from cogs.stats.gamification import cozy_gamification
                session = user_voice_sessions[guild_id]
                
                for user_id, user_data in session['users'].items():
                    # Get username for logging
                    try:
                        user = await bot.fetch_user(int(user_id))
                        username = user.name if user else f"User {user_id[:8]}"
                    except:
                        username = f"User {user_id[:8]}"
                    
                    # Calculate final session time
                    final_duration = (datetime.now() - user_data['join_time']).total_seconds()
                    total_session_time = user_data['accumulated_time'] + final_duration
                    
                    if final_duration > 0:
                        result = cozy_gamification.add_listening_time(user_id, final_duration)
                        points_to_add = result['points_added'] if result else int(final_duration / 60)
                        logging.info(f"👋 BOT DISCONNECT: {username} final session - total: {format_duration(total_session_time)}, final chunk: {format_duration(final_duration)}, +{points_to_add} points")
                
                # Clean up session
                del user_voice_sessions[guild_id]
        return

    # Handle user voice channel changes (when bot is present)
    if member.bot:
        return
    
    guild_id = str(member.guild.id)
    user_id = str(member.id)
    
    # Only track if bot is currently in a voice channel in this guild
    if guild_id not in user_voice_sessions:
        return
    
    bot_voice_client = member.guild.voice_client
    bot_channel = bot_voice_client.channel if bot_voice_client else None
    
    if not bot_channel:
        return
    
    from cogs.stats.gamification import cozy_gamification
    session = user_voice_sessions[guild_id]
    
    # User joined the bot's channel
    if after.channel == bot_channel and before.channel != bot_channel:
        session['users'][user_id] = {
            'join_time': datetime.now(),
            'accumulated_time': 0.0
        }
        result = cozy_gamification.join_session(user_id, member.name)  # real username
        cozy_gamification.update_username(user_id, member.name, member.global_name or member.display_name)
        logging.info(f"✅ USER JOIN: {member.name} joined bot channel {after.channel.name} in {member.guild.name}")
    
    # User left the bot's channel  
    elif before.channel == bot_channel and after.channel != bot_channel:
        if user_id in session['users']:
            user_data = session['users'][user_id]
            final_duration = (datetime.now() - user_data['join_time']).total_seconds()
            total_session_time = user_data['accumulated_time'] + final_duration
            
            if final_duration > 0:
                result = cozy_gamification.add_listening_time(user_id, final_duration)
                points_to_add = result['points_added'] if result else int(final_duration / 60)
                logging.info(f"👋 USER LEAVE: {member.name} left bot channel {before.channel.name} in {member.guild.name} - total: {format_duration(total_session_time)}, final chunk: {format_duration(final_duration)}, +{points_to_add} points")
            else:
                logging.info(f"👋 USER LEAVE: {member.name} left bot channel {before.channel.name} in {member.guild.name} - no additional time")
            
            # Finalize sound tracking when user leaves
            cozy_gamification.finalize_current_sound(user_id)
            logging.info(f"👉 SOUND TRACKING: Finalized current sound for {member.name}")
            
            # Remove user from session
            del session['users'][user_id] 

# Bot ready event handler - initialization complete
@bot.event
async def on_ready():
    # Display bot header
    print("\n" + "="*60)
    print("╔═════════════════════════════════════════════════════════════════╗")
    print("║                                                                 ║")
    print("║   ██████╗ ██████╗ ███████╗██╗   ██╗██████╗  ██████╗ ████████╗   ║")
    print("║  ██╔════╝██╔═══██╗╚══███╔╝╚██╗ ██╔╝██╔══██╗██╔═══██╗╚══██╔══╝   ║")
    print("║  ██║     ██║   ██║  ███╔╝  ╚████╔╝ ██████╔╝██║   ██║   ██║      ║")
    print("║  ██║     ██║   ██║ ███╔╝    ╚██╔╝  ██╔══██╗██║   ██║   ██║      ║")
    print("║  ╚██████╗╚██████╔╝███████╗   ██║   ██████╔╝╚██████╔╝   ██║      ║")
    print("║   ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═════╝  ╚═════╝    ╚═╝      ║")
    print("║                                                                 ║")
    print("║                      Version 1.0.10                             ║")
    print("║            by @kitsuiwebster & @BubbleXGum                      ║")
    print("║                                                                 ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print("="*60 + "\n")
    
    # Set bot instance for API access
    try:
        from api.routes.stats import set_bot_instance
        set_bot_instance(bot)
        logging.info('🔗 Bot instance shared with API for LIVE access')
    except Exception as e:
        logging.warning(f'⚠️ Could not share bot instance with API: {e}')
    
    logging.info(f'🎉 {bot.user.name} is ready and connected!')
    
    # Synchronize application commands with Discord API
    try:
        logging.info('🔄 Syncing application commands...')
        synced = await bot.tree.sync()
        logging.info(f'✅ Synced {len(synced)} application commands!')
    except Exception as e:
        logging.error(f'❌ Error syncing commands: {e}')
    
    logging.info('🚀 Bot startup complete - All systems operational')
    
    # Check API endpoints health
    await check_api_endpoints()
    
    bot.heartbeat_interval = 360
    bot.loop.create_task(change_status())
    bot.loop.create_task(periodic_backup())

    # Log bot deployment statistics and connected guilds
    server_count = len(bot.guilds)
    total_member_count = sum(guild.member_count for guild in bot.guilds)
    logging.info(f'👉 Serving {total_member_count:,} members across {server_count} servers')
    logging.info('🏠 Connected servers:')
    for guild in bot.guilds:
        logging.info(f'   ╰┈➤ {guild.name} ({guild.member_count:,} members)')

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
            ('cogs.stats.total', '📊'),
            ('cogs.stats.stats_command', '📈'),
            ('cogs.notifications.startup_message', '📢')
        ]
        
        logging.info('🔧 Loading bot extensions...')
        for ext_name, emoji in extensions:
            await bot.load_extension(ext_name)
            # Add extra space for emojis that take 2 characters
            space = '  ' if emoji == '🌧️' else ' '
            logging.info(f'✅️ {emoji}{space} {ext_name} loaded successfully')
        
    except Exception as e:
        logging.error(f'❌ Error loading extension: {e}')

    # Initialize bot connection using authentication token
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if not bot_token:
        logging.critical('💥 Discord token not found in environment variables')
        return
    
    try:
        await bot.start(bot_token)
    except Exception as e:
        logging.critical(f'💥 Failed to start bot: {e}')
        raise

# Application entry point - bot startup sequence
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user.")
        # Save all data on graceful shutdown
        save_voice_time_data()
        try:
            from cogs.stats.gamification import cozy_gamification
            cozy_gamification.save_user_data()
            logging.info('✅ Gamification data saved on shutdown')
        except Exception as e:
            logging.error(f'❌ Failed to save gamification data on shutdown: {e}')
    finally:
        loop.close()