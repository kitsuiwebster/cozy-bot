import discord
from discord import app_commands
from discord.ext import commands

class StopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="stop", description="Stop the sound and disconnect the bot")
    async def stop_command(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        
        if voice_client:
            # Stop any currently playing audio
            if voice_client.is_playing():
                voice_client.stop()
            
            # Disconnect from voice channel
            await voice_client.disconnect()
            await interaction.response.send_message("Stopped playing and disconnected from voice channel!")
        else:
            await interaction.response.send_message("❌ I'm not connected to any voice channel!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(StopCog(bot))