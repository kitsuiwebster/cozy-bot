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
                    except:
                        pass
                        
        except Exception as e:
            logging.error(f"❌ Error processing pending tasks: {e}")

    # Process a single audio restoration task
    async def process_restore_task(self, file_path):
        try:
            with open(file_path, 'r') as f:
                task_data = json.load(f)
            
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
        try:
            # Check if bot is already connected to voice in this guild
            voice_client = guild.voice_client
            
            if voice_client:
                # Bot is already connected, just start the sound
                logging.info(f"🎵 Bot already connected to voice in {guild.name}, starting {sound_name}")
            else:
                # Connect to the voice channel
                voice_client = await channel.connect()
                logging.info(f"🔗 Connected to voice channel in {guild.name}")
            
            # Play the sound directly using Discord.py
            from discord import FFmpegPCMAudio
            import os
            
            # Determine the sound file path based on sound name
            sound_path = self.get_sound_file_path(sound_name)
            if not sound_path or not os.path.exists(sound_path):
                logging.error(f"❌ Sound file not found: {sound_name}")
                return
            
            # Play the audio with infinite loop
            audio_source = FFmpegPCMAudio(sound_path, before_options='-loglevel error -stream_loop -1')
            voice_client.play(audio_source)

            # Update global state to track what's playing
            from cogs.audio.base_sound import global_current_sounds
            global_current_sounds[guild.id] = sound_name

            # Update the corresponding cog's guild_state
            cog_name = self.get_cog_name_for_sound(sound_name)
            if cog_name:
                cog = self.bot.get_cog(cog_name)
                if cog and hasattr(cog, 'guild_states'):
                    guild_state = cog.get_guild_state(guild.id)
                    guild_state['is_playing'] = True
                    guild_state['current_sound'] = sound_name
                    guild_state['target_channel'] = channel
                    logging.info(f"✅ Updated {cog_name} guild_state for {guild.name}")

            # Update gamification current_sound for each user in the channel
            from cogs.stats.gamification import cozy_gamification
            current_users = [member for member in channel.members if not member.bot]
            for member in current_users:
                try:
                    cozy_gamification.track_sound_start(str(member.id), sound_name)
                except Exception as e:
                    logging.error(f"❌ Failed to start sound tracking for {member.name}: {e}")

            if current_users:
                logging.info(f"✅ Started sound tracking for {len(current_users)} users in {guild.name}")

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