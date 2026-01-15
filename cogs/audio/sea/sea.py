import discord
from discord import app_commands
from discord.ext import commands
from ..base_sound import BaseSoundCog

# Cog for playing sea sounds
class SeaCog(BaseSoundCog):
    def __init__(self, bot):
        sounds = ["sea00.mp3", "sea01.mp3", "sea02.mp3", "sea03.mp3", "sea04.mp3"]
        sound_labels = {
            "sea00.mp3": "🌊💧💦",
            "sea01.mp3": "🌊🕊️⛱️",
            "sea02.mp3": "🌊🏝️🌙",
            "sea03.mp3": "🌊⛵🕊️",
            "sea04.mp3": "🌊🤿🔱",
        }
        super().__init__(bot, "sea", sounds, sound_labels, "Play the sound of sea.🌊")

    @app_commands.command(name="sea", description="Play the sound of sea")
    async def sea_command(self, interaction: discord.Interaction):
        await self.play_sound_command(interaction, "Please select a sea sound:")

async def setup(bot):
    await bot.add_cog(SeaCog(bot))