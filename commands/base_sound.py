import discord
from discord import FFmpegPCMAudio, ButtonStyle, app_commands
from discord.ext import commands
from discord.ui import Button, View
import os
import random
import asyncio
from cozy_gamification import cozy_gamification

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
                'session_users': set(),
                'session_start_time': None,
            }
        return self.guild_states[guild_id]

    def after_playing(self, error, guild_id):
        """Audio playback completion callback handler"""
        guild_state = self.get_guild_state(guild_id)
        if error:
            print(f"Player error: {error}")
        else:
            # Handle loop state transitions on playback completion
            if guild_state['current_sound']:
                guild_state['is_playing'] = False

    async def on_button_click(self, interaction):
        """Process audio file selection interactions"""
        await interaction.response.defer()
        
        guild_id = interaction.guild.id
        guild_state = self.get_guild_state(guild_id)
        
        # Extract audio file identifier from interaction data
        sound_filename = interaction.data.get('custom_id')
        
        # Connect to voice channel if not already connected, or move to user's channel
        voice_client = interaction.guild.voice_client
        user_channel = guild_state.get('target_channel')
        
        if voice_client is None:
            # Not connected, connect to user's channel
            if user_channel:
                try:
                    voice_client = await user_channel.connect()
                    # Start disconnect timer for empty channel monitoring
                    await self.start_disconnect_timer(guild_id)
                except Exception as e:
                    await interaction.followup.send(f"❌ Failed to connect to voice channel: {str(e)}", ephemeral=True)
                    return
            else:
                await interaction.followup.send("❌ No target voice channel found", ephemeral=True)
                return
        else:
            # Already connected, move to user's channel if different
            if user_channel and voice_client.channel != user_channel:
                try:
                    await voice_client.move_to(user_channel)
                except Exception as e:
                    await interaction.followup.send(f"❌ Failed to move to voice channel: {str(e)}", ephemeral=True)
                    return
        
        # Stop current audio and play new sound
        if voice_client.is_playing():
            voice_client.stop()
        
        # Play new audio directly
        try:
            sound_path = f"sounds/{sound_filename}"
            if os.path.exists(sound_path):
                audio_source = FFmpegPCMAudio(sound_path)
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
                
                guild_state['is_playing'] = True
                guild_state['current_sound'] = sound_filename
                
                # Start gamification tracking
                await self.start_gamification_session(interaction, guild_state, sound_filename)
                
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
                    print(f"🤖 Auto-disconnected from empty voice channel in {guild.name}")
                    break
                else:
                    # Still has users, continue monitoring
                    continue
                    
        except asyncio.CancelledError:
            # Timer was cancelled (normal when new user joins or manual stop)
            pass
        except Exception as e:
            print(f"Error in disconnect timer: {e}")

    async def stop_sound(self, interaction, guild_id):
        """Terminate active audio playback session and disconnect"""
        await interaction.response.defer()
        
        guild_state = self.get_guild_state(guild_id)
        voice_client = interaction.guild.voice_client
        
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

    async def start_gamification_session(self, interaction, guild_state, sound_filename):
        """Start tracking user session for gamification"""
        from datetime import datetime
        
        # Track users in voice channel
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.channel:
            current_users = {member.id for member in voice_client.channel.members if not member.bot}
            
            # Award points for joining session
            for user_id in current_users:
                if user_id not in guild_state['session_users']:
                    result = cozy_gamification.join_session(user_id)
                    if result and result.get('new_achievements'):
                        # Notify about new achievements (optional)
                        pass
            
            guild_state['session_users'] = current_users
            guild_state['session_start_time'] = datetime.now()
            
            # Track sound preference
            for user_id in current_users:
                cozy_gamification.track_sound_preference(user_id, sound_filename)

    async def update_listening_time(self, guild_id):
        """Update listening time for all users in session"""
        from datetime import datetime
        
        guild_state = self.get_guild_state(guild_id)
        if not guild_state['session_start_time'] or not guild_state['session_users']:
            return
        
        # Calculate session duration
        session_duration = (datetime.now() - guild_state['session_start_time']).total_seconds()
        
        # Award points for listening time
        for user_id in guild_state['session_users']:
            result = cozy_gamification.add_listening_time(user_id, session_duration)
            if result and result.get('new_achievements'):
                # Could notify about achievements here
                pass
        
        # Reset session timer
        guild_state['session_start_time'] = datetime.now()

