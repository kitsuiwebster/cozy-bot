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
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m',
        'RESET': '\033[0m'
    }

    EMOJIS = {
        'DEBUG': '⚙️',
        'INFO': '✨',
        'WARNING': '⚡',
        'ERROR': '❌',
        'CRITICAL': '💥'
    }

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        emoji = self.EMOJIS.get(record.levelname, '📝')
        reset = self.COLORS['RESET']
        timestamp = self.formatTime(record, '%H:%M:%S')

        # Pad emoji to consistent width for alignment
        if len(emoji) == 1:
            emoji_padded = f"{emoji}  "
        else:
            emoji_padded = f"{emoji} "
        return f"{color}{emoji_padded}[{timestamp}] {record.levelname:<8} {reset}{record.getMessage()}"

# Initialize enhanced logging system
logger = logging.getLogger()
logger.setLevel(logging.INFO)

for handler in logger.handlers[:]:
    logger.removeHandler(handler)

discord_logger = logging.getLogger('discord')
for handler in discord_logger.handlers[:]:
    discord_logger.removeHandler(handler)

# Configure logging to use custom formatter
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(FancyFormatter())
logger.addHandler(handler)
discord_logger.propagate = False
discord_logger.addHandler(handler)
discord_logger.setLevel(logging.ERROR)

# Configure Discord bot intents
intents = discord.Intents.default()
intents.typing = False
intents.members = False
intents.message_content = False
intents.guilds = True
intents.voice_states = True

# Initialize Discord bot instance with command prefix and intents
bot = commands.Bot(command_prefix="/", intents=intents)
logging.debug(f"⚔️ Bot guilds: {bot.guilds}")

# Format duration in seconds to human readable format
def format_duration(seconds):
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

# Save voice time data to disk with file locking
def save_voice_time_data(silent=False):
    data_file = 'data/voice_time_data.json'
    temp_file = data_file + '.tmp'
    os.makedirs('data', exist_ok=True)

    try:
        with open(temp_file, 'w') as file:
            fcntl.flock(file.fileno(), fcntl.LOCK_EX)
            json.dump(guild_voice_time, file, indent=2)
            file.flush()
            os.fsync(file.fileno())

        os.rename(temp_file, data_file)
        if not silent:
            logging.info('✅ SERVER TIME SAVE: Saved successfully')

    except Exception as e:
        if os.path.exists(temp_file):
            os.remove(temp_file)
        logging.error(f'❌ Failed to save voice time data: {e}')

