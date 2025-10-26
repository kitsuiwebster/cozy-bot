import discord
from discord import FFmpegPCMAudio, ButtonStyle, app_commands
from discord.ext import commands
from discord.ui import Button, View
import os
import random

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

        channel = interaction.user.voice.channel
        # Establish or migrate voice channel connection
        try:
            if interaction.guild.voice_client is None:
                await channel.connect()
            else:
                await interaction.guild.voice_client.move_to(channel)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to connect to voice channel: {str(e)}", ephemeral=True)
            return

        # Render interactive sound selection interface
        view = BaseSoundView(self.sounds, self.sound_labels, interaction.user.id, self.bot, self.__class__.__name__)
        await interaction.followup.send(prompt_message, view=view)

    def get_guild_state(self, guild_id):
        """Retrieve or initialize guild-specific state management"""
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = {
                'is_playing': False,
                'current_sound': None,
                'loop_task': None
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
        
        # Terminate active audio playback session
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
        
        # Extract audio file identifier from interaction data
        sound_filename = interaction.data.get('custom_id')
        
        # Initialize audio playback for selected file
        try:
            sound_path = f"sounds/{sound_filename}"
            if os.path.exists(sound_path):
                audio_source = FFmpegPCMAudio(sound_path)
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
                
                guild_state['is_playing'] = True
                guild_state['current_sound'] = sound_filename
                
                sound_label = self.sound_labels.get(sound_filename, sound_filename)
                await interaction.followup.send(f"🎵 Now playing: {sound_label}")
            else:
                await interaction.followup.send(f"❌ Sound file not found: {sound_filename}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error playing sound: {str(e)}", ephemeral=True)

    async def stop_sound(self, interaction, guild_id):
        """Terminate active audio playback session"""
        await interaction.response.defer()
        
        guild_state = self.get_guild_state(guild_id)
        voice_client = interaction.guild.voice_client
        
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            guild_state['is_playing'] = False
            guild_state['current_sound'] = None
            await interaction.followup.send("⏹️ Stopped playing.")
        else:
            await interaction.followup.send("❌ No sound is currently playing.", ephemeral=True)