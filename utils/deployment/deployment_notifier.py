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
                    
                    # Find a suitable text channel
                    target_channel = None
                    voice_channel_name = guild_info['channel_name'].lower()
                    
                    # Look for text channels
                    text_channels = [ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages]
                    
                    # Priority: channel with similar name, then general, then first available
                    for text_ch in text_channels:
                        if any(keyword in text_ch.name.lower() for keyword in ['general', 'chat', 'main', voice_channel_name]):
                            target_channel = text_ch
                            break
                    
                    if not target_channel and text_channels:
                        target_channel = text_channels[0]
                    
                    if target_channel:
                        await target_channel.send(message)
                        notifications_sent += 1
                        logging.info(f"📢 Notification sent to {guild.name} #{target_channel.name}")
                    else:
                        logging.warning(f"⚠️ No suitable text channel found in {guild.name}")
                        
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