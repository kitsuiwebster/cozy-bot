import discord
from discord import app_commands
from discord.ext import commands

# Cog for displaying menu of available commands and welcoming new servers
class MenuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Show interactive menu with all sound commands
    @app_commands.command(name="menu", description="Display all available sound commands")
    async def menu_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            description=(
                "**Available Commands**\n\n"
                "🌧️ `/rain` • 10 rain ambiances\n"
                "🌊 `/sea` • 5 ocean sounds\n"
                "✨ `/sparkles` • 5 magical sounds\n"
                "🎶 `/music` • 5 background tracks\n"
                "🤍 `/noise` • 5 noise variations"
            ),
            color=0x2b2d31
        )

        await interaction.response.send_message(embed=embed)

    # Send welcome message when bot joins a new server
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        # Try to find a suitable channel to send the welcome message
        # Priority: system channel > general channel > first text channel
        target_channel = None

        # Try system channel first
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            target_channel = guild.system_channel

        # Try to find a "general" channel
        if not target_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    if 'general' in channel.name.lower() or 'chat' in channel.name.lower():
                        target_channel = channel
                        break

        # Fallback to first available text channel
        if not target_channel:
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    target_channel = channel
                    break

        if not target_channel:
            return  # No channel available

        # Create welcome embed
        embed = discord.Embed(
            title="Thanks for adding CozyBot",
            description=(
                "Relax and focus with 30+ ambient sounds.\n\n"
                "**Get Started**\n"
                "Join a voice channel and use `/menu`\n\n"
                "**Commands**\n"
                "`/menu` • `/profile` • `/top-users`"
            ),
            color=0x2b2d31
        )

        embed.set_footer(text="CozyBot • Ambient sounds for relaxation")

        try:
            await target_channel.send(embed=embed)
        except discord.Forbidden:
            pass  # No permissions to send message

async def setup(bot):
    await bot.add_cog(MenuCog(bot))