# Load voice time data from disk
def load_voice_time_data():
    data_file = 'data/voice_time_data.json'
    try:
        with open(data_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

# Initialize global tracking variables
guild_voice_time = load_voice_time_data()
guild_voice_time_changes = {}
user_voice_sessions = {}
periodic_backup_task = None

# Dynamic bot presence updates
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

            for status in statuses:
                if bot.is_closed():
                    return
                await bot.change_presence(activity=status)
                await asyncio.sleep(10)
        except (ConnectionResetError, OSError, discord.ConnectionClosed):
            await asyncio.sleep(30)
        except Exception as e:
            logging.error(f"❌ Error updating bot status: {e}")
            await asyncio.sleep(60)

# Periodic data backup task
async def periodic_backup():
    await bot.wait_until_ready()

    while not bot.is_closed():
        await asyncio.sleep(600)

        try:
            from cogs.stats.gamification import cozy_gamification

            logging.info("")
            logging.info("")
            logging.info("🕐 PERIODIC BACKUP: Starting complete data backup...")

            active_session_updates = {}
            active_user_updates = {}
            
            # Process active server sessions
            for guild_id, guild_data in guild_voice_time.items():
                if isinstance(guild_data, list) and len(guild_data) >= 2 and guild_data[0] is not None:
                    guild = bot.get_guild(int(guild_id))
                    if not guild or not guild.voice_client or not guild.voice_client.channel:
                        guild_voice_time[guild_id] = [None, guild_data[1]]
                        continue

                    start_time = datetime.fromisoformat(guild_data[0])
                    accumulated_time = guild_data[1]
                    current_session_time = (datetime.now() - start_time).total_seconds()

                    # Cap session duration at 30 minutes to prevent corrupted data
                    max_session_duration = 30 * 60
                    if current_session_time > max_session_duration:
                        logging.warning(f"⚠️ Suspicious server session duration for guild {guild_id}: {current_session_time/60:.1f}min - capping to 30min")
                        current_session_time = max_session_duration

                    new_total = accumulated_time + current_session_time
                    guild_voice_time[guild_id] = [datetime.now().isoformat(), new_total]
                    active_session_updates[guild_id] = current_session_time
            
            # Track users currently in voice with bot
            users_in_voice_with_bot = set()
            for guild in bot.guilds:
                if guild.voice_client and guild.voice_client.channel:
                    for member in guild.voice_client.channel.members:
                        if not member.bot:
                            users_in_voice_with_bot.add(str(member.id))
            
            # Process active user listening sessions
            for user_id, user_stats in cozy_gamification.user_data.items():
                current_sound = user_stats.get('current_sound')
                if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                    try:
                        if str(user_id) not in users_in_voice_with_bot:
                            username = cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                            logging.warning(f"⚠️ Removing session for {username}: not in voice with bot")

                            # Finalize the current sound before removing session to award remaining points
                            cozy_gamification.finalize_current_sound(user_id)
                            logging.info(f"👉 PERIODIC CLEANUP: Finalized session for {username}")
                            continue
                        
                        start_time = datetime.fromisoformat(current_sound['start_time'])
                        session_duration = (datetime.now() - start_time).total_seconds()
                        sound_name = current_sound['name']

                        # Cap session duration at 30 minutes to prevent corrupted data
                        max_session_duration = 30 * 60
                        if session_duration > max_session_duration:
                            username = cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                            logging.warning(f"⚠️ Removing old session for {username}: {session_duration/60:.1f}min old")
                            user_stats['current_sound'] = None
                            continue

                        if session_duration > 0:
                            user_stats['listening_time'] += session_duration

                            if 'listening_time_by_sound' not in user_stats:
                                user_stats['listening_time_by_sound'] = {}
                            if sound_name not in user_stats['listening_time_by_sound']:
                                user_stats['listening_time_by_sound'][sound_name] = {
                                    'total_time': 0.0,
                                    'session_count': 0,
                                    'consecutive_time': 0.0
                                }
                            user_stats['listening_time_by_sound'][sound_name]['total_time'] += session_duration
                            if 'consecutive_time' not in user_stats['listening_time_by_sound'][sound_name]:
                                user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] = 0.0
                            user_stats['listening_time_by_sound'][sound_name]['consecutive_time'] += session_duration

                            if user_id not in cozy_gamification.changes_since_save['user_listening_time']:
                                cozy_gamification.changes_since_save['user_listening_time'][user_id] = 0
                            cozy_gamification.changes_since_save['user_listening_time'][user_id] += session_duration

                            if user_id not in cozy_gamification.changes_since_save['user_sound_time']:
                                cozy_gamification.changes_since_save['user_sound_time'][user_id] = {}
                            if sound_name not in cozy_gamification.changes_since_save['user_sound_time'][user_id]:
                                cozy_gamification.changes_since_save['user_sound_time'][user_id][sound_name] = 0
                            cozy_gamification.changes_since_save['user_sound_time'][user_id][sound_name] += session_duration

                            # Award points: 1 point per minute
                            points_to_add = int(session_duration / 60)
                            if points_to_add > 0:
                                user_stats['total_points'] += points_to_add
                                if user_id not in cozy_gamification.changes_since_save['user_points_breakdown']:
                                    cozy_gamification.changes_since_save['user_points_breakdown'][user_id] = []
                                cozy_gamification.changes_since_save['user_points_breakdown'][user_id].append({
                                    'reason': f"Periodic save: listening to {sound_name}",
                                    'points': points_to_add
                                })

                            # Award streak bonus
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

                            current_sound['start_time'] = datetime.now().isoformat()

                            for guild_id, session_data in user_voice_sessions.items():
                                if user_id in session_data.get('users', {}):
                                    session_data['users'][user_id]['accumulated_time'] += session_duration
                                    session_data['users'][user_id]['join_time'] = datetime.now()
                                    break

                            total_points_awarded = points_to_add + streak_bonus
                            active_user_updates[user_id] = {
                                'time': session_duration,
                                'sound': sound_name,
                                'points': total_points_awarded
                            }
                    except Exception as e:
                        logging.warning(f"⚠️ Error processing active session for user {user_id}: {e}")
            
            # Restart tracking for users who lost sessions after reconnection
            from cogs.stats.gamification import cozy_gamification
            users_with_active_sessions = set()
            for user_id, user_stats in cozy_gamification.user_data.items():
                current_sound = user_stats.get('current_sound')
                if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                    users_with_active_sessions.add(str(user_id))

            users_missing_sessions = users_in_voice_with_bot - users_with_active_sessions
            if users_missing_sessions:
                for guild in bot.guilds:
                    if guild.voice_client and guild.voice_client.channel:
                        guild_id = str(guild.id)
                        from cogs.audio.base_sound import global_current_sounds
                        current_guild_sound = global_current_sounds.get(guild.id)

                        if current_guild_sound:
                            for member in guild.voice_client.channel.members:
                                if not member.bot and str(member.id) in users_missing_sessions:
                                    cozy_gamification.track_sound_start(str(member.id), current_guild_sound)
                                    logging.info(f"👉 RECONNECT FIX: Restarted session for \033[35m{member.name}\033[0m tracking {current_guild_sound}")
                                    users_missing_sessions.remove(str(member.id))
            
            # Log voice time changes since last save
            if guild_voice_time_changes or active_session_updates:
                from cogs.stats.gamification import cozy_gamification

                for guild_id, added_time in guild_voice_time_changes.items():
                    if added_time > 0:
                        server_name = cozy_gamification.servernames.get(str(guild_id), {}).get('name', f'Server {str(guild_id)[:8]}')
                        logging.info(f"  🏠 \033[94m+{format_duration(added_time)}\033[0m for {server_name}")

                for guild_id, added_time in active_session_updates.items():
                    if added_time > 0:
                        guild = bot.get_guild(int(guild_id))
                        has_users = False
                        if guild and guild.voice_client and guild.voice_client.channel:
                            human_members = [m for m in guild.voice_client.channel.members if not m.bot]
                            has_users = len(human_members) > 0

                        if has_users:
                            server_name = cozy_gamification.servernames.get(str(guild_id), {}).get('name', f'Server {str(guild_id)[:8]}')
                            logging.info(f"  🏠 \033[94m+{format_duration(added_time)}\033[0m for {server_name} (active session)")

                guild_voice_time_changes.clear()
            
            if active_user_updates:
                for user_id, update_info in active_user_updates.items():
                    username = f'\033[35m{cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")}\033[0m'
                    time_str = f'\033[94m+{format_duration(update_info["time"])}\033[0m'
                    points_str = f' (\033[32m+{update_info["points"]} points\033[0m)' if update_info["points"] > 0 else ''
                    logging.info(f"  👉 {time_str} for {username} ({update_info['sound']} active session){points_str}")

            if guild_voice_time:
                save_voice_time_data(silent=True)

            cozy_gamification.save_user_data(force_detailed_log=True)
            logging.info("✅ PERIODIC BACKUP: Complete backup finished")

        except Exception as e:
            logging.error(f"❌ PERIODIC BACKUP FAILED: {e}")

        save_current_stats_for_api()

