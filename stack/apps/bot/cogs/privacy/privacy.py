import discord
from discord import app_commands
from discord.ext import commands

# Cog for handling GDPR data deletion requests
class PrivacyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # Command to handle GDPR data deletion requests
    @app_commands.command(name="delete-request", description="Request deletion of your personal data")
    async def delete_request_command(self, interaction: discord.Interaction):
        # Create informative embed
        embed = discord.Embed(
            title="🗑️ Data Deletion Request",
            description="To request deletion of your personal data from CozyBot, please follow the instructions below:",
            color=0xff6b6b  # Red color for deletion
        )
        
        # Add user information
        global_display_name = interaction.user.global_name or interaction.user.name
        embed.add_field(
            name="📝 Your Information",
            value=f"**User ID:** {interaction.user.id}\n**Username:** {interaction.user.name}\n**Global Display Name:** {global_display_name}",
            inline=False
        )
        
        # Add contact instructions
        embed.add_field(
            name="📧 Contact Information",
            value="Please send an email to **contact@kitsuiwebster.com** with the following information:",
            inline=False
        )
        
        # Add required information
        embed.add_field(
            name="✅ Required Information",
            value=("• Your Discord User ID: `{}`\n"
                   "• Your Discord Username: `{}`\n"
                   "• Subject: \"CozyBot Data Deletion Request\"\n"
                   "• Reason for deletion (optional)").format(
                       interaction.user.id, 
                       interaction.user.name
                   ),
            inline=False
        )
        
        # Add data information
        embed.add_field(
            name="📊 Data We Store",
            value=("• Listening time and session data\n"
                   "• Cozy points and achievements\n"
                   "• Username and display name cache\n"
                   "• Sound preferences and statistics"),
            inline=False
        )
        
        # Add processing time
        embed.add_field(
            name="⏰ Processing Time",
            value="Data deletion requests are typically processed within **7 business days**.",
            inline=False
        )
        
        # Add footer
        embed.set_footer(text="This action complies with GDPR Article 17 (Right to Erasure)")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(PrivacyCog(bot))