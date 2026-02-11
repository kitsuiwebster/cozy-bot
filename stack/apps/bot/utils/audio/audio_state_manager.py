import logging
from datetime import datetime
from typing import Dict, List, Optional
from utils.storage.couchdb_client import get_couchdb_client

# Manage saving and restoring audio state during deployments
class AudioStateManager:
    def __init__(self):
        self.db = get_couchdb_client()

    # Save current audio state to JSON file
    def save_current_state(self, bot_instance):
        try:
            audio_states = []
            
            for guild in bot_instance.guilds:
                voice_client = guild.voice_client
                
                if voice_client and voice_client.channel and voice_client.is_playing():
                    
                    # Find what sound is playing from global state
                    from cogs.audio.base_sound import global_current_sounds
                    current_sound = global_current_sounds.get(guild.id)
                    
                    if current_sound:
                        # Get users in voice channel
                        user_ids = [str(member.id) for member in voice_client.channel.members if not member.bot]
                        
                        if user_ids:  # Only save if there are users
                            state_entry = {
                                'guild_id': str(guild.id),
                                'channel_id': str(voice_client.channel.id), 
                                'sound_name': current_sound,
                                'user_ids': user_ids,
                                'guild_name': guild.name,
                                'channel_name': voice_client.channel.name
                            }
                            audio_states.append(state_entry)
            
            # Save to CouchDB
            state_data = {
                'timestamp': datetime.now().isoformat(),
                'audio_states': audio_states
            }

            self.db.save_audio_state(state_data)

            logging.info(f"📦 Audio state saved to CouchDB: {len(audio_states)} active sessions")
            return len(audio_states)
            
        except Exception as e:
            logging.error(f"❌ Failed to save audio state: {e}")
            return 0

    # Restore audio state from CouchDB
    def restore_audio_state(self, bot_instance):
        try:
            state_data = self.db.load_audio_state()
            if not state_data:
                logging.info("")
                logging.info("📦 No audio state found in CouchDB")
                return 0

            audio_states = state_data.get('audio_states', [])
            restored_count = 0
            
            for state in audio_states:
                try:
                    guild_id = int(state['guild_id'])
                    channel_id = int(state['channel_id'])
                    sound_name = state['sound_name']
                    expected_users = set(state['user_ids'])
                    
                    guild = bot_instance.get_guild(guild_id)
                    if not guild:
                        logging.warning(f"⚠️ Guild {guild_id} not found")
                        continue
                    
                    channel = guild.get_channel(channel_id)
                    if not channel:
                        logging.warning(f"⚠️ Channel {channel_id} not found")
                        continue
                    
                    # Check if any of the original users are still there
                    current_users = {str(member.id) for member in channel.members if not member.bot}
                    common_users = expected_users.intersection(current_users)
                    
                    if not common_users:
                        logging.info(f"⏭️ Skipping {guild.name} - no original users remain")
                        continue
                    
                    # Schedule audio restoration (can't do async operations in sync function)
                    self._schedule_audio_restore(guild_id, channel_id, sound_name)
                    restored_count += 1
                    logging.info("")
                    logging.info(f"🎵 Scheduled restore: {sound_name} in {guild.name}")
                    
                except Exception as e:
                    logging.error(f"❌ Failed to restore audio for guild {state.get('guild_id', 'unknown')}: {e}")
                    continue
            
            # Clean up state
            try:
                self.db.delete_audio_state()
                logging.info("🧹 Audio state cleaned up from CouchDB")
            except Exception:
                pass
            
            return restored_count
            
        except Exception as e:
            logging.error(f"❌ Failed to restore audio state: {e}")
            return 0

    # Schedule audio restoration to happen after bot is fully ready
    def _schedule_audio_restore(self, guild_id: int, channel_id: int, sound_name: str):
        restore_data = {
            'guild_id': str(guild_id),
            'channel_id': str(channel_id),
            'sound_name': sound_name,
            'timestamp': datetime.now().isoformat()
        }

        # Save individual restore task to CouchDB
        self.db.save_restore_task(str(guild_id), restore_data)

# Global instance
audio_state_manager = AudioStateManager()
