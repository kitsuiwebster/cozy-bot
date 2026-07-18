import asyncio
import json
import os
import glob
import logging
from datetime import datetime

# Monitor and process audio restoration tasks after deployment or reconnection
class AudioRestorationMonitor:
    def __init__(self, bot):
        self.bot = bot
        self.check_interval = 5  # Check every 5 seconds

    # Start monitoring for audio restoration tasks
    async def start_monitoring(self):
        await self.bot.wait_until_ready()
        
        # Wait a bit for bot to be fully ready before checking for restore tasks
        await asyncio.sleep(3)
        
        # First check if there's a main audio state file to convert to individual tasks
        from .audio_state_manager import audio_state_manager
        if audio_state_manager:
            restored = audio_state_manager.restore_audio_state(self.bot)
            if restored > 0:
                logging.info(f"📦 Converted {restored} audio states to restore tasks")
        
        await self.process_pending_tasks()
        
        # Continue monitoring for new tasks
        while not self.bot.is_closed():
            try:
                await self.process_pending_tasks()
                await asyncio.sleep(self.check_interval)
                    
            except Exception as e:
                logging.error(f"❌ Error in audio restoration monitor: {e}")
                await asyncio.sleep(10)

    # Process any pending audio restoration tasks
    async def process_pending_tasks(self):
        try:
            await self.process_pending_couchdb_tasks()
            restore_files = glob.glob('data/restore_task_*.json')
            
            if not restore_files:
                return
                
            logging.info(f"🎵 Found {len(restore_files)} pending audio restoration tasks")
            
            for file_path in restore_files:
                try:
                    await self.process_restore_task(file_path)
                except Exception as e:
                    logging.error(f"❌ Failed to process restore task {file_path}: {e}")
                    # Clean up failed task file
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
                        
        except Exception as e:
            logging.error(f"❌ Error processing pending tasks: {e}")

    async def process_pending_couchdb_tasks(self):
        try:
            from utils.storage.couchdb_client import get_couchdb_client
            db = get_couchdb_client()
            tasks = db.get_all_restore_tasks()
            if not tasks:
                return

            logging.info(f"🎵 Found {len(tasks)} pending audio restoration tasks")

            for task_id, task_data in tasks.items():
                try:
                    guild_id = int(task_id)
                    channel_id = int(task_data.get('channel_id'))
                    sound_name = task_data.get('sound_name')
                    if not channel_id or not sound_name:
                        logging.warning(f"⚠️ Invalid restore task data for guild {task_id}, deleting task")
                        db.delete_restore_task(task_id)
                        continue

                    guild = self.bot.get_guild(guild_id)
                    if not guild:
                        logging.warning(f"⚠️ Guild {guild_id} not found for restore task")
                        db.delete_restore_task(task_id)
                        continue

                    channel = guild.get_channel(channel_id)
                    if not channel:
                        logging.warning(f"⚠️ Channel {channel_id} not found in {guild.name} for restore task")
                        db.delete_restore_task(task_id)
                        continue

                    current_users = [member for member in channel.members if not member.bot]
                    if not current_users:
                        logging.info(f"⏭️ Skipping restore for {guild.name} - no users in voice channel")
                        db.delete_restore_task(task_id)
                        continue

                    await self.restore_audio_in_channel(guild, channel, sound_name)
                    db.delete_restore_task(task_id)
                    logging.info(f"✅ Audio restoration task completed for {guild.name}")

                except Exception as e:
                    logging.error(f"❌ Failed to process restore task {task_id}: {e}")
                    # Avoid infinite retries on bad tasks
                    try:
                        db.delete_restore_task(task_id)
                    except Exception:
                        pass
        except Exception as e:
            logging.error(f"❌ Error processing CouchDB restore tasks: {e}")

    # Process a single audio restoration task
    async def process_restore_task(self, file_path):
        try:
            loop = asyncio.get_event_loop()

            def read_task_file():
                with open(file_path, 'r') as f:
                    return json.load(f)

            task_data = await loop.run_in_executor(None, read_task_file)
            
            guild_id = int(task_data['guild_id'])
            channel_id = int(task_data['channel_id'])
            sound_name = task_data['sound_name']
            
            guild = self.bot.get_guild(guild_id)
            if not guild:
                logging.warning(f"⚠️ Guild {guild_id} not found for restore task")
                os.remove(file_path)
                return
            
            channel = guild.get_channel(channel_id)
            if not channel:
                logging.warning(f"⚠️ Channel {channel_id} not found for restore task")
                os.remove(file_path)
                return
            
            # Check if any users are still in the voice channel
            current_users = [member for member in channel.members if not member.bot]
            if not current_users:
                logging.info(f"⏭️ Skipping restore for {guild.name} - no users in voice channel")
                os.remove(file_path)
                return
            
            # Try to restore audio
            await self.restore_audio_in_channel(guild, channel, sound_name)
            
            # Clean up task file
            os.remove(file_path)
            logging.info(f"✅ Audio restoration task completed for {guild.name}")
            
        except Exception as e:
            logging.error(f"❌ Error processing restore task {file_path}: {e}")
            raise

    # Restore audio playback in a specific channel
    async def restore_audio_in_channel(self, guild, channel, sound_name):
        from cogs.audio.base_sound import (
            get_guild_audio_lock,
            global_current_sounds,
            known_voice_clients,
            teardown_voice_client,
        )

        # Serialize with the button/watchdog/timer paths for this guild.
        async with get_guild_audio_lock(guild.id):
            await self._restore_audio_in_channel_locked(
                guild, channel, sound_name,
                global_current_sounds, known_voice_clients, teardown_voice_client,
            )

    async def _restore_audio_in_channel_locked(self, guild, channel, sound_name,
                                               global_current_sounds, known_voice_clients,
                                               teardown_voice_client):
        try:
            # Check if bot is already connected to voice in this guild.
            # The connection must have a live websocket, not just exist:
            # half-dead clients keep .channel set and crash play().
            voice_client = guild.voice_client

            if voice_client and voice_client.channel and voice_client.is_connected():
                # Bot is already connected, just start the sound
                logging.info(f"🎵 Bot already connected to voice in {guild.name}, starting {sound_name}")
            else:
                if voice_client:
                    # Dead leftover client: tear it down or the fresh connect
                    # below cannot complete its handshake.
                    await teardown_voice_client(guild)
                # Connect to the voice channel
                voice_client = await channel.connect()
                known_voice_clients[guild.id] = voice_client
                logging.info(f"🔗 Connected to voice channel in {guild.name}")

            # Play the sound directly using Discord.py
            from discord import FFmpegPCMAudio
            import os

            # Determine the sound file path based on sound name
            sound_path = self.get_sound_file_path(sound_name)
            if not sound_path or not os.path.exists(sound_path):
                logging.error(f"❌ Sound file not found: {sound_name}")
                return

            # Update the corresponding cog's guild_state first
            cog_name = self.get_cog_name_for_sound(sound_name)
            cog = None
            if cog_name:
                cog = self.bot.get_cog(cog_name)
                if cog and hasattr(cog, 'guild_states'):
                    guild_state = cog.get_guild_state(guild.id)
                    guild_state['is_playing'] = True
                    guild_state['current_sound'] = sound_name
                    guild_state['target_channel'] = channel
                    logging.info(f"✅ Updated {cog_name} guild_state for {guild.name}")
                    # Arm the empty-channel auto-disconnect for the restored
                    # session (it used to be armed only on user-initiated
                    # connects, leaving restored sessions immortal).
                    await cog.start_disconnect_timer(guild.id)

            # Play the audio with callback for looping (removed -stream_loop for instant start)
            audio_source = FFmpegPCMAudio(
                sound_path,
                before_options='-stream_loop -1 -loglevel error',
            )
            # Use the cog's after_playing callback if available
            if cog and hasattr(cog, 'after_playing'):
                voice_client.play(audio_source, after=lambda e: cog.after_playing(e, guild.id))
            else:
                voice_client.play(audio_source)

            # Update global state to track what's playing
            global_current_sounds[guild.id] = sound_name

            # Update gamification current_sound for each user in the channel
            from cogs.stats.gamification import cozy_gamification
            current_users = [member for member in channel.members if not member.bot]

            logging.info("")
            logging.info("")
            logging.info(f"🎵 SOUND RESTORE: \033[36m{sound_name}\033[0m in {channel.name} ({guild.name}) - {len(current_users)} users listening")

            # Finalize any previous sounds and reset consecutive time
            for member in current_users:
                cozy_gamification.finalize_current_sound(str(member.id))

            user_ids = [str(member.id) for member in current_users]
            cozy_gamification.reset_consecutive_time_for_guild(guild.id, user_ids)

            # Start tracking the restored sound for each user
            for member in current_users:
                try:
                    cozy_gamification.update_username(str(member.id), member.name, member.global_name or member.name)
                    cozy_gamification.track_sound_start(str(member.id), sound_name)
                    logging.info(f"🎵 Tracking \033[36m{sound_name}\033[0m for \033[35m{member.name}\033[0m")
                except Exception as e:
                    logging.error(f"❌ Failed to start sound tracking for {member.name}: {e}")

            logging.info(f"🎵 Successfully restored {sound_name} in {guild.name}")
                
        except Exception as e:
            logging.error(f"❌ Failed to restore audio in {guild.name}: {e}")
            raise

    # Get the cog name for a given sound
    def get_cog_name_for_sound(self, sound_name):
        if sound_name.startswith('rain'):
            return 'RainCog'
        elif sound_name.startswith('sea'):
            return 'SeaCog'
        elif sound_name.startswith('sparkles'):
            return 'SparklesCog'
        elif sound_name.startswith('background-music'):
            return 'BackgroundMusicCog'
        elif sound_name.startswith('white-noise'):
            return 'NoiseCog'
        return None

    # Get the full path to a sound file based on its name
    def get_sound_file_path(self, sound_name):
        # Map of sound categories to their directories
        sound_categories = {
            'rain': 'cogs/audio/rain/',
            'sea': 'cogs/audio/sea/', 
            'sparkles': 'cogs/audio/sparkles/',
            'background_music': 'cogs/audio/background_music/',
            'noise': 'cogs/audio/noise/'
        }
        
        # Try to find the file in each category
        for category, directory in sound_categories.items():
            file_path = os.path.join(directory, sound_name)
            if os.path.exists(file_path):
                return file_path
        
        # If not found with full name, try to match partial names
        import glob
        for category, directory in sound_categories.items():
            pattern = os.path.join(directory, f"*{sound_name}*")
            matches = glob.glob(pattern)
            if matches:
                return matches[0]
        
        logging.warning(f"⚠️ Sound file not found: {sound_name}")
        return None
