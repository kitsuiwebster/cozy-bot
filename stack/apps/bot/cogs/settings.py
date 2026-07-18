import asyncio

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View

from utils import guild_settings


def build_settings_embed(guild):
    always_on = guild_settings.is_always_on(guild.id)
    embed = discord.Embed(title="⚙️ Server Settings", color=discord.Color.blurple())
    embed.add_field(
        name="📡 24/7 Mode",
        value=(
            "Keeps the bot connected to the voice channel even when it's empty.\n"
            f"Status: {'🟢 Enabled' if always_on else '⚪ Disabled'}"
        ),
        inline=False,
    )
    return embed


class SettingsView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self._refresh()

    def _refresh(self):
        button = self.children[0]
        if guild_settings.is_always_on(self.guild_id):
            button.style = discord.ButtonStyle.success
            button.label = "24/7: ON"
        else:
            button.style = discord.ButtonStyle.secondary
            button.label = "24/7: OFF"

    @discord.ui.button(label="24/7", emoji="📡", style=discord.ButtonStyle.secondary, custom_id="cozy_settings_247")
    async def toggle_247(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need the **Manage Server** permission to change bot settings.", ephemeral=True
            )
            return

        enabled = not guild_settings.is_always_on(self.guild_id)
        # CouchDB write is blocking HTTP: keep it off the event loop.
        saved = await asyncio.to_thread(guild_settings.set_always_on, self.guild_id, enabled)
        if not saved:
            await interaction.response.send_message(
                "❌ Could not save the setting, please try again.", ephemeral=True
            )
            return

        self._refresh()
        await interaction.response.edit_message(embed=build_settings_embed(interaction.guild), view=self)


# Cog for per-server bot settings
class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="settings", description="Configure CozyBot for this server")
    async def settings_command(self, interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message("❌ This command only works in a server.", ephemeral=True)
            return

        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "❌ You need the **Manage Server** permission to view bot settings.", ephemeral=True
            )
            return

        # First access may hit CouchDB: load off the event loop.
        await asyncio.to_thread(guild_settings.preload)
        await interaction.response.send_message(
            embed=build_settings_embed(interaction.guild),
            view=SettingsView(interaction.guild.id),
        )


async def setup(bot):
    await bot.add_cog(SettingsCog(bot))
