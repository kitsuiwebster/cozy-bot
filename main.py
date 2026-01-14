import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands
from datetime import datetime
import json
import asyncio
import fcntl
import aiohttp
from utils.deployment.deployment_notifier import DeploymentNotifier
from utils.audio.audio_restoration_monitor import AudioRestorationMonitor

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
        'WARNING': '⚡',
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
        # Pad emoji to consistent width
        if len(emoji) == 1:
            emoji_padded = f"{emoji}  "  # Single char emoji + 2 spaces
        else:
            emoji_padded = f"{emoji} "   # Other multi char emoji + 1 space
        return f"{color}{emoji_padded}[{timestamp}] {record.levelname:<8} {reset}{record.getMessage()}"

# Initialize enhanced logging system
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clear existing log handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Configure Discord.py logger to use our formatter too
discord_logger = logging.getLogger('discord')
for handler in discord_logger.handlers[:]:
    discord_logger.removeHandler(handler)

# Install custom log formatter - single handler for all loggers
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(FancyFormatter())
logger.addHandler(handler)

# Force discord logger to use our handler and suppress intent warnings
discord_logger.propagate = False
discord_logger.addHandler(handler)
discord_logger.setLevel(logging.ERROR)  # Skip warnings, only show errors from discord

# Configure Discord Gateway intents for bot permissions
intents = discord.Intents.default()
intents.typing = False
intents.members = False  # Test: Désactivé pour voir si le bot fonctionne toujours
intents.message_content = False
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

def save_voice_time_data(silent=False):
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
        if not silent:
            logging.info('✅ SERVER TIME SAVE: Saved successfully')
        
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

# Track guild voice time changes for periodic logging
guild_voice_time_changes = {}  # {guild_id: added_seconds_since_last_save}

# Initialize user voice session tracking - with accumulated time
user_voice_sessions = {}  # {guild_id: {bot_start_time: datetime, users: {user_id: {join_time: datetime, accumulated_time: float}}}}

# Global variable to track periodic backup task
periodic_backup_task = None

# Background task for dynamic bot presence updates
async def change_status():
    await bot.wait_until_ready()

    while not bot.is_closed():
        try:
            server_count = len(bot.guilds)
            total_member_count = sum(guild.member_count or 0 for guild in bot.guilds)
            statuses = [
                discord.Game(name=f"in {server_count} servers"),
                discord.Game(name=f"with {total_member_count} members"),
            ]

            # Rotate through presence states with configured interval
            for status in statuses:
                if bot.is_closed():
                    return
                await bot.change_presence(activity=status)
                await asyncio.sleep(10)
        except (ConnectionResetError, OSError, discord.ConnectionClosed):
            # Connection issues during reconnection, wait and retry
            await asyncio.sleep(30)
        except Exception as e:
            logging.error(f"❌ Error updating bot status: {e}")
            await asyncio.sleep(60)

