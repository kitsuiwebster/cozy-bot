"""
Logging utilities for CozyBot
Provides logging configuration, formatters, and startup information display
"""
import logging
import sys
import os
import platform
import subprocess
import socket
import time
import locale as locale_module


class FancyFormatter(logging.Formatter):
    """Custom log formatter with colors and emojis"""

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
        line = f"{color}{emoji_padded}[{timestamp}] {record.levelname:<8} {reset}{record.getMessage()}"
        # Append traceback when the log call passed exc_info=True or a logger
        # (like discord.py's) attached an exception to the record. Without this
        # the bot silently swallows every "Ignoring exception" stack trace.
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        elif record.exc_text:
            line += "\n" + record.exc_text
        return line


class _LogFilter(logging.Filter):
    """Filter to suppress noisy Discord warnings"""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "Privileged message content intent is missing" in msg:
            return False
        return True


def setup_logging(discord_log_level: str = "WARNING"):
    """
    Configure enhanced logging system with visual formatting

    Args:
        discord_log_level: Log level for Discord library (DEBUG/INFO/WARNING/ERROR/CRITICAL)
    """
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

    # Apply log filter
    handler.addFilter(_LogFilter())

    # Telegram operational alerts (warning+). Attached at WARNING so it stays
    # quiet during normal runs; the notifier itself short-circuits when
    # TELEGRAM_ENABLED != "1", so this is a no-op if not configured.
    from .telegram_log_handler import TelegramLogHandler
    telegram_handler = TelegramLogHandler(level=logging.WARNING)
    telegram_handler.addFilter(_LogFilter())
    logger.addHandler(telegram_handler)

    # Set Discord log level
    discord_log_level_value = getattr(logging, discord_log_level.upper(), logging.WARNING)
    discord_logger.setLevel(discord_log_level_value)

    # Enable full Discord logging (voice + gateway + HTTP + websocket)
    discord_logger_names = [
        'discord',
        'discord.client',
        'discord.gateway',
        'discord.http',
        'discord.voice',
        'discord.voice_client',
        'discord.voice_state',
        'discord.ws',
    ]
    for logger_name in discord_logger_names:
        logging.getLogger(logger_name).setLevel(discord_log_level_value)


def print_ascii_banner():
    """Print the CozyBot ASCII art banner"""
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
    print("║                      Version 2.0.5                              ║")
    print("║            by @kitsuiwebster & @BubbleXGum                      ║")
    print("║                                                                 ║")
    print("╚═════════════════════════════════════════════════════════════════╝")
    print("="*60 + "\n")


def log_system_info():
    """Log system and environment information"""
    try:
        import discord
        discord_version = discord.__version__
    except Exception:
        discord_version = "unknown"

    try:
        import nacl
        nacl_version = nacl.__version__
    except Exception:
        nacl_version = "unknown"

    try:
        import aiohttp
        aiohttp_version = aiohttp.__version__
    except Exception:
        aiohttp_version = "unknown"

    logging.info("")
    logging.info(f"🐍 Python version: {sys.version.split()[0]}")
    logging.info(f"🐍 discord.py version: {discord_version}")
    logging.info(f"🔐 PyNaCl version: {nacl_version}")
    logging.info(f"🌐 aiohttp version: {aiohttp_version}")
    logging.info(f"💻 Platform: {platform.system()} {platform.release()}")
    logging.info(f"🏗️ Architecture: {platform.machine()}")
    logging.info(f"🔧 Python implementation: {platform.python_implementation()}")


