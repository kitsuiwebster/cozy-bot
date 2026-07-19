import discord
from discord import app_commands
from discord.ext import commands
from ..base_sound import BaseSoundCog
from ..sound_mappings import SOUND_LABELS

# Cog for playing noise sounds
class NoiseCog(BaseSoundCog):
    def __init__(self, bot):
        sounds = ["white-noise00.mp3", "white-noise01.mp3", "pink-noise01.mp3", "white-noise03.mp3", "white-noise04.mp3"]
        sound_labels = {sound: SOUND_LABELS[sound] for sound in sounds}
        super().__init__(bot, "noise", sounds, sound_labels, "Play differnet types of noises.📡")

    # Override to add work in progress message for unavailable sounds
    async def on_button_click(self, interaction):
        sound_filename = interaction.data.get('custom_id')

        # Check if this is a work in progress sound
        wip_sounds = ["white-noise00.mp3", "white-noise03.mp3", "white-noise04.mp3"]
        if sound_filename in wip_sounds:
            await interaction.response.send_message(
                "🚧 **Work in Progress** 🚧\n\nThis noise sound is currently being prepared and will be available soon!\n\nTry **📡🤍🌌** in the meantime.",
                ephemeral=True
            )
            return

        # For available sounds, use parent method
        await super().on_button_click(interaction)

    @app_commands.command(name="noise", description="Play different types of noises")
    async def noise_command(self, interaction: discord.Interaction):
        await self.play_sound_command(interaction, "Please select a noise sound:")

async def setup(bot):
    await bot.add_cog(NoiseCog(bot))