# Background task for hourly data backup
async def periodic_backup():
    await bot.wait_until_ready()
    
    while not bot.is_closed():
        # Full backup every 10 minutes
        await asyncio.sleep(600)  # 10 minutes
        
        try:
            from cogs.stats.gamification import cozy_gamification
            
            logging.info("")
            logging.info("")
            logging.info("🕐 PERIODIC BACKUP: Starting complete data backup...")
            
            # DEBUG: Log all users with active sessions at start of periodic backup
            users_with_sessions = []
            if hasattr(cozy_gamification, 'user_data'):
                for user_id, user_stats in cozy_gamification.user_data.items():
                    current_sound = user_stats.get('current_sound')
                    if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                        users_with_sessions.append(user_id)
            logging.info(f"🔍 DEBUG: PERIODIC users with active sessions at start: {len(users_with_sessions)} - {users_with_sessions}")
            
            # DEBUG: Log all users currently in voice with bot
            users_in_voice = []
            for guild in bot.guilds:
                if guild.voice_client and guild.voice_client.channel:
                    current_users = [member for member in guild.voice_client.channel.members if not member.bot]
                    for user in current_users:
                        users_in_voice.append(str(user.id))
            logging.info(f"🔍 DEBUG: PERIODIC users currently in voice with bot: {len(users_in_voice)} - {users_in_voice}")
            
            # Process active sessions and calculate time since last save
            active_session_updates = {}  # {guild_id: added_time}
            active_user_updates = {}     # {user_id: {time: float, sound: str}}
            
            # Update voice time for active bot sessions
            for guild_id, guild_data in guild_voice_time.items():
                if isinstance(guild_data, list) and len(guild_data) >= 2 and guild_data[0] is not None:
                    # Check if bot is actually connected to voice in this guild
                    guild = bot.get_guild(int(guild_id))
                    if not guild or not guild.voice_client or not guild.voice_client.channel:
                        # Bot is not in voice, reset the session start time to None
                        guild_voice_time[guild_id] = [None, guild_data[1]]  # Keep accumulated time, reset session
                        continue
                    
                    # Bot is active in this server
                    start_time = datetime.fromisoformat(guild_data[0])
                    accumulated_time = guild_data[1]
                    current_session_time = (datetime.now() - start_time).total_seconds()
                    
                    # Validate server session duration (max 30 minutes to prevent corrupted data)
                    max_session_duration = 30 * 60  # 30 minutes in seconds
                    if current_session_time > max_session_duration:
                        logging.warning(f"⚠️ Suspicious server session duration for guild {guild_id}: {current_session_time/60:.1f}min - capping to 30min")
                        current_session_time = max_session_duration
                    
                    # Update the accumulated time
                    new_total = accumulated_time + current_session_time
                    guild_voice_time[guild_id] = [datetime.now().isoformat(), new_total]
                    
                    # Track this update for logging
                    active_session_updates[guild_id] = current_session_time
            
            # Get list of users actually in voice channels with the bot
            users_in_voice_with_bot = set()
            for guild in bot.guilds:
                if guild.voice_client and guild.voice_client.channel:
                    # Bot is connected to a voice channel in this guild
                    for member in guild.voice_client.channel.members:
                        if not member.bot:  # Exclude bots
                            users_in_voice_with_bot.add(str(member.id))
            
            # Update gamification data for active user sessions
            logging.info(f"🔍 DEBUG: PERIODIC processing user sessions - total users in data: {len(cozy_gamification.user_data)}")
            for user_id, user_stats in cozy_gamification.user_data.items():
                current_sound = user_stats.get('current_sound')
                if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                    logging.info(f"🔍 DEBUG: PERIODIC processing user {user_id} with active session: {current_sound.get('name')}")
                    try:
                        # First check: is user actually in voice with bot?
                        if str(user_id) not in users_in_voice_with_bot:
                            username = cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                            logging.warning(f"⚠️ Removing session for {username}: not in voice with bot")
                            logging.info(f"🔍 DEBUG: PERIODIC user {user_id} not in voice, removing session")
                            
                            # Finalize the current sound before removing session to award remaining points
                            cozy_gamification.finalize_current_sound(user_id)
                            logging.info(f"👉 PERIODIC CLEANUP: Finalized session for {username}")
                            continue
                        
                        logging.info(f"🔍 DEBUG: PERIODIC user {user_id} is in voice, processing session")
                        
                        start_time = datetime.fromisoformat(current_sound['start_time'])
                        session_duration = (datetime.now() - start_time).total_seconds()
                        sound_name = current_sound['name']
                        
                        # Backup validation: max 30 minutes to prevent corrupted data
                        max_session_duration = 30 * 60  # 30 minutes in seconds
                        if session_duration > max_session_duration:
                            username = cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                            logging.warning(f"⚠️ Removing old session for {username}: {session_duration/60:.1f}min old")
                            user_stats['current_sound'] = None
                            continue
                        
                        if session_duration > 0:
                            # Update listening time
                            user_stats['listening_time'] += session_duration
                            
                            # Update sound-specific time
                            if 'listening_time_by_sound' not in user_stats:
                                user_stats['listening_time_by_sound'] = {}
                            if sound_name not in user_stats['listening_time_by_sound']:
                                user_stats['listening_time_by_sound'][sound_name] = {
                                    'total_time': 0.0,
                                    'session_count': 0,
                                    'consecutive_time': 0.0
                                }
                            user_stats['listening_time_by_sound'][sound_name]['total_time'] += session_duration
                            # Update consecutive time during periodic backup
                            if 'consecutive_time' not in user_stats['listening_time_by_sound'][sound_name]:
                                user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                            user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] += session_duration
                            
                            # Update tracking for logging
                            if user_id not in cozy_gamification.changes_since_save['user_listening_time']:
                                cozy_gamification.changes_since_save['user_listening_time'][user_id] = 0
                            cozy_gamification.changes_since_save['user_listening_time'][user_id] += session_duration
                            
                            if user_id not in cozy_gamification.changes_since_save['user_sound_time']:
                                cozy_gamification.changes_since_save['user_sound_time'][user_id] = {}
                            if sound_name not in cozy_gamification.changes_since_save['user_sound_time'][user_id]:
                                cozy_gamification.changes_since_save['user_sound_time'][user_id][sound_name] = 0
                            cozy_gamification.changes_since_save['user_sound_time'][user_id][sound_name] += session_duration
                            
                            # Award points for listening time (1 point per minute)
                            points_to_add = int(session_duration / 60)
                            if points_to_add > 0:
                                user_stats['total_points'] += points_to_add
                                if user_id not in cozy_gamification.changes_since_save['user_points_breakdown']:
                                    cozy_gamification.changes_since_save['user_points_breakdown'][user_id] = []
                                cozy_gamification.changes_since_save['user_points_breakdown'][user_id].append({
                                    'reason': f"Periodic save: listening to {sound_name}",
                                    'points': points_to_add
                                })
                            
                            # Award streak bonus (+[streak days] points every 10 minutes)
                            streak_bonus = cozy_gamification.calculate_streak_bonus(user_id, session_duration / 60)
                            if streak_bonus > 0:
                                user_stats['total_points'] += streak_bonus
                                current_streak = cozy_gamification.get_current_streak(user_id)
                                if user_id not in cozy_gamification.changes_since_save['user_points_breakdown']:
                                    cozy_gamification.changes_since_save['user_points_breakdown'][user_id] = []
                                cozy_gamification.changes_since_save['user_points_breakdown'][user_id].append({
                                    'reason': f"Streak bonus: {current_streak}-day streak",
                                    'points': streak_bonus
                                })
                            
                            # Reset start time for next period
                            current_sound['start_time'] = datetime.now().isoformat()
                            
                            # Update accumulated time in user_voice_sessions for correct disconnect logging
                            for guild_id, session_data in user_voice_sessions.items():
                                if user_id in session_data.get('users', {}):
                                    session_data['users'][user_id]['accumulated_time'] += session_duration
                                    session_data['users'][user_id]['join_time'] = datetime.now()
                                    break
                            
                            # Track for logging
                            total_points_awarded = points_to_add + streak_bonus
                            active_user_updates[user_id] = {
                                'time': session_duration,
                                'sound': sound_name,
                                'points': total_points_awarded
                            }
                    except Exception as e:
                        logging.warning(f"⚠️ Error processing active session for user {user_id}: {e}")
            
            # RECONNECTION FIX: Restart sessions for users in voice who lost tracking
            from cogs.stats.gamification import cozy_gamification
            users_with_active_sessions = set()
            for user_id, user_stats in cozy_gamification.user_data.items():
                current_sound = user_stats.get('current_sound')
                if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                    users_with_active_sessions.add(str(user_id))
            
            # Find users in voice but without active sessions (lost after reconnection)
            users_missing_sessions = users_in_voice_with_bot - users_with_active_sessions
            if users_missing_sessions:
                for guild in bot.guilds:
                    if guild.voice_client and guild.voice_client.channel:
                        guild_id = str(guild.id)
                        # Get current sound playing in this guild from global state
                        from cogs.audio.base_sound import global_current_sounds
                        current_guild_sound = global_current_sounds.get(guild.id)
                        
                        if current_guild_sound:
                            # Restart sessions for users in this guild who lost tracking
                            for member in guild.voice_client.channel.members:
                                if not member.bot and str(member.id) in users_missing_sessions:
                                    cozy_gamification.track_sound_start(str(member.id), current_guild_sound)
                                    logging.info(f"👉 RECONNECT FIX: Restarted session for \033[35m{member.name}\033[0m tracking {current_guild_sound}")
                                    users_missing_sessions.remove(str(member.id))
            
            # Log voice time changes for servers since last save
            if guild_voice_time_changes or active_session_updates:
                from cogs.stats.gamification import cozy_gamification
                
                # Log completed session changes
                for guild_id, added_time in guild_voice_time_changes.items():
                    if added_time > 0:
                        server_name = cozy_gamification.servernames.get(str(guild_id), {}).get('name', f'Server {str(guild_id)[:8]}')
                        logging.info(f"  🏠 \033[94m+{format_duration(added_time)}\033[0m for {server_name}")
                
                # Log active session updates only if users are present
                for guild_id, added_time in active_session_updates.items():
                    if added_time > 0:
                        # Check if any users are actually in voice with the bot in this guild
                        guild = bot.get_guild(int(guild_id))
                        has_users = False
                        if guild and guild.voice_client and guild.voice_client.channel:
                            human_members = [m for m in guild.voice_client.channel.members if not m.bot]
                            has_users = len(human_members) > 0
                        
                        if has_users:
                            server_name = cozy_gamification.servernames.get(str(guild_id), {}).get('name', f'Server {str(guild_id)[:8]}')
                            logging.info(f"  🏠 \033[94m+{format_duration(added_time)}\033[0m for {server_name} (active session)")
                
                # Reset changes tracking
                guild_voice_time_changes.clear()
            
            # Log active user session updates
            if active_user_updates:
                for user_id, update_info in active_user_updates.items():
                    username = f'\033[35m{cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
                    time_str = f'\033[94m+{format_duration(update_info["time"])}\033[0m'
                    points_str = f' (\033[32m+{update_info["points"]} points\033[0m)' if update_info["points"] > 0 else ''
                    logging.info(f"  👉 {time_str} for {username} ({update_info['sound']} active session){points_str}")
            
            # Save voice time data for all servers (silently)
            if guild_voice_time:
                save_voice_time_data(silent=True)
            
            # Save gamification data (users, points, achievements, etc.) with detailed logging
            cozy_gamification.save_user_data(force_detailed_log=True)
            
            logging.info("✅ PERIODIC BACKUP: Complete backup finished")
            
        except Exception as e:
            logging.error(f"❌ PERIODIC BACKUP FAILED: {e}")
        
        # Save current stats for API
        save_current_stats_for_api()