def log_ffmpeg_info():
    """Log FFmpeg availability and version"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=2)
        ffmpeg_first_line = result.stdout.split('\n')[0] if result.stdout else "unknown"
        # Keep only version info to avoid long line
        ffmpeg_short = ffmpeg_first_line.split("Copyright")[0].strip()
        logging.info(f"🎵 FFmpeg: {ffmpeg_short}")
    except Exception as e:
        logging.warning(f"⚠️ FFmpeg check failed: {e}")


def log_network_info():
    """Log Docker/Network information"""
    # Container info
    try:
        hostname = socket.gethostname()
        logging.info(f"📦 Container hostname: {hostname}")
    except Exception as e:
        logging.warning(f"⚠️ Could not get hostname: {e}")

    # Get container IP
    try:
        container_ip = socket.gethostbyname(socket.gethostname())
        logging.info(f"🌐 Container IP: {container_ip}")
    except Exception as e:
        logging.warning(f"⚠️ Could not get container IP: {e}")

    # Get DNS servers
    try:
        with open('/etc/resolv.conf', 'r') as f:
            dns_servers = [line.split()[1] for line in f if line.startswith('nameserver')]
            if dns_servers:
                logging.info(f"🔍 DNS servers: {', '.join(dns_servers)}")
    except Exception as e:
        logging.warning(f"⚠️ Could not read DNS config: {e}")

    # Get default gateway
    try:
        result = subprocess.run(['ip', 'route'], capture_output=True, text=True, timeout=2)
        for line in result.stdout.split('\n'):
            if line.startswith('default'):
                gateway = line.split()[2]
                logging.info(f"⛩️ Default gateway: {gateway}")
                break
    except Exception as e:
        logging.debug(f"Could not get gateway: {e}")


def log_discord_intents(intents):
    """
    Log enabled Discord intents

    Args:
        intents: discord.Intents object
    """
    intent_list = []
    if intents.guilds: intent_list.append("guilds")
    if intents.members: intent_list.append("members")
    if intents.message_content: intent_list.append("message_content")
    if intents.voice_states: intent_list.append("voice_states")
    if intents.presences: intent_list.append("presences")
    if intents.typing: intent_list.append("typing")

    if intent_list:
        logging.info(f"✅ Enabled intents: {', '.join(intent_list)}")
    else:
        logging.info("❌ No intents enabled")

    if not intents.voice_states:
        logging.error("❌ CRITICAL: voice_states intent is NOT enabled! Voice will NOT work!")


def log_voice_dependencies():
    """Log voice-related dependencies status"""
    logging.info("")

    # Check libsodium (for voice encryption)
    try:
        logging.info("✅ libsodium (PyNaCl): Available")
    except Exception as e:
        logging.error(f"❌ libsodium check failed: {e}")

    # Check voice client availability
    try:
        from discord.voice_client import VoiceClient
        logging.info("✅ VoiceClient: Available")
    except Exception as e:
        logging.error(f"❌ VoiceClient import failed: {e}")


def log_locale_info():
    """Log timezone and locale information"""
    logging.info("")

    # Timezone
    try:
        tz_name = time.tzname[time.daylight]
        utc_offset = time.timezone if not time.daylight else time.altzone
        offset_hours = -utc_offset // 3600
        logging.info(f"🕐 Timezone: {tz_name} (UTC{offset_hours:+d})")
    except Exception as e:
        logging.warning(f"⚠️ Could not get timezone: {e}")

    # Locale
    try:
        current_locale = locale_module.getlocale()
        logging.info(f"🌐 Locale: {current_locale[0] if current_locale[0] else 'C'}")
    except Exception as e:
        logging.warning(f"⚠️ Could not get locale: {e}")


def log_bot_info(bot):
    """
    Log bot Discord information

    Args:
        bot: discord.ext.commands.Bot instance
    """
    logging.info("")
    logging.info(f"👤 Bot name: {bot.user.name}#{bot.user.discriminator}")
    logging.info(f"🆔 Bot User ID: {bot.user.id}")

    # Shard info
    if bot.shard_id is not None:
        logging.info(f"🔀 Shard ID: {bot.shard_id}/{bot.shard_count}")
    else:
        logging.info("🔀 Sharding: Not enabled (single process)")


async def log_application_info(bot):
    """
    Log bot application information (async)

    Args:
        bot: discord.ext.commands.Bot instance
    """
    try:
        app_info = await bot.application_info()
        if app_info.bot_public:
            logging.info("🌍 Bot visibility: Public")
        else:
            logging.info("🔒 Bot visibility: Private")
    except Exception as e:
        logging.warning(f"⚠️ Could not fetch app info: {e}")


def log_python_packages():
    """Log installed Python packages"""
    try:
        import pkg_resources
        installed_packages = [(d.project_name, d.version) for d in pkg_resources.working_set]
        installed_packages.sort(key=lambda x: x[0].lower())

        logging.info('')
        logging.info('📦 Python packages:')
        for package_name, version in installed_packages:
            logging.info(f'   ╰┈➤ {package_name} {version}')
    except Exception as e:
        logging.warning(f'⚠️ Could not list Python packages: {e}')


def log_couchdb_summary(cozy_gamification, guild_voice_time):
    """
    Log CouchDB storage statistics

    Args:
        cozy_gamification: Gamification cog instance
        guild_voice_time: Guild voice time tracking dict
    """
    logging.info('')
    logging.info('📂 CouchDB storage:')
    logging.info(f'   ╰┈➤ 📂 {len(cozy_gamification.user_data)} user records')
    logging.info(f'   ╰┈➤ 📂 {len(cozy_gamification.usernames)} username cache entries')
    logging.info(f'   ╰┈➤ 📂 {len(cozy_gamification.servernames)} server cache entries')
    logging.info(f'   ╰┈➤ 📂 {len(guild_voice_time)} voice time tracking records')


def log_global_statistics(bot, cozy_gamification):
    """
    Log global bot statistics

    Args:
        bot: discord.ext.commands.Bot instance
        cozy_gamification: Gamification cog instance
    """
    server_count = len(bot.guilds)
    total_member_count = sum(guild.member_count for guild in bot.guilds)

    # Calculate global statistics
    total_cozy_points = sum(user.get('total_points', 0) for user in cozy_gamification.user_data.values())
    total_sessions = sum(user.get('sessions_joined', 0) for user in cozy_gamification.user_data.values())
    total_listening_seconds = sum(user.get('listening_time', 0) for user in cozy_gamification.user_data.values())

    # Format total time
    total_hours = total_listening_seconds // 3600
    total_minutes = (total_listening_seconds % 3600) // 60

    logging.info('')
    logging.info(f'   ╰┈➤ 👥 {total_member_count:,} server members')
    logging.info(f'   ╰┈➤ 🏠 {server_count} servers')
    logging.info(f'   ╰┈➤ ⭐ {total_cozy_points:,} total cozy points')
    logging.info(f'   ╰┈➤ 🎵 {total_sessions:,} total sound sessions')
    logging.info(f'   ╰┈➤ ⏱️  {total_hours:,}h {total_minutes}m total time spent')


def log_connected_servers(bot):
    """
    Log list of connected Discord servers

    Args:
        bot: discord.ext.commands.Bot instance
    """
    logging.info('')
    logging.info('🏠 Connected servers:')
    # Sort guilds by member count in descending order (most populated first)
    sorted_guilds = sorted(bot.guilds, key=lambda guild: guild.member_count, reverse=True)
    for guild in sorted_guilds:
        logging.info(f'   ╰┈➤ {guild.name} ({guild.member_count:,} members)')


def log_startup_complete():
    """Log startup completion message"""
    logging.info('🚀 Bot startup complete - All systems operational')
