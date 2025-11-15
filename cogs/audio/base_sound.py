import discord
from discord import FFmpegPCMAudio, ButtonStyle, app_commands
from discord.ext import commands
from discord.ui import Button, View
import os
import random
import asyncio
import logging
from ..stats.gamification import cozy_gamification

# Abstract base view component for audio command interfaces
class BaseSoundView(View):
    def __init__(self, sounds, sound_labels, user_id, bot, cog_name):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        self.sounds = sounds
        self.sound_labels = sound_labels
        self.cog_name = cog_name

        # Generate interactive button components for sound selection
        for sound in self.sounds:
            button = Button(style=ButtonStyle.secondary, label=self.sound_labels[sound], custom_id=sound)
            button.callback = self.on_button_click
            self.add_item(button)

        # Add stop control button to interface
        stop_button = Button(style=ButtonStyle.danger, label="Stop", emoji="⏹", custom_id="stop")
        stop_button.callback = self.on_button_click
        self.add_item(stop_button)

    async def on_button_click(self, interaction):
        # Validate interaction authorization against command initiator
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who typed the command can use these buttons.😵‍💫 Use the commands instead.", ephemeral=True)
            return
        
        # Extract component identifier from interaction payload
        custom_id = interaction.data.get('custom_id')
        
        # Process audio playback termination request
        if custom_id == "stop":
            guild_id = interaction.guild.id
            await self.bot.get_cog(self.cog_name).stop_sound(interaction, guild_id)
        else: 
            # Process audio file selection request
            await self.bot.get_cog(self.cog_name).on_button_click(interaction)