def save_current_stats_for_api():
    """Save current bot stats for API access (only counts users with active sounds)"""
    try:
        active_listeners = 0
        servers_with_bot = 0

        # Count servers where bot is connected
        for guild in bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                servers_with_bot += 1

        # Count only users who have an active sound session
        from cogs.stats.gamification import cozy_gamification
        if hasattr(cozy_gamification, 'user_data'):
            for user_id, user_stats in cozy_gamification.user_data.items():
                current_sound = user_stats.get('current_sound')
                # Check if user has an active sound session (with start_time)
                if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                    active_listeners += 1

        stats = {
            'current_listeners': active_listeners,
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
                            logging.info(f"✨ {endpoint} - healthy")
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
            existing_data = guild_voice_time.get(guild_id, [None, 0])
            if isinstance(existing_data, list) and len(existing_data) >= 2:
                accumulated_time = existing_data[1]
            else:
                accumulated_time = 0  # Reset corrupted data
            guild_voice_time[guild_id] = [datetime.now().isoformat(), accumulated_time]
            
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
            logging.info("")
            logging.info("")
            logging.info(f"👉 BOT JOIN: Connected to {after.channel.name} in {member.guild.name} - {len(current_users)} users already present")
            for user in current_users:
                user_id = str(user.id)
                user_voice_sessions[guild_id]['users'][user_id] = {
                    'join_time': datetime.now(),
                    'accumulated_time': 0.0
                }
                # Award session join points - pass both username and display_name
                # Force bonus for users already present when bot joins (new session start)
                result = cozy_gamification.join_session(user_id, user.name, force_bonus=True)
                cozy_gamification.update_username(user_id, user.name, user.global_name or user.name)
                logging.info(f"👉 USER JOIN: \033[35m{user.name}\033[0m was already in channel when bot joined {after.channel.name} in {member.guild.name}")
            
            # RECONNECTION FIX: Immediately restart sound tracking for users already present
            if current_users:
                # Check if bot is currently playing audio in this guild
                voice_client = member.guild.voice_client
                if voice_client and voice_client.is_playing():
                    # Reset consecutive time for all users (sound change behavior) 
                    current_user_ids = [str(u.id) for u in current_users]
                    cozy_gamification.reset_consecutive_time_for_guild(guild_id, current_user_ids)
                    
                    # Get current sound from global state (survives reconnections)
                    from cogs.audio.base_sound import global_current_sounds
                    current_guild_sound = global_current_sounds.get(int(guild_id))
                    
                    if current_guild_sound:
                        # Immediately restart tracking for all users
                        logging.info(f"🔍 DEBUG: RECONNECT attempting to restart tracking for {len(current_users)} users with sound {current_guild_sound}")
                        for user in current_users:
                            logging.info(f"🔍 DEBUG: RECONNECT calling track_sound_start({user.id}, {current_guild_sound}) for {user.name}")
                            cozy_gamification.track_sound_start(str(user.id), current_guild_sound)
                            logging.info(f"🔍 DEBUG: RECONNECT track_sound_start completed for {user.name}")
                            logging.info(f"👉 RECONNECT FIX: Restarted tracking {current_guild_sound} for \\033[35m{user.name}\\033[0m")
                        logging.info(f"🔍 DEBUG: RECONNECT all track_sound_start calls completed")
                    else:
                        logging.info("👉 RECONNECT FIX: Bot is playing audio but couldn't identify current sound")
                        logging.info(f"🔍 DEBUG: RECONNECT no current_guild_sound found, global_current_sounds: {global_current_sounds}")
                else:
                    # Bot joined but no audio is playing - this is an error state
                    # Wait 2 seconds to give audio time to start, then check again
                    import asyncio
                    await asyncio.sleep(2)

                    # Double check if audio started in the meantime
                    if voice_client and voice_client.is_playing():
                        logging.info("🔄 RECONNECT INFO: Audio started after brief delay, continuing normally")
                    else:
                        # Still no audio - disconnect and notify user
                        logging.warning("⚠️ RECONNECT ERROR: No audio playing after join, disconnecting bot")

                        # Find a text channel to send the error message
                        text_channel = None
                        if member.guild.system_channel:
                            text_channel = member.guild.system_channel
                        else:
                            # Try to find a general/chat channel
                            for channel in member.guild.text_channels:
                                if channel.permissions_for(member.guild.me).send_messages:
                                    if 'general' in channel.name.lower() or 'chat' in channel.name.lower() or 'bot' in channel.name.lower():
                                        text_channel = channel
                                        break

                            # Fallback to first available text channel
                            if not text_channel:
                                for channel in member.guild.text_channels:
                                    if channel.permissions_for(member.guild.me).send_messages:
                                        text_channel = channel
                                        break

                        # Send fun error message
                        if text_channel:
                            try:
                                await text_channel.send(
                                    "Oops! CozyBot encountered a hiccup and couldn't start the ambiance. "
                                    "Please try your command again! 🌧️✨"
                                )
                            except Exception as e:
                                logging.error(f"❌ Failed to send reconnect error message: {e}")

                        # Disconnect the bot
                        try:
                            if voice_client:
                                await voice_client.disconnect()
                                logging.info("✅ Bot disconnected from voice channel due to no audio playing")
                        except Exception as e:
                            logging.error(f"❌ Failed to disconnect bot: {e}")

        # Bot left a voice channel
        elif before.channel is not None and after.channel is None:
            # Handle server timing (existing)
            if guild_id in guild_voice_time:
                guild_data = guild_voice_time[guild_id]
                if isinstance(guild_data, list) and len(guild_data) >= 2 and guild_data[0] is not None:
                    start_time = datetime.fromisoformat(guild_data[0])
                    accumulated_time = guild_data[1]
                    time_spent = datetime.now() - start_time
                    session_duration = time_spent.total_seconds()
                    total_time = accumulated_time + session_duration
                    guild_voice_time[guild_id] = [None, total_time]
                    
                    # Track this change for periodic logging
                    if guild_id not in guild_voice_time_changes:
                        guild_voice_time_changes[guild_id] = 0
                    guild_voice_time_changes[guild_id] += session_duration
                else:
                    # Reset corrupted data
                    guild_voice_time[guild_id] = [None, 0]
                    session_duration = 0
                    total_time = 0
                logging.info("")
                logging.info("")
                logging.info(f"👋 BOT DISCONNECT: Left {before.channel.guild.name} - session: \033[94m+{format_duration(session_duration)}\033[0m, server total: \033[94m{format_duration(total_time)}\033[0m")
                logging.info(f"🏠 \033[94m+{format_duration(session_duration)}\033[0m for {before.channel.guild.name}")
                save_voice_time_data()
            
            # Calculate final listening time for all remaining users
            if guild_id in user_voice_sessions:
                from cogs.stats.gamification import cozy_gamification
                session = user_voice_sessions[guild_id]
                
                for user_id, user_data in session['users'].items():
                    # Validate user_data structure
                    if not isinstance(user_data, dict) or 'join_time' not in user_data or 'accumulated_time' not in user_data:
                        logging.warning(f"⚠️ Corrupted user data for {user_id} in final session, skipping")
                        continue
                        
                    # Get username for logging
                    try:
                        user = await bot.fetch_user(int(user_id))
                        username = f'\033[35m{user.name if user else f"User {user_id[:8]}"}\033[0m'
                    except:
                        username = f'\033[35m{f"User {user_id[:8]}"}\033[0m'
                    
                    # Calculate final session time
                    final_duration = (datetime.now() - user_data['join_time']).total_seconds()
                    total_session_time = user_data['accumulated_time'] + final_duration
                    
                    if final_duration > 0:
                        points_to_add = int(final_duration / 60)
                        logging.info(f"👋 BOT DISCONNECT: {username} final session - total: \033[94m{format_duration(total_session_time)}\033[0m, final chunk: \033[94m{format_duration(final_duration)}\033[0m, \033[32m+{points_to_add} points\033[0m")
                    
                    # Finalize current sound to award loyalty bonuses (this handles the actual point calculation)
                    cozy_gamification.finalize_current_sound(user_id)
                
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
        cozy_gamification.update_username(user_id, member.name, member.global_name or member.name)
        
        # Check if there's a currently playing sound and assign it to the new user
        current_sound = None
        guild_id_int = int(guild_id)  # Convert string to int for guild_states lookup
        for cog_name in ['RainCog', 'SeaCog', 'SparklesCog', 'BackgroundMusicCog']:
            cog = bot.get_cog(cog_name)
            if cog and hasattr(cog, 'guild_states'):
                guild_state = cog.guild_states.get(guild_id_int, {})
                if guild_state.get('is_playing') and guild_state.get('current_sound'):
                    current_sound = guild_state['current_sound']
                    logging.info("")
                    logging.info("")
                    logging.info(f"🔍 Found current sound {current_sound} in {cog_name} for guild {guild_id}")
                    break
        
        if current_sound:
            # Finalize any existing sound before starting new one
            cozy_gamification.finalize_current_sound(user_id)
            cozy_gamification.track_sound_start(user_id, current_sound)
            logging.info(f"🎵 Tracking {current_sound} for \033[35m{member.name}\033[0m")
        else:
            logging.warning(f"⚠️ No current sound found for \033[35m{member.name}\033[0m joining guild {guild_id}")
        
        logging.info(f"👉 USER JOIN: \033[35m{member.name}\033[0m joined bot channel {after.channel.name} in {member.guild.name}")
    
    # User left the bot's channel  
    elif before.channel == bot_channel and after.channel != bot_channel:
        if user_id in session['users']:
            user_data = session['users'][user_id]
            if isinstance(user_data, dict) and 'join_time' in user_data and 'accumulated_time' in user_data:
                final_duration = (datetime.now() - user_data['join_time']).total_seconds()
                total_session_time = user_data['accumulated_time'] + final_duration
            else:
                # Reset corrupted user data
                final_duration = 0
                total_session_time = 0
                logging.warning(f"⚠️ Corrupted user data for {user_id}, resetting")
            
            if final_duration > 0:
                points_to_add = int(final_duration / 60)
                logging.info("")
                logging.info("")
                logging.info(f"👋 USER LEAVE: \033[35m{member.name}\033[0m left bot channel {before.channel.name} in {member.guild.name} - total: \033[94m{format_duration(total_session_time)}\033[0m, final chunk: \033[94m{format_duration(final_duration)}\033[0m, \033[32m+{points_to_add} points\033[0m")
            else:
                logging.info(f"👋 USER LEAVE: \033[35m{member.name}\033[0m left bot channel {before.channel.name} in {member.guild.name} - no additional time")
            
            # Finalize sound tracking when user leaves (this handles the actual point calculation)
            cozy_gamification.finalize_current_sound(user_id)
            logging.info(f"👉 SOUND TRACKING: Finalized current sound for \033[35m{member.name}\033[0m")
            
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
    print("║                      Version 1.0.17                             ║")
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
    
    # Share bot instance with audio restore API
    try:
        from api.routes.audio_restore import set_bot_instance as set_audio_bot_instance
        set_audio_bot_instance(bot)
        logging.info('🔗 Bot instance shared with audio restore API')
    except Exception as e:
        logging.warning(f'⚠️ Could not share bot instance with audio restore API: {e}')
    
    logging.info(f'✨ {bot.user.name} is ready and connected!')
    
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
    
    # Only create periodic backup task if it doesn't exist
    global periodic_backup_task
    if periodic_backup_task is None or periodic_backup_task.done():
        periodic_backup_task = bot.loop.create_task(periodic_backup())
        logging.info('🕐 Started periodic backup task')
    else:
        logging.info('🕐 Periodic backup task already running')
    
    # Start deployment notifier
    deployment_notifier = DeploymentNotifier(bot)
    bot.loop.create_task(deployment_notifier.start_monitoring())
    logging.info('📢 Started deployment notifier task')
    
    # Start audio restoration monitor  
    audio_monitor = AudioRestorationMonitor(bot)
    bot.loop.create_task(audio_monitor.start_monitoring())
    logging.info('🎵 Started audio restoration monitor task')

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

# Bot initialization and startup routine
async def run_bot():
    try:
        # Load bot command modules and register extensions
        extensions = [
            ('cogs.audio.rain.rain', '🌧️'),
            ('cogs.audio.sea.sea', '🌊'),
            ('cogs.audio.sparkles.sparkles', '✨'),
            ('cogs.audio.background_music.background-music', '🎵'),
            ('cogs.audio.noise.white-noise', '🤍'),
            ('cogs.audio.stop', '🛑'),
            ('cogs.menu', '📋'),
            ('cogs.stats.profile', '🏅'),
            ('cogs.stats.tops', '🏆'),
            ('cogs.stats.total', '📊'),
            ('cogs.stats.stats', '📈'),
            ('cogs.notifications.startup_message', '📢'),
            ('cogs.privacy.privacy', '🗑️'),
            ('cogs.credits', '🎵')
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

