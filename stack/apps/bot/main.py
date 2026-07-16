import discord
import logging
from dotenv import load_dotenv
import os
from discord.ext import commands, tasks
from datetime import datetime, timezone
import json
import asyncio
import time
import fcntl
import aiohttp
import threading
import warnings
import errno
import math
from utils.deployment.deployment_notifier import DeploymentNotifier
from utils.audio.audio_restoration_monitor import AudioRestorationMonitor
from utils.logging_utils import setup_logging

# Load environment variables from configuration file
load_dotenv()
warnings.filterwarnings("ignore", message="pkg_resources is deprecated as an API.*", category=DeprecationWarning)

# Minimal mode: skip non-voice-critical background work to reduce event loop load
COZY_MINIMAL = os.getenv("COZY_MINIMAL", "0") == "1"

def _env_enabled(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value == "1"

COZY_ENABLE_API_CHECKS = _env_enabled("COZY_ENABLE_API_CHECKS", not COZY_MINIMAL)
COZY_ENABLE_BACKUPS = _env_enabled("COZY_ENABLE_BACKUPS", not COZY_MINIMAL)
COZY_ENABLE_DEPLOY_NOTIFIER = _env_enabled("COZY_ENABLE_DEPLOY_NOTIFIER", not COZY_MINIMAL)
COZY_ENABLE_AUDIO_RESTORE = _env_enabled("COZY_ENABLE_AUDIO_RESTORE", not COZY_MINIMAL)
COZY_ENABLE_VOICE_TRACKING = _env_enabled("COZY_ENABLE_VOICE_TRACKING", not COZY_MINIMAL)
COZY_ENABLE_COUCHDB_SUMMARY = _env_enabled("COZY_ENABLE_COUCHDB_SUMMARY", not COZY_MINIMAL)
COZY_ENABLE_BOT_API = _env_enabled("COZY_ENABLE_BOT_API", True)
BOT_API_PORT = int(os.getenv("BOT_API_PORT", "8002"))

# Configure enhanced logging system with visual formatting
discord_log_level = os.getenv("DISCORD_LOG_LEVEL", "WARNING")
setup_logging(discord_log_level)

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


def patch_discord_ffmpeg_cleanup():
    """Ignore sporadic EBADF during FFmpeg process cleanup in discord.py worker threads."""
    try:
        import discord.player as discord_player

        original_kill = getattr(discord_player.FFmpegAudio, "_kill_process", None)
        if not original_kill or getattr(original_kill, "_cozy_safe_patch", False):
            return

        def safe_kill_process(self):
            try:
                return original_kill(self)
            except OSError as exc:
                if exc.errno == errno.EBADF:
                    logging.warning("⚠️ Ignored FFmpeg cleanup EBADF (process already closed)")
                    return
                raise

        safe_kill_process._cozy_safe_patch = True
        discord_player.FFmpegAudio._kill_process = safe_kill_process
    except Exception as exc:
        logging.warning(f"⚠️ Could not patch discord FFmpeg cleanup: {exc}")


def finite_float(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(default)
    if math.isfinite(number):
        return number
    return float(default)


patch_discord_ffmpeg_cleanup()

# Track user join in background to avoid blocking Discord events
def _track_user_join_sync(user_id, member, guild_id):
    try:
        from cogs.stats.gamification import cozy_gamification

        # Don't save immediately for user tracking
        cozy_gamification.update_username(user_id, member.name, member.global_name or member.name, save_immediately=False)
        cozy_gamification.join_session(user_id, member.name, save_immediately=False)

        # Find currently playing sound to track for new user
        current_sound = None
        guild_id_int = int(guild_id)
        for cog_name in ['RainCog', 'SeaCog', 'SparklesCog', 'BackgroundMusicCog', 'NoiseCog']:
            cog = bot.get_cog(cog_name)
            if cog and hasattr(cog, 'guild_states'):
                guild_state = cog.guild_states.get(guild_id_int, {})
                if guild_state.get('is_playing') and guild_state.get('current_sound'):
                    current_sound = guild_state['current_sound']
                    logging.info("")
                    logging.info("")
                    logging.info(f"🔍 Found current sound \033[36m{current_sound}\033[0m in {cog_name} for guild {guild_id}")
                    break

        if current_sound:
            cozy_gamification.finalize_current_sound(user_id)
            cozy_gamification.track_sound_start(user_id, current_sound, save_immediately=False)
            logging.info(f"🎵 Tracking \033[36m{current_sound}\033[0m for \033[35m{member.name}\033[0m")
        else:
            logging.warning(f"⚠️ No current sound found for \033[35m{member.name}\033[0m joining guild {guild_id}")

        # Save once after all operations
        cozy_gamification.save_user_data()
        cozy_gamification.save_usernames()
    except Exception as e:
        logging.error(f"❌ Error tracking user join: {e}")

# Track bot join in background to avoid blocking Discord connection
def _track_bot_join_sync(guild_id, guild_name, channel, current_users):
    try:
        from cogs.stats.gamification import cozy_gamification

        for user in current_users:
            user_id = str(user.id)
            user_voice_sessions[guild_id]['users'][user_id] = {
                'join_time': datetime.now(),
                'accumulated_time': 0.0
            }
            # Don't save immediately to avoid blocking the event loop
            cozy_gamification.update_username(user_id, user.name, user.global_name or user.name, save_immediately=False)
            cozy_gamification.join_session(user_id, user.name, save_immediately=False)
            logging.info("")
            logging.info(f"👉 USER JOIN: \033[35m{user.name}\033[0m was already in channel when bot joined {channel.name} in {guild_name}")

        # Save once after processing all users
        if current_users:
            cozy_gamification.save_user_data()
            cozy_gamification.save_usernames()

        # Restart tracking for users already in channel if bot is playing
        if current_users:
            voice_client = channel.guild.voice_client
            if voice_client and voice_client.is_playing():
                current_user_ids = [str(u.id) for u in current_users]
                cozy_gamification.reset_consecutive_time_for_guild(guild_id, current_user_ids)

                from cogs.audio.base_sound import global_current_sounds
                current_guild_sound = global_current_sounds.get(int(guild_id))

                if current_guild_sound:
                    for user in current_users:
                        # Don't save immediately to avoid blocking
                        cozy_gamification.track_sound_start(str(user.id), current_guild_sound, save_immediately=False)
                        logging.info(f"👉 RECONNECT FIX: Restarted tracking \033[36m{current_guild_sound}\033[0m for \\033[35m{user.name}\\033[0m")
                    # Save once after processing all users
                    cozy_gamification.save_user_data()
                else:
                    logging.info("👉 RECONNECT FIX: Bot is playing audio but couldn't identify current sound")
    except Exception as e:
        logging.error(f"❌ Error tracking bot join: {e}")

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

# Sound-category emojis matching the website's "listening now" header
# (buildLiveSoundCategories in the web app). Order matches the site too.
_SOUND_EMOJI_ORDER = ['🌧️', '🌊', '✨', '🎶', '📡', '🎵']

def _sound_category_emoji(sound_name):
    if sound_name.startswith('rain'):
        return '🌧️'
    if sound_name.startswith('sea'):
        return '🌊'
    if sound_name.startswith('sparkles'):
        return '✨'
    if sound_name.startswith('background-music'):
        return '🎶'
    if sound_name.startswith('white-noise') or sound_name.startswith('noise'):
        return '📡'
    return '🎵'

# Build the Telegram "N person/people listening" line, prefixed with the
# emojis of the sound categories currently being listened to (same emojis as
# the website's "listening now" header). Falls back to ✨ when nothing plays.
# Counts every human currently in any voice channel the bot is connected to,
# across all guilds. Pass exclude_channel to discount a channel the bot is
# about to leave (e.g. mid-disconnect, when bot.voice_clients still references it).
def _total_listeners_text(exclude_channel=None):
    from cogs.audio.base_sound import global_current_sounds

    total = 0
    playing_emojis = set()
    for guild in bot.guilds:
        vc = guild.voice_client
        if not vc or not vc.channel:
            continue
        if exclude_channel is not None and vc.channel.id == exclude_channel.id:
            continue
        humans = sum(1 for m in vc.channel.members if not m.bot)
        total += humans
        if humans:
            sound = global_current_sounds.get(guild.id)
            if sound:
                playing_emojis.add(_sound_category_emoji(sound))
    prefix = ''.join(e for e in _SOUND_EMOJI_ORDER if e in playing_emojis)
    if not prefix:
        prefix = '🚫' if total == 0 else '✨'
    suffix = "person listening" if total == 1 else "people listening"
    return f"{prefix} <b>{total}</b> {suffix}"


# Save voice time data to CouchDB
def save_voice_time_data(silent=False):
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()

        # Reload from CouchDB first to merge with any external changes (like API modifications)
        file_data = load_voice_time_data()

        # Merge: keep active sessions from memory, preserve CouchDB data for inactive sessions
        merged_data = file_data.copy()
        for guild_id, guild_data in guild_voice_time.items():
            # Use memory data if: active session (start_time is not None) OR guild not in file
            if (isinstance(guild_data, list) and len(guild_data) >= 1 and guild_data[0] is not None) or guild_id not in file_data:
                merged_data[guild_id] = guild_data

        db.save_voice_time_data(merged_data)

        if not silent:
            logging.info('✅ SERVER TIME SAVE: Saved successfully to CouchDB')

    except Exception as e:
        logging.error(f'❌ Failed to save voice time data to CouchDB: {e}')

# Load voice time data from CouchDB
def load_voice_time_data():
    try:
        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        return db.load_voice_time_data()
    except Exception:
        return {}

# Initialize global tracking variables
guild_voice_time = load_voice_time_data()
guild_voice_time_changes = {}
user_voice_sessions = {}
periodic_backup_task = None
background_tasks = set()  # Keep references to prevent garbage collection
_deploy_notifier_started = False
_audio_monitor_started = False

# Create background task and keep reference to prevent garbage collection
def create_background_task(coro):
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task

# Dynamic bot presence updates
@tasks.loop(seconds=10)
async def change_status():
    try:
        server_count = len(bot.guilds)
        if server_count == 0 and hasattr(change_status, '_last_count'):
            server_count = change_status._last_count
        else:
            change_status._last_count = server_count

        # Cycle through statuses
        if not hasattr(change_status, '_status_index'):
            change_status._status_index = 0

        statuses = [
            discord.Game(name=f"in {server_count} servers"),
            discord.Game(name="/menu"),
        ]

        status = statuses[change_status._status_index]
        await bot.change_presence(activity=status)
        change_status._status_index = (change_status._status_index + 1) % len(statuses)

    except (OSError, discord.ConnectionClosed):
        pass
    except Exception as e:
        logging.error(f"❌ Error updating bot status: {e}")

@change_status.before_loop
async def before_change_status():
    await bot.wait_until_ready()

# Periodic data backup task
@tasks.loop(seconds=600)
async def periodic_backup():
    try:
        from cogs.stats.gamification import cozy_gamification

        logging.info("")
        logging.info("")
        logging.info("🕐 PERIODIC BACKUP: Starting complete data backup...")

        active_session_updates = {}
        active_user_updates = {}
        
        # Process active server sessions
        for idx, (guild_id, guild_data) in enumerate(guild_voice_time.items()):
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
            if idx % 50 == 0:
                await asyncio.sleep(0)
        
        # Track users currently in voice with bot
        users_in_voice_with_bot = set()
        for idx, guild in enumerate(bot.guilds):
            if guild.voice_client and guild.voice_client.channel:
                for member in guild.voice_client.channel.members:
                    if not member.bot:
                        users_in_voice_with_bot.add(str(member.id))
            if idx % 50 == 0:
                await asyncio.sleep(0)
        
        # Process active user listening sessions
        for idx, (user_id, user_stats) in enumerate(cozy_gamification.user_data.items()):
            current_sound = user_stats.get('current_sound')
            if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                try:
                    if str(user_id) not in users_in_voice_with_bot:
                        username = cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                        logging.info(f"ℹ️ Removing session for {username}: not in voice with bot")

                        # Finalize the current sound before removing session to award remaining points
                        cozy_gamification.finalize_current_sound(user_id)
                        logging.info(f"👉 PERIODIC CLEANUP: Finalized session for {username}")
                        continue
                    
                    start_time = datetime.fromisoformat(current_sound['start_time'])
                    now = datetime.now()
                    session_duration = (now - start_time).total_seconds()
                    from cogs.audio.sound_mappings import normalize_sound_name
                    sound_name = normalize_sound_name(current_sound['name'])
                    current_sound['name'] = sound_name

                    # Advance start_time NOW, before crediting. If a concurrent
                    # finalize_current_sound is dispatched for the same user mid-loop,
                    # it will compute a near-zero duration off the new start_time
                    # instead of re-crediting the same window.
                    current_sound['start_time'] = now.isoformat()

                    # Cap session duration at 30 minutes to prevent corrupted data
                    max_session_duration = 30 * 60
                    if session_duration > max_session_duration:
                        username = cozy_gamification.usernames.get(str(user_id), {}).get("username", f"User {str(user_id)[:8]}")
                        logging.warning(f"⚠️ Removing old session for {username}: {session_duration/60:.1f}min old")
                        user_stats['current_sound'] = None
                        continue

                    if session_duration > 0:
                        user_stats['listening_time'] += session_duration

                        # Ensure daily streak updates even if join event was missed (UTC day boundary)
                        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
                        last_active = user_stats.get('last_active_date')
                        if last_active != today:
                            try:
                                from cogs.stats.gamification import cozy_gamification
                                if last_active and cozy_gamification.is_consecutive_day(last_active, today):
                                    user_stats['daily_streak'] += 1
                                else:
                                    user_stats['daily_streak'] = 1
                                user_stats['last_active_date'] = today
                            except Exception:
                                user_stats['daily_streak'] = 1
                                user_stats['last_active_date'] = today

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

                        # start_time was already advanced above (before crediting) — no need to repeat.

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
            if idx % 200 == 0:
                await asyncio.sleep(0)
        
        # Restart tracking for users who lost sessions after reconnection
        from cogs.stats.gamification import cozy_gamification
        users_with_active_sessions = set()
        for idx, (user_id, user_stats) in enumerate(cozy_gamification.user_data.items()):
            current_sound = user_stats.get('current_sound')
            if current_sound and isinstance(current_sound, dict) and 'start_time' in current_sound:
                users_with_active_sessions.add(str(user_id))
            if idx % 200 == 0:
                await asyncio.sleep(0)

        users_missing_sessions = users_in_voice_with_bot - users_with_active_sessions
        if users_missing_sessions:
            for idx, guild in enumerate(bot.guilds):
                if guild.voice_client and guild.voice_client.channel:
                    guild_id = str(guild.id)
                    from cogs.audio.base_sound import global_current_sounds
                    current_guild_sound = global_current_sounds.get(guild.id)

                    if current_guild_sound:
                        users_to_restore = []
                        for member in guild.voice_client.channel.members:
                            if not member.bot and str(member.id) in users_missing_sessions:
                                users_to_restore.append(member)
                                users_missing_sessions.remove(str(member.id))

                        # Batch save to avoid multiple CouchDB writes
                        for member in users_to_restore:
                            cozy_gamification.update_username(str(member.id), member.name, member.global_name or member.name, save_immediately=False)
                            cozy_gamification.track_sound_start(str(member.id), current_guild_sound, save_immediately=False)
                            logging.info(f"👉 RECONNECT FIX: Restarted session for \033[35m{member.name}\033[0m tracking \033[36m{current_guild_sound}\033[0m")

                        if users_to_restore:
                            await asyncio.to_thread(cozy_gamification.save_user_data)
                            await asyncio.to_thread(cozy_gamification.save_usernames)
                if idx % 50 == 0:
                    await asyncio.sleep(0)
        
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
                logging.info(f"  👉 {time_str} for {username} (\033[36m{update_info['sound']}\033[0m active session){points_str}")

        if guild_voice_time:
            await asyncio.to_thread(save_voice_time_data, silent=True)

        await asyncio.to_thread(cozy_gamification.save_user_data, force_detailed_log=True)
        logging.info("✅ PERIODIC BACKUP: Complete backup finished")

    except Exception as e:
        logging.error(f"❌ PERIODIC BACKUP FAILED: {e}")

    save_current_stats_for_api()

@periodic_backup.before_loop
async def before_periodic_backup():
    await bot.wait_until_ready()

# Save current bot stats for API access
def save_current_stats_for_api():
    try:
        active_listeners = 0
        servers_with_bot = 0
        listeners_by_sound = {}
        active_usernames = set()

        for guild in bot.guilds:
            voice_state = guild.voice_client
            if voice_state and voice_state.channel:
                servers_with_bot += 1
                human_members = [m for m in voice_state.channel.members if not m.bot]
                if human_members:
                    active_listeners += len(human_members)
                    for member in human_members:
                        active_usernames.add(member.name)
                    try:
                        from cogs.audio.base_sound import global_current_sounds
                        from cogs.audio.sound_mappings import normalize_sound_name
                        sound_name = global_current_sounds.get(guild.id)
                        if sound_name:
                            sound_name = normalize_sound_name(sound_name)
                            listeners_by_sound[sound_name] = listeners_by_sound.get(sound_name, 0) + len(human_members)
                    except Exception:
                        pass

        from cogs.stats.gamification import cozy_gamification
        total_servers = 0
        if hasattr(cozy_gamification, 'servernames'):
            total_servers = len(cozy_gamification.servernames)

        stats = {
            'current_listeners': active_listeners,
            'servers_with_bot': servers_with_bot,
            'total_servers': total_servers,
            'listeners_by_sound': listeners_by_sound,
            'active_usernames': sorted(active_usernames),
            'last_updated': datetime.now().isoformat()
        }

        from utils.storage.couchdb_client import get_couchdb_client
        db = get_couchdb_client()
        db.save_live_stats(stats)

    except Exception as e:
        logging.error(f'❌ Failed to save current stats: {e}')

# Schedule a live stats snapshot without blocking the event loop
LIVE_STATS_FLUSH_SECONDS = int(os.getenv("COZY_LIVE_STATS_FLUSH_SECONDS", "5"))
_live_stats_dirty = False
_live_stats_task_started = False
PLAYBACK_WATCHDOG_SECONDS = 10
PLAYBACK_WATCHDOG_COOLDOWN_SECONDS = 30
AUDIO_COG_NAMES = ['RainCog', 'SeaCog', 'SparklesCog', 'BackgroundMusicCog', 'NoiseCog']
# Wait for Discord's session teardown / discord.py's own reconnect attempt
# before repairing voice ourselves.
VOICE_RECOVERY_DELAY_SECONDS = 8
VOICE_RECONCILE_GRACE_SECONDS = 15

async def _live_stats_flush_loop():
    while True:
        try:
            await asyncio.to_thread(save_current_stats_for_api)
        except Exception as e:
            logging.error(f'❌ Live stats flush failed: {e}')
        await asyncio.sleep(LIVE_STATS_FLUSH_SECONDS)

@tasks.loop(seconds=PLAYBACK_WATCHDOG_SECONDS)
async def _playback_watchdog_loop():
    if not hasattr(_playback_watchdog_loop, 'last_restart_by_guild'):
        _playback_watchdog_loop.last_restart_by_guild = {}

    try:
        for guild in bot.guilds:
            voice_client = guild.voice_client

            for cog_name in AUDIO_COG_NAMES:
                cog = bot.get_cog(cog_name)
                if not cog or not hasattr(cog, 'guild_states'):
                    continue

                guild_state = cog.guild_states.get(guild.id)
                if not guild_state:
                    continue

                if guild_state.get('current_sound') and guild_state.get('is_playing'):
                    # A usable connection needs a live websocket. Zombie clients
                    # keep .channel set after a drop, and after a gateway
                    # re-IDENTIFY the registry can be wiped entirely
                    # (voice_client is None) while state says we should play.
                    connected = bool(voice_client and voice_client.channel and voice_client.is_connected())
                    if not connected or not voice_client.is_playing():
                        # Skip silently when the channel has no human listeners: the
                        # bot is about to auto-disconnect, "playback stalled" is not
                        # the real cause, and warning + spawning a restart task that
                        # will immediately bail just spams the logs.
                        listen_channel = voice_client.channel if connected else guild_state.get('target_channel')
                        if not listen_channel or not any(not m.bot for m in listen_channel.members):
                            continue
                        now = time.monotonic()
                        last_restart = _playback_watchdog_loop.last_restart_by_guild.get(guild.id, 0.0)
                        if now - last_restart < PLAYBACK_WATCHDOG_COOLDOWN_SECONDS:
                            continue
                        is_paused = voice_client.is_paused() if (voice_client and hasattr(voice_client, "is_paused")) else None
                        source = getattr(voice_client, "source", None) if voice_client else None
                        source_type = type(source).__name__ if source else None
                        logging.info(
                            "🔍 WATCHDOG CHECK: guild=%s channel=%s cog=%s "
                            "sound=%s connected=%s is_paused=%s source=%s",
                            guild.name,
                            listen_channel.name,
                            cog_name,
                            guild_state.get('current_sound'),
                            connected,
                            is_paused,
                            source_type,
                        )
                        logging.warning(
                            f"⚠️ Playback stalled in {guild.name} "
                            f"(sound={guild_state.get('current_sound')}, connected={connected}). Restarting..."
                        )
                        task = bot.loop.create_task(cog.restart_audio_loop(guild.id))
                        background_tasks.add(task)
                        task.add_done_callback(background_tasks.discard)
                        _playback_watchdog_loop.last_restart_by_guild[guild.id] = now
                    break
    except Exception as e:
        logging.error(f'❌ Playback watchdog failed: {e}')

@_playback_watchdog_loop.before_loop
async def before_playback_watchdog():
    await bot.wait_until_ready()

def _find_active_audio_cog(guild_id):
    """Returns the audio cog whose state says it should be playing in this guild."""
    for cog_name in AUDIO_COG_NAMES:
        cog = bot.get_cog(cog_name)
        if not cog or not hasattr(cog, 'guild_states'):
            continue
        state = cog.guild_states.get(guild_id)
        if state and state.get('current_sound') and state.get('is_playing'):
            return cog
    return None

_voice_recovery_pending = set()

async def _recover_voice_after_drop(guild):
    """The bot left voice while it was supposed to be playing.

    Waits out Discord's session teardown (reconnecting immediately races the
    old session's events into the new handshake), then reconnects through
    restart_audio_loop if listeners are still waiting. No-op when a stop or
    auto-disconnect already cleared the playing state, or when discord.py's
    internal reconnect already brought the connection back.
    """
    try:
        await asyncio.sleep(VOICE_RECOVERY_DELAY_SECONDS)
        cog = _find_active_audio_cog(guild.id)
        if cog is None:
            return
        voice_client = guild.voice_client
        if voice_client and voice_client.channel and voice_client.is_connected():
            return
        logging.warning(
            f"⚠️ Voice connection dropped in {guild.name} while playing. Attempting recovery..."
        )
        await cog.restart_audio_loop(guild.id)
    except Exception as e:
        logging.error(f"❌ Voice drop recovery failed for {guild.name}: {e}")
    finally:
        _voice_recovery_pending.discard(guild.id)

def _schedule_voice_recovery(guild):
    if guild.id in _voice_recovery_pending:
        return
    _voice_recovery_pending.add(guild.id)
    create_background_task(_recover_voice_after_drop(guild))

async def _reconcile_voice_clients(trigger):
    """Repair voice state after a gateway reconnect.

    on_ready/on_resumed fire again on every gateway reconnect. Two failure
    modes need repair: half-dead clients (websocket gone, .channel still set)
    and orphaned clients (discord.py wiped its registry on re-IDENTIFY without
    stopping them; their internal tasks sabotage every new handshake). Gives
    discord.py a grace period to recover on its own first.
    """
    try:
        await asyncio.sleep(VOICE_RECONCILE_GRACE_SECONDS)
        from cogs.audio.base_sound import reap_orphan_voice_clients, teardown_voice_client

        reaped = reap_orphan_voice_clients(bot)
        if reaped:
            logging.warning(f"⚠️ Voice reconcile ({trigger}): reaped {reaped} orphaned voice client(s)")

        for guild in bot.guilds:
            voice_client = guild.voice_client
            if not voice_client:
                continue
            if voice_client.channel and voice_client.is_connected():
                continue
            logging.warning(
                f"⚠️ Voice reconcile ({trigger}): tearing down dead voice client in {guild.name} "
                f"(channel={voice_client.channel}, is_connected={voice_client.is_connected()})"
            )
            await teardown_voice_client(guild)
            cog = _find_active_audio_cog(guild.id)
            if cog is not None:
                task = bot.loop.create_task(cog.restart_audio_loop(guild.id))
                background_tasks.add(task)
                task.add_done_callback(background_tasks.discard)
    except Exception as e:
        logging.error(f"❌ Voice reconcile ({trigger}) failed: {e}")

def schedule_live_stats_update():
    global _live_stats_dirty, _live_stats_task_started
    try:
        _live_stats_dirty = True
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running() and not _live_stats_task_started:
            _live_stats_task_started = True
            task = loop.create_task(_live_stats_flush_loop())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
    except Exception as e:
        logging.error(f'❌ Failed to schedule live stats update: {e}')

def start_bot_api_server():
    try:
        import uvicorn
        from live_api.app import app, set_bot_instance
        set_bot_instance(bot)
        uvicorn.run(app, host="0.0.0.0", port=BOT_API_PORT, log_level="warning")
    except Exception as e:
        logging.error(f"❌ Bot API server failed: {e}")

# Check all API endpoints health
async def check_api_endpoints():
    public_api_base = os.getenv("API_BASE_URL_PUBLIC", "http://api:8000")
    live_api_base = os.getenv("BOT_API_BASE_URL", "http://localhost:8002")

    apis = [
        {
            "name": "Public API",
            "emoji": "🔥",
            "base": public_api_base,
            "get_endpoints": [
                "/",
                "/health",
                "/api/public/health",
                "/api/public/total",
                "/api/public/top-users",
                "/api/public/top-sounds",
                "/api/public/top-servers",
                "/api/public/deployment/check-status",
                "/api/public/audio/restore-tasks",
                "/api/public/admin/debug/all-data"
            ],
            "write_endpoints": [
                ("POST", "/api/public/admin/points"),
                ("POST", "/api/public/admin/time"),
                ("POST", "/api/public/admin/add-sound"),
                ("POST", "/api/public/admin/server-time"),
                ("DELETE", "/api/public/admin/user")
            ]
        },
        {
            "name": "Live API",
            "emoji": "✨",
            "base": live_api_base,
            "get_endpoints": [
                "/health",
                "/api/live/bot/health",
                "/api/live/bot/stats"
            ],
            "write_endpoints": [
                ("POST", "/api/live/audio/save-state"),
                ("POST", "/api/live/audio/restore-state"),
                ("POST", "/api/live/audio/finalize-sessions"),
                ("POST", "/api/live/audio/restore-sessions"),
                ("POST", "/api/live/deployment/simple-notify")
            ]
        }
    ]

    logging.info("")
    logging.info("⚙️ Checking API endpoints...")

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        for api in apis:
            logging.info(f"{api['emoji']} {api['name']} endpoints:")
            for endpoint in api["get_endpoints"]:
                try:
                    async with session.get(f"{api['base']}{endpoint}", timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status in [200, 401, 403, 422]:
                            logging.info(f"{api['emoji']} GET {endpoint} - healthy")
                        else:
                            logging.error(f"{api['emoji']} GET {endpoint} - error (status: {response.status})")
                except Exception:
                    logging.error(f"{api['emoji']} GET {endpoint} - error")

            logging.info("")
            logging.info(f"{api['emoji']} Available write endpoints ({api['name']}): {len(api['write_endpoints'])}")
            for method, endpoint in api["write_endpoints"]:
                logging.info(f"{api['emoji']}    ╰┈➤ {method} {endpoint}")
            logging.info("")
    logging.info("")

# Global error handler for bot events
@bot.event
async def on_error(event, *args, **kwargs):
    import sys
    # Pull the current exception so the formatter can render a real traceback;
    # otherwise we just log the event name and have no idea what actually broke.
    logging.error(f"Unhandled exception in event '{event}'", exc_info=sys.exc_info())

# Handle voice state changes for tracking
@bot.event
async def on_voice_state_update(member, before, after):
    # The bot's own voice session ended (kick, voice-server migration, or a
    # dead websocket discord.py gave up on). This is the only reliable signal
    # that voice died (on_disconnect/on_resumed do not cover voice), so it runs
    # regardless of the tracking config. Recovery is a no-op when a stop or
    # auto-disconnect already cleared the playing state.
    if member.id == bot.user.id and before.channel is not None and after.channel is None:
        _schedule_voice_recovery(member.guild)

    # Skip tracking if disabled to avoid blocking voice handshake
    if not COZY_ENABLE_VOICE_TRACKING:
        return
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

            current_users = [m for m in after.channel.members if not m.bot]
            logging.info("")
            logging.info("")
            logging.info(f"👉 BOT JOIN: Connected to {after.channel.name} in {member.guild.name} - {len(current_users)} users already present")

            try:
                from utils.telegram_notifier import notify as tg_notify
                tg_notify(_total_listeners_text())
            except Exception:
                pass

            # Track in background to not block Discord connection
            create_background_task(asyncio.to_thread(_track_bot_join_sync, guild_id, member.guild.name, after.channel, current_users))
            schedule_live_stats_update()

        # Bot left voice channel
        elif before.channel is not None and after.channel is None:
            duplicate_disconnect_event = False
            session_duration = 0.0
            total_time = 0.0

            if guild_id in guild_voice_time:
                guild_data = guild_voice_time[guild_id]
                if isinstance(guild_data, list) and len(guild_data) >= 2:
                    start_at = guild_data[0]
                    accumulated_time = finite_float(guild_data[1], default=0.0)
                    total_time = accumulated_time
                    if start_at is None:
                        duplicate_disconnect_event = True
                    else:
                        try:
                            start_time = datetime.fromisoformat(start_at)
                            time_spent = datetime.now() - start_time
                            session_duration = max(0.0, finite_float(time_spent.total_seconds(), default=0.0))
                            total_time = accumulated_time + session_duration
                        except Exception:
                            logging.warning(
                                f"⚠️ Invalid guild_data format for {guild_id}, preserved accumulated time: "
                                f"{format_duration(accumulated_time)}"
                            )
                            session_duration = 0.0
                            total_time = accumulated_time

                    guild_voice_time[guild_id] = [None, total_time]
                else:
                    accumulated_time = 0.0
                    if isinstance(guild_data, list) and len(guild_data) >= 2:
                        accumulated_time = finite_float(guild_data[1], default=0.0)
                    guild_voice_time[guild_id] = [None, accumulated_time]
                    total_time = accumulated_time
                    duplicate_disconnect_event = True

                if not duplicate_disconnect_event:
                    if guild_id not in guild_voice_time_changes:
                        guild_voice_time_changes[guild_id] = 0
                    guild_voice_time_changes[guild_id] += session_duration
                    logging.info("")
                    logging.info("")
                    logging.info(
                        f"👋 BOT DISCONNECT: Left {before.channel.guild.name} - session: "
                        f"\033[94m+{format_duration(session_duration)}\033[0m, server total: "
                        f"\033[94m{format_duration(total_time)}\033[0m"
                    )
                    logging.info(f"🏠 \033[94m+{format_duration(session_duration)}\033[0m for {before.channel.guild.name}")

                    try:
                        from utils.telegram_notifier import notify as tg_notify
                        # The bot just dropped this voice client; compute the new total without it.
                        tg_notify(_total_listeners_text(exclude_channel=before.channel))
                    except Exception:
                        pass

                    create_background_task(asyncio.to_thread(save_voice_time_data))
                    schedule_live_stats_update()
                else:
                    logging.info(f"🔁 Ignored duplicate bot disconnect event in {before.channel.guild.name}")

            session = user_voice_sessions.pop(guild_id, None)
            if session:
                from cogs.stats.gamification import cozy_gamification

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

        logging.info("")
        logging.info(f"👉 USER JOIN: \033[35m{member.name}\033[0m joined bot channel {after.channel.name} in {member.guild.name}")

        try:
            from utils.telegram_notifier import notify as tg_notify
            tg_notify(_total_listeners_text())
        except Exception:
            pass

        # Track in background to avoid blocking Discord events
        create_background_task(asyncio.to_thread(_track_user_join_sync, user_id, member, guild_id))
        schedule_live_stats_update()

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

            try:
                from utils.telegram_notifier import notify as tg_notify
                tg_notify(_total_listeners_text())
            except Exception:
                pass

            cozy_gamification.finalize_current_sound(user_id)
            logging.info(f"👉 SOUND TRACKING: Finalized current sound for \033[35m{member.name}\033[0m")

            del session['users'][user_id] 
            schedule_live_stats_update()

# Bot ready event handler
@bot.event
async def on_ready():
    from utils.logging_utils import print_ascii_banner
    print_ascii_banner()

    # System information
    from utils.logging_utils import log_system_info
    log_system_info()

    # Check FFmpeg availability
    from utils.logging_utils import log_ffmpeg_info
    log_ffmpeg_info()

    # Docker/Network information
    from utils.logging_utils import log_network_info
    log_network_info()

    # Discord Intents
    from utils.logging_utils import log_discord_intents
    log_discord_intents(bot.intents)

    # Check voice dependencies
    from utils.logging_utils import log_voice_dependencies
    log_voice_dependencies()

    # Timezone and locale
    from utils.logging_utils import log_locale_info
    log_locale_info()

    try:
        from api.routes.stats import set_bot_instance
        set_bot_instance(bot)
        logging.info('🔗 Bot instance shared with API for LIVE access')
    except Exception as e:
        logging.warning(f'⚠️ Could not share bot instance with API: {e}')

    # audio_restore no longer needs bot_instance — the audio mutation endpoints
    # were deduped into the live API (see live_api/app.py). The public API's
    # audio_restore module only exposes a read-only CouchDB endpoint now.

    try:
        from api.routes.health import set_bot_instance as set_health_bot_instance
        set_health_bot_instance(bot)
        logging.info('🔗 Bot instance shared with health check API')
    except Exception as e:
        logging.warning(f'⚠️ Could not share bot instance with health check API: {e}')

    logging.info(f'✨ {bot.user.name} is ready and connected!')

    # Bot Discord information
    from utils.logging_utils import log_bot_info, log_application_info
    log_bot_info(bot)
    await log_application_info(bot)

    try:
        logging.info('👉 Syncing application commands...')
        synced = await bot.tree.sync()
        logging.info(f'✅ Synced {len(synced)} application commands!')
    except Exception as e:
        logging.error(f'❌ Error syncing commands: {e}')

    from utils.logging_utils import log_startup_complete
    log_startup_complete()

    if COZY_ENABLE_API_CHECKS:
        await check_api_endpoints()

    if not change_status.is_running():
        change_status.start()

    if COZY_ENABLE_BACKUPS:
        global periodic_backup_task
        if not periodic_backup.is_running():
            periodic_backup.start()
            periodic_backup_task = periodic_backup
            logging.info('🕐 Started periodic backup task')
        else:
            logging.info('🕐 Periodic backup task already running')

    # on_ready fires again after gateway reconnects: guard the one-shot
    # monitors like the task loops above, or each reconnect leaks a duplicate.
    if COZY_ENABLE_DEPLOY_NOTIFIER:
        global _deploy_notifier_started
        if not _deploy_notifier_started:
            _deploy_notifier_started = True
            deployment_notifier = DeploymentNotifier(bot)
            task = bot.loop.create_task(deployment_notifier.start_monitoring())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
            logging.info('📢 Started deployment notifier task')
        else:
            logging.info('📢 Deployment notifier task already running')

    if not _playback_watchdog_loop.is_running():
        _playback_watchdog_loop.start()
    logging.info('🎧 Started playback watchdog task')

    if COZY_ENABLE_AUDIO_RESTORE:
        global _audio_monitor_started
        if not _audio_monitor_started:
            _audio_monitor_started = True
            audio_monitor = AudioRestorationMonitor(bot)
            task = bot.loop.create_task(audio_monitor.start_monitoring())
            background_tasks.add(task)
            task.add_done_callback(background_tasks.discard)
            logging.info('🎵 Started audio restoration monitor task')
        else:
            logging.info('🎵 Audio restoration monitor already running')

    # Repair voice connections the gateway reconnect may have left half-dead
    # or orphaned (this on_ready may be a reconnect, not the first startup).
    create_background_task(_reconcile_voice_clients('on_ready'))

    # Python packages summary
    from utils.logging_utils import log_python_packages
    log_python_packages()

    # CouchDB statistics summary
    if COZY_ENABLE_COUCHDB_SUMMARY:
        from cogs.stats.gamification import cozy_gamification
        from utils.logging_utils import log_couchdb_summary
        log_couchdb_summary(cozy_gamification, guild_voice_time)

    # Global statistics and connected servers
    from utils.logging_utils import log_global_statistics, log_connected_servers
    log_global_statistics(bot, cozy_gamification)
    log_connected_servers(bot)

# Gateway session resumed: existing voice connections may have died during the
# gap without emitting any event. Verify and repair them.
@bot.event
async def on_resumed():
    create_background_task(_reconcile_voice_clients('on_resumed'))

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
            ('cogs.audio.noise.noise', '📡'),
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

        logging.info('')
        logging.info('🔧 Loading bot extensions...')
        for ext_name, emoji in extensions:
            await bot.load_extension(ext_name)
            # Add extra space for emojis that take more visual space
            if emoji == '🌧️':
                space = '  '
            elif emoji == '🗑️':
                space = '  '
            else:
                space = ' '
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
    # Welcome message
    print("✨ Welcome to CozyBot CLI v2.0.5 by @kitsuiwebster\n")

    loop = asyncio.get_event_loop()
    if COZY_ENABLE_BOT_API:
        threading.Thread(target=start_bot_api_server, daemon=True).start()

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
