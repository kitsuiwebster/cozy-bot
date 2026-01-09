import asyncio
import json
import os
import logging
from datetime import datetime

class DeploymentNotifier:
    def __init__(self, bot):
        self.bot = bot
        self.notification_file = 'data/deployment_notification.json'
        self.check_interval = 2  # Check every 2 seconds
        
    async def start_monitoring(self):
        """Start monitoring for deployment notifications"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                if os.path.exists(self.notification_file):
                    await self.handle_deployment_notification()
                    
                await asyncio.sleep(self.check_interval)
                    
            except Exception as e:
                logging.error(f"❌ Error in deployment notifier: {e}")
                await asyncio.sleep(5)
    
    async def handle_deployment_notification(self):
        """Handle a pending deployment notification"""
        try:
            with open(self.notification_file, 'r') as f:
                data = json.load(f)
            
            if data.get("status") != "pending":
                return
            
            version = data.get("version", "unknown")
            delay_seconds = data.get("delay_seconds", 30)
            active_guilds = data.get("active_guilds", [])
            total_users = data.get("total_users", 0)
            
            logging.info(f"📢 Processing deployment notification for version {version}")
            
            # Send notifications to each active guild
            notifications_sent = 0
            
            for guild_info in active_guilds:
                try:
                    guild_id = int(guild_info['guild_id'])
                    guild = self.bot.get_guild(guild_id)
                    
                    if not guild:
                        continue
                    
                    # Create user mentions
                    user_mentions = []
                    for user_id in guild_info['user_ids']:
                        user_mentions.append(f'<@{user_id}>')
                    
                    mentions_text = ' '.join(user_mentions)
                    
                    # Create message
                    message = (
                        f"🔄 **CozyBot Update {version}**\n"
                        f"Hey {mentions_text}!\n\n"
                        f"📢 Bot update will deploy in **{delay_seconds} seconds**\n"
                        f"⏱️ Expected downtime: **<1 minute**\n"
                        f"🎵 **Please restart your audio after the update!**\n"
                        f"💡 Just use the same `/rain`, `/sea` or `/sparkles` command\n\n"
                        f"*Thank you for your patience* ✨"
                    )
                    
                    # Find the text channel associated with the voice channel
                    target_channel = None
                    voice_channel_id = int(guild_info['channel_id'])
                    voice_channel = guild.get_channel(voice_channel_id)
                    
                    if voice_channel:
                        
                        # Method 0: Check if voice channel has a linked text channel (Discord native feature)  
                        if hasattr(voice_channel, 'text_channel') and voice_channel.text_channel:
                            if voice_channel.text_channel.permissions_for(guild.me).send_messages:
                                target_channel = voice_channel.text_channel
                                logging.info(f"🔗 Using native linked text channel: #{voice_channel.text_channel.name}")
                        
                        # Method 0.5: Try to send directly to voice channel (if it has integrated chat)
                        elif not target_channel:
                            try:
                                if voice_channel.permissions_for(guild.me).send_messages:
                                    target_channel = voice_channel
                                    logging.info(f"🔗 Using voice channel with integrated text: #{voice_channel.name}")
                            except:
                                pass
                        
                        # Method 1: If voice channel is in a category, look for text channels in same category
                        if not target_channel and voice_channel.category:
                            category_text_channels = [ch for ch in voice_channel.category.text_channels 
                                                    if ch.permissions_for(guild.me).send_messages]
                            if category_text_channels:
                                # Priority: channel with same name as voice channel
                                voice_name = voice_channel.name.lower()
                                for text_ch in category_text_channels:
                                    if text_ch.name.lower() == voice_name:
                                        target_channel = text_ch
                                        break
                                
                                # Fallback: first available text channel in same category
                                if not target_channel:
                                    target_channel = category_text_channels[0]
                        
                        # Method 2: Look for text channel with same name as voice channel (server-wide)
                        if not target_channel:
                            voice_name = voice_channel.name.lower()
                            for text_ch in guild.text_channels:
                                if (text_ch.name.lower() == voice_name and 
                                    text_ch.permissions_for(guild.me).send_messages):
                                    target_channel = text_ch
                                    break
                    
                    # Method 3: Fallback to any available text channel
                    if not target_channel:
                        available_channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]
                        if available_channels:
                            target_channel = available_channels[0]
                    
                    if target_channel:
                        await target_channel.send(message)
                        notifications_sent += 1
                        logging.info(f"📢 Notification sent to {guild.name} #{target_channel.name} (linked to voice: {voice_channel.name if voice_channel else 'unknown'})")
                    else:
                        logging.warning(f"⚠️ No suitable text channel found in {guild.name} for voice channel {voice_channel.name if voice_channel else 'unknown'}")
                        
                except Exception as e:
                    logging.error(f"❌ Failed to notify guild {guild_info.get('guild_name', 'unknown')}: {e}")
                    continue
            
            # Mark as sent and start countdown
            data["status"] = "sent"
            data["notifications_sent"] = notifications_sent
            with open(self.notification_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logging.info(f"📢 Sent {notifications_sent} deployment notifications")
            
            # Wait for the delay period
            logging.info(f"⏳ Waiting {delay_seconds} seconds before deployment can proceed...")
            await asyncio.sleep(delay_seconds)
            
            # Mark as complete
            data["status"] = "complete"
            data["completed_at"] = datetime.now().isoformat()
            with open(self.notification_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            logging.info(f"✅ Deployment notification period completed")
            
        except Exception as e:
            logging.error(f"❌ Error handling deployment notification: {e}")
            # Clean up file on error
            try:
                os.remove(self.notification_file)
            except:
                pass