import discord
from discord import app_commands
from discord.ext import commands
from .gamification import cozy_gamification
import asyncio

class SyncUsernamesCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sync-usernames", description="[ADMIN] Sync all usernames for existing users")
    async def sync_usernames_command(self, interaction: discord.Interaction):
        # Check if user is admin (you can customize this check)
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is admin-only!", ephemeral=True)
            return

        await interaction.response.defer()
        
        try:
            synced_count = 0
            skipped_count = 0
            
            # Get all user IDs from gamification data
            all_user_ids = list(cozy_gamification.user_data.keys())
            
            for user_id in all_user_ids:
                try:
                    # Try to fetch user from Discord
                    user = await self.bot.fetch_user(int(user_id))
                    if user:
                        # Save both real username and global display name
                        cozy_gamification.update_username(user_id, user.name, user.global_name or user.display_name)
                        synced_count += 1
                    else:
                        skipped_count += 1
                        
                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    skipped_count += 1
                    print(f"Failed to fetch user {user_id}: {e}")
            
            await interaction.followup.send(
                f"✅ Username sync complete!\n"
                f"📊 **Results:**\n"
                f"• Synced: {synced_count} users\n"
                f"• Skipped: {skipped_count} users\n"
                f"• Total: {len(all_user_ids)} users"
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during sync: {e}")

    @app_commands.command(name="sync-servers", description="[ADMIN] Sync server names for servers with statistics")
    async def sync_servers_command(self, interaction: discord.Interaction):
        # Check if user is admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ This command is admin-only!", ephemeral=True)
            return

        await interaction.response.defer()
        
        try:
            synced_count = 0
            skipped_count = 0
            
            # Load voice time data to see which servers have stats
            import json
            import os
            try:
                with open('data/voice_time_data.json', 'r') as f:
                    voice_stats = json.load(f)
            except FileNotFoundError:
                await interaction.followup.send("❌ No voice statistics found!")
                return
            
            # Sync only guilds that have voice statistics
            for guild_id_str in voice_stats.keys():
                try:
                    guild_id = int(guild_id_str)
                    guild = self.bot.get_guild(guild_id)
                    if guild:
                        cozy_gamification.update_servername(guild_id_str, guild.name)
                        synced_count += 1
                    else:
                        skipped_count += 1
                except Exception as e:
                    skipped_count += 1
                    print(f"Failed to sync server {guild_id_str}: {e}")
            
            await interaction.followup.send(
                f"✅ Server names sync complete!\n"
                f"📊 **Results:**\n"
                f"• Synced: {synced_count} servers with stats\n"
                f"• Skipped: {skipped_count} servers (bot not in guild)\n"
                f"• Total servers with stats: {len(voice_stats)}\n"
                f"• Total bot guilds: {len(self.bot.guilds)}"
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during server sync: {e}")

async def setup(bot):
    await bot.add_cog(SyncUsernamesCog(bot))