# Save current bot stats for API access
def save_current_stats_for_api():
    try:
        active_listeners = 0
        servers_with_bot = 0

        for guild in bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                servers_with_bot += 1

        from cogs.stats.gamification import cozy_gamification
        if hasattr(cozy_gamification, 'user_data'):
            for user_id, user_stats in cozy_gamification.user_data.items():
                current_sound = user_stats.get('current_sound')
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

# Check all API endpoints health
async def check_api_endpoints():
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
                async with session.get(f"{api_base}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                    if response.status == 200:
                        logging.info(f"✨ {endpoint} - healthy")
                    else:
                        logging.error(f"🔥 {endpoint} - error (status: {response.status})")
            except:
                try:
                    async with session.get(f"{api_base_http}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            logging.info(f"✨ {endpoint} - healthy")
                        else:
                            logging.error(f"❌ {endpoint} - error (status: {response.status})")
                except:
                    logging.error(f"❌ {endpoint} - error")

# Global error handler for bot events
@bot.event
async def on_error(event, *args, **kwargs):
    logging.error(f"An error occurred: {event}")

# Handle voice state changes for tracking
@bot.event
async def on_voice_state_update(member, before, after):
    # Handle bot joining/leaving voice channels
    if member.id == bot.user.id:
        guild_id = str(member.guild.id)

        # Bot joined voice channel
        if before.channel is None and after.channel is not None:
            existing_data = guild_voice_time.get(guild_id, [None, 0])
            if isinstance(existing_data, list) and len(existing_data) >= 2:
                accumulated_time = existing_data[1]
            else:
                accumulated_time = 0
            guild_voice_time[guild_id] = [datetime.now().isoformat(), accumulated_time]

            from cogs.stats.gamification import cozy_gamification
            cozy_gamification.update_servername(guild_id, member.guild.name)

            user_voice_sessions[guild_id] = {
                'bot_start_time': datetime.now(),
                'users': {}
            }

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
                result = cozy_gamification.join_session(user_id, user.name, force_bonus=True)
                cozy_gamification.update_username(user_id, user.name, user.global_name or user.name)
                logging.info(f"👉 USER JOIN: \033[35m{user.name}\033[0m was already in channel when bot joined {after.channel.name} in {member.guild.name}")
            
            # Restart tracking for users already in channel
            if current_users:
                voice_client = member.guild.voice_client
                if voice_client and voice_client.is_playing():
                    current_user_ids = [str(u.id) for u in current_users]
                    cozy_gamification.reset_consecutive_time_for_guild(guild_id, current_user_ids)

                    from cogs.audio.base_sound import global_current_sounds
                    current_guild_sound = global_current_sounds.get(int(guild_id))

                    if current_guild_sound:
                        for user in current_users:
                            cozy_gamification.track_sound_start(str(user.id), current_guild_sound)
                            logging.info(f"👉 RECONNECT FIX: Restarted tracking {current_guild_sound} for \\033[35m{user.name}\\033[0m")
                    else:
                        logging.info("👉 RECONNECT FIX: Bot is playing audio but couldn't identify current sound")
                else:
                    import asyncio
                    await asyncio.sleep(2)

                    if voice_client and voice_client.is_playing():
                        logging.info("👉 RECONNECT INFO: Audio started after brief delay, continuing normally")
                    else:
                        logging.warning("⚠️ RECONNECT ERROR: No audio playing after join, disconnecting bot")

                        text_channel = None
                        if member.guild.system_channel:
                            text_channel = member.guild.system_channel
                        else:
                            for channel in member.guild.text_channels:
                                if channel.permissions_for(member.guild.me).send_messages:
                                    if 'general' in channel.name.lower() or 'chat' in channel.name.lower() or 'bot' in channel.name.lower():
                                        text_channel = channel
                                        break

                            if not text_channel:
                                for channel in member.guild.text_channels:
                                    if channel.permissions_for(member.guild.me).send_messages:
                                        text_channel = channel
                                        break

                        if text_channel:
                            try:
                                await text_channel.send(
                                    "Oops! CozyBot encountered a hiccup and couldn't start the ambiance. "
                                    "Please try your command again! 🌧️✨"
                                )
                            except Exception as e:
                                logging.error(f"❌ Failed to send reconnect error message: {e}")

                        try:
                            if voice_client:
                                await voice_client.disconnect(force=True)
                                await asyncio.sleep(0.5)  # Give Discord time to process disconnect
                                logging.info("✅ Bot disconnected from voice channel due to no audio playing")
                        except Exception as e:
                            logging.error(f"❌ Failed to disconnect bot: {e}")

        # Bot left voice channel
        elif before.channel is not None and after.channel is None:
            if guild_id in guild_voice_time:
                guild_data = guild_voice_time[guild_id]
                if isinstance(guild_data, list) and len(guild_data) >= 2 and guild_data[0] is not None:
                    start_time = datetime.fromisoformat(guild_data[0])
                    accumulated_time = guild_data[1]
                    time_spent = datetime.now() - start_time
                    session_duration = time_spent.total_seconds()
                    total_time = accumulated_time + session_duration
                    guild_voice_time[guild_id] = [None, total_time]

                    if guild_id not in guild_voice_time_changes:
                        guild_voice_time_changes[guild_id] = 0
                    guild_voice_time_changes[guild_id] += session_duration
                else:
                    # Preserve accumulated time even if format is invalid
                    accumulated_time = guild_data[1] if isinstance(guild_data, list) and len(guild_data) >= 2 else 0
                    guild_voice_time[guild_id] = [None, accumulated_time]
                    session_duration = 0
                    total_time = accumulated_time
                    logging.warning(f"⚠️ Invalid guild_data format for {guild_id}, preserved accumulated time: {format_duration(accumulated_time)}")
                logging.info("")
                logging.info("")
                logging.info(f"👋 BOT DISCONNECT: Left {before.channel.guild.name} - session: \033[94m+{format_duration(session_duration)}\033[0m, server total: \033[94m{format_duration(total_time)}\033[0m")
                logging.info(f"🏠 \033[94m+{format_duration(session_duration)}\033[0m for {before.channel.guild.name}")
                save_voice_time_data()

            if guild_id in user_voice_sessions:
                from cogs.stats.gamification import cozy_gamification
                session = user_voice_sessions[guild_id]

                for user_id, user_data in session['users'].items():
                    if not isinstance(user_data, dict) or 'join_time' not in user_data or 'accumulated_time' not in user_data:
                        logging.warning(f"⚠️ Corrupted user data for {user_id} in final session, skipping")
                        continue

                    try:
                        user = await bot.fetch_user(int(user_id))
                        username = f'\033[35m{user.name if user else f"User {user_id[:8]}"}\033[0m'
                    except:
                        username = f'\033[35m{f"User {user_id[:8]}"}\033[0m'

                    final_duration = (datetime.now() - user_data['join_time']).total_seconds()
                    total_session_time = user_data['accumulated_time'] + final_duration

                    if final_duration > 0:
                        points_to_add = int(final_duration / 60)
                        logging.info(f"👋 BOT DISCONNECT: {username} final session - total: \033[94m{format_duration(total_session_time)}\033[0m, final chunk: \033[94m{format_duration(final_duration)}\033[0m, \033[32m+{points_to_add} points\033[0m")

                    cozy_gamification.finalize_current_sound(user_id)

                del user_voice_sessions[guild_id]
        return

    # Handle user voice channel changes
    if member.bot:
        return

    guild_id = str(member.guild.id)
    user_id = str(member.id)

    if guild_id not in user_voice_sessions:
        return

    bot_voice_client = member.guild.voice_client
    bot_channel = bot_voice_client.channel if bot_voice_client else None

    if not bot_channel:
        return

    from cogs.stats.gamification import cozy_gamification
    session = user_voice_sessions[guild_id]

    # User joined bot's channel
    if after.channel == bot_channel and before.channel != bot_channel:
        session['users'][user_id] = {
            'join_time': datetime.now(),
            'accumulated_time': 0.0
        }
        result = cozy_gamification.join_session(user_id, member.name)
        cozy_gamification.update_username(user_id, member.name, member.global_name or member.name)

        # Find currently playing sound to track for new user
        current_sound = None
        guild_id_int = int(guild_id)
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
            cozy_gamification.finalize_current_sound(user_id)
            cozy_gamification.track_sound_start(user_id, current_sound)
            logging.info(f"🎵 Tracking {current_sound} for \033[35m{member.name}\033[0m")
        else:
            logging.warning(f"⚠️ No current sound found for \033[35m{member.name}\033[0m joining guild {guild_id}")

        logging.info(f"👉 USER JOIN: \033[35m{member.name}\033[0m joined bot channel {after.channel.name} in {member.guild.name}")

    # User left bot's channel
    elif before.channel == bot_channel and after.channel != bot_channel:
        if user_id in session['users']:
            user_data = session['users'][user_id]
            if isinstance(user_data, dict) and 'join_time' in user_data and 'accumulated_time' in user_data:
                final_duration = (datetime.now() - user_data['join_time']).total_seconds()
                total_session_time = user_data['accumulated_time'] + final_duration
            else:
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

            cozy_gamification.finalize_current_sound(user_id)
            logging.info(f"👉 SOUND TRACKING: Finalized current sound for \033[35m{member.name}\033[0m")

            del session['users'][user_id] 

# Bot ready event handler
@bot.event
async def on_ready():
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
    print("║                      Version 1.0.18                             ║")
    print("║            by @kitsuiwebster & @BubbleXGum                      ║")
    print("║                                                                 ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print("="*60 + "\n")

    try:
        from api.routes.stats import set_bot_instance
        set_bot_instance(bot)
        logging.info('🔗 Bot instance shared with API for LIVE access')
    except Exception as e:
        logging.warning(f'⚠️ Could not share bot instance with API: {e}')

    try:
        from api.routes.audio_restore import set_bot_instance as set_audio_bot_instance
        set_audio_bot_instance(bot)
        logging.info('🔗 Bot instance shared with audio restore API')
    except Exception as e:
        logging.warning(f'⚠️ Could not share bot instance with audio restore API: {e}')

    logging.info(f'✨ {bot.user.name} is ready and connected!')

    try:
        logging.info('👉 Syncing application commands...')
        synced = await bot.tree.sync()
        logging.info(f'✅ Synced {len(synced)} application commands!')
    except Exception as e:
        logging.error(f'❌ Error syncing commands: {e}')

    logging.info('🚀 Bot startup complete - All systems operational')

    await check_api_endpoints()

    bot.heartbeat_interval = 360
    bot.loop.create_task(change_status())

    global periodic_backup_task
    if periodic_backup_task is None or periodic_backup_task.done():
        periodic_backup_task = bot.loop.create_task(periodic_backup())
        logging.info('🕐 Started periodic backup task')
    else:
        logging.info('🕐 Periodic backup task already running')

    deployment_notifier = DeploymentNotifier(bot)
    bot.loop.create_task(deployment_notifier.start_monitoring())
    logging.info('📢 Started deployment notifier task')

    audio_monitor = AudioRestorationMonitor(bot)
    bot.loop.create_task(audio_monitor.start_monitoring())
    logging.info('🎵 Started audio restoration monitor task')

    server_count = len(bot.guilds)
    total_member_count = sum(guild.member_count for guild in bot.guilds)
    logging.info(f'👉 Serving {total_member_count:,} members across {server_count} servers')
    logging.info('🏠 Connected servers:')
    for guild in bot.guilds:
        logging.info(f'   ╰┈➤ {guild.name} ({guild.member_count:,} members)')

# Message handler to process commands
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    await bot.process_commands(message)

# Bot initialization
async def run_bot():
    try:
        extensions = [
            ('cogs.audio.rain.rain', '🌧️'),
            ('cogs.audio.sea.sea', '🌊'),
            ('cogs.audio.sparkles.sparkles', '✨'),
            ('cogs.audio.background_music.background-music', '🎵'),
            ('cogs.audio.noise.noise', '🤍'),
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
            space = '  ' if emoji == '🌧️' else ' '
            logging.info(f'✅️ {emoji}{space} {ext_name} loaded successfully')

    except Exception as e:
        logging.error(f'❌ Error loading extension: {e}')

    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if not bot_token:
        logging.critical('💥 Discord token not found in environment variables')
        return

    try:
        await bot.start(bot_token)
    except Exception as e:
        logging.critical(f'💥 Failed to start bot: {e}')
        raise

# Main entry point for bot execution
if __name__ == "__main__":
    loop = asyncio.get_event_loop()

    try:
        loop.run_until_complete(run_bot())
    except KeyboardInterrupt:
        logging.info("🛑 Bot stopped by user.")
        save_voice_time_data()
        try:
            from cogs.stats.gamification import cozy_gamification
            cozy_gamification.save_user_data()
            logging.info('✅ Gamification data saved on shutdown')
        except Exception as e:
            logging.error(f'❌ Failed to save gamification data on shutdown: {e}')
    finally:
        loop.close()

