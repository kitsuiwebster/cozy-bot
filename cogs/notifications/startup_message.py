import discord
from discord.ext import commands
import logging
import os
import json

class StartupMessageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.startup_message_sent = False
        
    @commands.Cog.listener()
    async def on_ready(self):
        """Send startup message to all servers when bot is ready"""
        try:
            # Only send once per bot session
            if self.startup_message_sent:
                logging.info("📢 Startup messages already sent this session")
                return
                
            # Check if startup messages are enabled
            if not self.is_startup_messages_enabled():
                logging.info("📢 Startup messages are disabled")
                return
                
            logging.info("📢 Starting startup message process...")
            self.startup_message_sent = True
            await self.send_startup_messages()
        except Exception as e:
            logging.error(f"📢 Error in startup message on_ready: {e}")
            import traceback
            traceback.print_exc()
    
    def is_startup_messages_enabled(self):
        """Check if startup messages are enabled via config file"""
        try:
            config = self.load_message_config()
            # If current_message_type is null, disable startup messages
            message_type = config.get("current_message_type")
            if message_type is None or message_type == "null":
                return False
            return config.get("enabled", True)
        except:
            return False
    
    def load_message_config(self):
        """Load startup message configuration from JSON file"""
        try:
            with open('cogs/notifications/config/startup_messages.json', 'r', encoding='utf-8') as file:
                return json.load(file)
        except FileNotFoundError:
            logging.warning("📢 startup_messages.json not found, using default message")
            return self.get_default_config()
        except json.JSONDecodeError as e:
            logging.error(f"📢 Error parsing startup_messages.json: {e}")
            return self.get_default_config()
    
    def get_default_config(self):
        """Get default configuration if JSON file is not available"""
        return {
            "enabled": True,
            "messages": {
                "update": {
                    "title": "🎉 **Cozy Bot is back online!** 🎉",
                    "description": "We're ready to bring you relaxing sounds and cozy vibes again! ✨",
                    "call_to_action": "Use `/rain`, `/sea`, `/sparkles`, or `/background-music` to start your cozy experience!",
                    "footer": "We wish you a great day! ✨\n— Imène and Raphaël, CozyBot developers"
                }
            },
            "current_message_type": "update"
        }
    
    async def send_startup_messages(self):
        """Send startup message to all servers"""
        config = self.load_message_config()
        message_type = config.get("current_message_type", "update")
        
        # Get the message data, fallback to first available message if type not found
        if message_type in config["messages"]:
            message_data = config["messages"][message_type]
        else:
            # Use the first available message type
            first_key = next(iter(config["messages"]))
            message_data = config["messages"][first_key]
            logging.warning(f"📢 Message type '{message_type}' not found, using '{first_key}'")
        
        # Build the formatted message
        startup_message = self.format_message(message_data)
        
        success_count = 0
        total_servers = len(self.bot.guilds)
        
        logging.info(f"📢 Sending startup messages to {total_servers} servers...")
        
        for guild in self.bot.guilds:
            try:
                # Try to find a suitable channel to send the message
                channel = await self.find_suitable_channel(guild)
                
                if channel:
                    await channel.send(startup_message)
                    success_count += 1
                    logging.info(f"✅ Sent startup message to '{guild.name}' in #{channel.name} (ID: {channel.id})")
                else:
                    logging.warning(f"❌ No suitable channel found in '{guild.name}'")
                    
            except Exception as e:
                logging.error(f"❌ Failed to send startup message to {guild.name}: {e}")
        
        logging.info(f"📢 Startup messages sent: {success_count}/{total_servers} servers")
    
    async def find_suitable_channel(self, guild):
        """Find a suitable text channel to send the startup message"""
        # Priority order for channel names
        preferred_channels = [
            'general',
            'général',
            'allgemein',
            'geral',
            'generale',
            'общий',
            'ogólny',
            'allmänt',
            'yleinen',
            'generelt',
            'általános',
            'obecný',
            'všeobecný',
            'опћенито',
            'загален',
            'загальний',
            'genel',
            'عام',
            '一般',
            '일반',
            'सामान्य',
            'ทั่วไป',
            'umum',
            'γενικός',
            'כללי',
            'általános',
            'ogólny'
        ]
        
        logging.debug(f"🔍 Looking for suitable channel in '{guild.name}'...")
        
        # First, try to find preferred channels
        for channel_name in preferred_channels:
            for channel in guild.text_channels:
                if channel.name.lower() == channel_name.lower():
                    if channel.permissions_for(guild.me).send_messages:
                        logging.debug(f"✅ Found preferred channel #{channel.name} in '{guild.name}'")
                        return channel
                    else:
                        logging.debug(f"❌ No send permission in #{channel.name} in '{guild.name}'")
        
        # If no preferred channel found, try the system channel (where join/leave messages appear)
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            logging.debug(f"✅ Using system channel #{guild.system_channel.name} in '{guild.name}'")
            return guild.system_channel
        
        # Last resort: use any available channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                logging.debug(f"⚠️ Using fallback channel #{channel.name} in '{guild.name}'")
                return channel
            
        logging.debug(f"❌ No usable channel found in '{guild.name}'")
        return None
    
    def format_message(self, message_data):
        """Format the startup message from JSON configuration"""
        parts = []
        
        # Add title
        if "title" in message_data:
            parts.append(message_data["title"])
        
        # Add description
        if "description" in message_data:
            parts.append(message_data["description"])
        
        # Add features list
        if "features" in message_data:
            parts.append("")  # Empty line
            for feature in message_data["features"]:
                parts.append(feature)
        
        # Add call to action
        if "call_to_action" in message_data:
            parts.append("")  # Empty line
            parts.append(message_data["call_to_action"])
        
        # Add footer
        if "footer" in message_data:
            parts.append("")  # Empty line
            parts.append(message_data["footer"])
        
        return "\n".join(parts)

async def setup(bot):
    await bot.add_cog(StartupMessageCog(bot))