import discord
from discord import app_commands
from discord.ext import commands

from .base_sound import AUDIO_COG_NAMES, get_guild_audio_lock, global_current_sounds

# Cog for stopping audio playback and disconnecting bot
class StopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stop", description="Stop the sound and disconnect the bot")
    async def stop_command(self, interaction: discord.Interaction):
        guild = interaction.guild

        if not guild.voice_client:
            await interaction.response.send_message("❌ I'm not connected to any voice channel!", ephemeral=True)
            return

        # The lock can be held by a restart/connect in flight, so defer first.
        await interaction.response.defer()

        # Serialize with the watchdog/button/timer paths for this guild.
        async with get_guild_audio_lock(guild.id):
            voice_client = guild.voice_client
            if not voice_client:
                await interaction.followup.send("❌ I'm not connected to any voice channel!")
                return

            # Clear every cog's playing state BEFORE disconnecting so neither
            # the watchdog nor the voice-drop recovery brings the bot back.
            for cog_name in AUDIO_COG_NAMES:
                cog = self.bot.get_cog(cog_name)
                if not cog or not hasattr(cog, 'guild_states'):
                    continue
                state = cog.guild_states.get(guild.id)
                if not state:
                    continue
                state['is_playing'] = False
                state['current_sound'] = None
                if state.get('disconnect_timer'):
                    state['disconnect_timer'].cancel()
                    state['disconnect_timer'] = None
            global_current_sounds.pop(guild.id, None)

            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()

        await interaction.followup.send("Stopped playing and disconnected from voice channel!")

async def setup(bot):
    await bot.add_cog(StopCog(bot))