# Abstract base cog for audio command functionality
class BaseSoundCog(commands.Cog):
    def __init__(self, bot, sound_type, sounds, sound_labels, description):
        self.bot = bot
        self.sound_type = sound_type
        self.sounds = sounds
        self.sound_labels = sound_labels
        self.description = description
        self.guild_states = {}

    async def play_sound_command(self, interaction, prompt_message):
        """Shared command execution logic for audio playback commands"""
        await interaction.response.defer()

        # Validate user voice channel presence requirement
        if interaction.user.voice is None:
            await interaction.followup.send(content="You need to be in a voice channel to use this command.😵", ephemeral=True)
            return

        # Store user's voice channel for later connection
        user_channel = interaction.user.voice.channel
        guild_state = self.get_guild_state(interaction.guild.id)
        guild_state['target_channel'] = user_channel

        # Render interactive sound selection interface (bot connects when sound is chosen)
        view = BaseSoundView(self.sounds, self.sound_labels, interaction.user.id, self.bot, self.__class__.__name__)
        await interaction.followup.send(prompt_message, view=view)

    def get_guild_state(self, guild_id):
        """Retrieve or initialize guild-specific state management"""
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = {
                'is_playing': False,
                'current_sound': None,
                'loop_task': None,
                'target_channel': None,
                'disconnect_timer': None,
            }
        return self.guild_states[guild_id]

    def after_playing(self, error, guild_id):
        """Audio playback completion callback handler with automatic loop restart"""
        guild_state = self.get_guild_state(guild_id)
        
        if error:
            logging.error(f"❌ Player error: {error}")
            # Retry after error if we were playing something
            if guild_state['current_sound'] and guild_state['is_playing']:
                asyncio.create_task(self.restart_audio_loop(guild_id))
        else:
            # Automatically restart the same audio for continuous loop
            if guild_state['current_sound'] and guild_state['is_playing']:
                asyncio.create_task(self.restart_audio_loop(guild_id))
            else:
                logging.warning(f"❌ Not restarting - current_sound: {guild_state['current_sound']}, is_playing: {guild_state['is_playing']}")

    async def on_button_click(self, interaction):
        """Process audio file selection interactions"""
        await interaction.response.defer()
        
        guild_id = interaction.guild.id
        guild_state = self.get_guild_state(guild_id)
        
        # Extract audio file identifier from interaction data
        sound_filename = interaction.data.get('custom_id')
        
        # Check if the same sound is already playing (only if bot is actively playing)
        voice_client = interaction.guild.voice_client
        if (guild_state.get('current_sound') == sound_filename and 
            guild_state.get('is_playing') and 
            voice_client and 
            voice_client.is_playing()):
            await interaction.followup.send("❌ This sound is already playing! Choose a different sound or stop playback first.", ephemeral=True)
            return
        
        # Connect to voice channel if not already connected, or move to user's channel
        # voice_client already defined above
        user_channel = guild_state.get('target_channel')
        
        if voice_client is None:
            # Not connected, connect to user's channel
            if user_channel:
                # Retry logic for Discord voice connection issues
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        # Add timeout to prevent hanging connections
                        voice_client = await asyncio.wait_for(user_channel.connect(), timeout=20.0)
                        # Start disconnect timer for empty channel monitoring
                        await self.start_disconnect_timer(guild_id)
                        break  # Success, exit retry loop
                    except asyncio.TimeoutError:
                        if attempt == max_retries - 1:  # Last attempt
                            await interaction.followup.send("❌ Connection to voice channel timed out after multiple attempts. Discord voice servers may be unstable.", ephemeral=True)
                            return
                        await asyncio.sleep(3)  # Wait before retry
                    except Exception as e:
                        if attempt == max_retries - 1:  # Last attempt
                            await interaction.followup.send(f"❌ Failed to connect to voice channel: {str(e)}", ephemeral=True)
                            return
                        await asyncio.sleep(2)  # Wait before retry
            else:
                await interaction.followup.send("❌ No target voice channel found", ephemeral=True)
                return
        else:
            # Already connected, move to user's channel if different
            if user_channel and voice_client.channel != user_channel:
                try:
                    # Add timeout to prevent hanging on move operations
                    await asyncio.wait_for(voice_client.move_to(user_channel), timeout=10.0)
                except asyncio.TimeoutError:
                    await interaction.followup.send("❌ Failed to move to voice channel: timeout. Please try again.", ephemeral=True)
                    return
                except Exception as e:
                    await interaction.followup.send(f"❌ Failed to move to voice channel: {str(e)}", ephemeral=True)
                    return
        
        # Stop current audio and play new sound
        if voice_client.is_playing():
            voice_client.stop()
        
        # Play new audio directly
        try:
            # Determine command type from filename
            if sound_filename.startswith('rain'):
                sound_path = f"cogs/audio/rain/{sound_filename}"
            elif sound_filename.startswith('sea'):
                sound_path = f"cogs/audio/sea/{sound_filename}"
            elif sound_filename.startswith('sparkles'):
                sound_path = f"cogs/audio/sparkles/{sound_filename}"
            elif sound_filename.startswith('background-music'):
                sound_path = f"cogs/audio/background_music/{sound_filename}"
            else:
                sound_path = f"cogs/audio/{sound_filename}"
            if os.path.exists(sound_path):
                # Use FFmpeg infinite loop - SIMPLE AND WORKS!
                audio_source = FFmpegPCMAudio(sound_path, before_options='-stream_loop -1')
                voice_client.play(audio_source)
                
                guild_state['is_playing'] = True
                guild_state['current_sound'] = sound_filename
                
                # Track sound start for current users
                from cogs.stats.gamification import cozy_gamification
                voice_client = interaction.guild.voice_client
                if voice_client and voice_client.channel:
                    current_users = [member for member in voice_client.channel.members if not member.bot]
                    logging.info(f"🎵 SOUND START: {sound_filename} in {voice_client.channel.name} ({interaction.guild.name}) - {len(current_users)} users listening")
                    for member in current_users:
                        cozy_gamification.track_sound_start(member.id, sound_filename)
                        logging.info(f"🎵 Tracking {sound_filename} for \033[35m{member.name}\033[0m")
                
                sound_label = self.sound_labels.get(sound_filename, sound_filename)
                await interaction.followup.send(f"🎵 Now playing: {sound_label}")
            else:
                await interaction.followup.send(f"❌ Sound file not found: {sound_filename}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error playing sound: {str(e)}", ephemeral=True)

    async def start_disconnect_timer(self, guild_id):
        """Start timer to disconnect bot if channel becomes empty"""
        guild_state = self.get_guild_state(guild_id)
        
        # Cancel existing timer if any
        if guild_state['disconnect_timer']:
            guild_state['disconnect_timer'].cancel()
        
        # Start new timer task
        guild_state['disconnect_timer'] = asyncio.create_task(self.disconnect_timer_task(guild_id))
    
    async def disconnect_timer_task(self, guild_id):
        """Timer task that disconnects bot after 2 minutes if channel is empty"""
        try:
            while True:
                await asyncio.sleep(120)  # Wait 2 minutes
                
                guild = self.bot.get_guild(guild_id)
                if not guild or not guild.voice_client:
                    break
                
                voice_client = guild.voice_client
                if not voice_client.channel:
                    break
                
                # Check if there are real users (not bots) in the channel
                human_members = [m for m in voice_client.channel.members if not m.bot]
                
                if not human_members:
                    # Channel is empty, disconnect
                    guild_state = self.get_guild_state(guild_id)
                    
                    if voice_client.is_playing():
                        voice_client.stop()
                    await voice_client.disconnect()
                    guild_state['is_playing'] = False
                    guild_state['current_sound'] = None
                    guild_state['disconnect_timer'] = None
                    
                    logging.info(f"👋 AUTO-DISCONNECT: Left empty voice channel in {guild.name}")
                    break
                else:
                    # Still has users, continue monitoring
                    continue
                    
        except asyncio.CancelledError:
            # Timer was cancelled (normal when new user joins or manual stop)
            pass
        except Exception as e:
            logging.error(f"❌ Error in disconnect timer: {e}")

    async def stop_sound(self, interaction, guild_id):
        """Terminate active audio playback session and disconnect"""
        await interaction.response.defer()
        
        guild_state = self.get_guild_state(guild_id)
        voice_client = interaction.guild.voice_client
        
        # Finalize sound sessions for all users before stopping
        from cogs.stats.gamification import cozy_gamification
        if voice_client and voice_client.channel:
            current_users = [member for member in voice_client.channel.members if not member.bot]
            logging.info(f"🛑 SOUND STOP: Finalizing sound tracking for {len(current_users)} users in {voice_client.channel.name} ({interaction.guild.name})")
            for member in current_users:
                cozy_gamification.finalize_current_sound(member.id)
                logging.info(f"🛑 Finalized sound tracking for {member.name}")
        
        # Cancel disconnect timer
        if guild_state['disconnect_timer']:
            guild_state['disconnect_timer'].cancel()
            guild_state['disconnect_timer'] = None
        
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            guild_state['is_playing'] = False
            guild_state['current_sound'] = None
            await interaction.followup.send("⏹️ Stopped playing and left voice channel.")
        else:
            await interaction.followup.send("❌ No sound is currently playing.", ephemeral=True)

    async def restart_audio_loop(self, guild_id):
        """Restart audio for continuous looping"""
        try:
            guild_state = self.get_guild_state(guild_id)
            voice_client = guild_state.get('voice_client')
            current_sound = guild_state['current_sound']
            
            # Get voice client from guild if not in state
            if not voice_client:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    voice_client = guild.voice_client
            
            # Only restart if we should still be playing
            if not current_sound or not guild_state['is_playing'] or not voice_client:
                return
                
            # Small delay to avoid rapid restart issues
            await asyncio.sleep(0.1)
            
            # Find the correct sound path - use same logic as on_button_click
            if current_sound.startswith('rain'):
                sound_path = f"cogs/audio/rain/{current_sound}"
            elif current_sound.startswith('sea'):
                sound_path = f"cogs/audio/sea/{current_sound}"
            elif current_sound.startswith('sparkles'):
                sound_path = f"cogs/audio/sparkles/{current_sound}"
            elif current_sound.startswith('background-music'):
                sound_path = f"cogs/audio/background_music/{current_sound}"
            else:
                sound_path = f"cogs/audio/{current_sound}"
            
            # Restart audio if file exists and voice client is ready
            if os.path.exists(sound_path) and voice_client.is_connected() and not voice_client.is_playing():
                audio_source = FFmpegPCMAudio(sound_path)
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
            
        except Exception as e:
            logging.error(f"❌ Failed to restart audio loop: {e}")
            # Try again after a longer delay if restart failed
            await asyncio.sleep(1)
            guild_state = self.get_guild_state(guild_id)
            if guild_state['is_playing'] and guild_state['current_sound']:
                asyncio.create_task(self.restart_audio_loop(guild_id))


