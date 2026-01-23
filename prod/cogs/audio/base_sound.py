from discord import FFmpegPCMAudio, ButtonStyle, app_commands
from discord.ext import commands
from discord.ui import Button, View
import os
import asyncio
import logging
from ..stats.gamification import cozy_gamification

# Global state tracking which cog is playing in each guild and current sounds (survives reconnections)
global_playing_states = {}
global_current_sounds = {}

# Base view for interactive sound selection buttons
class BaseSoundView(View):
    def __init__(self, sounds, sound_labels, user_id, bot, cog_name):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.bot = bot
        self.sounds = sounds
        self.sound_labels = sound_labels
        self.cog_name = cog_name

        # Create sound selection buttons
        for sound in self.sounds:
            button = Button(style=ButtonStyle.secondary, label=self.sound_labels[sound], custom_id=sound)
            button.callback = self.on_button_click
            self.add_item(button)

        stop_button = Button(style=ButtonStyle.danger, label="Stop", emoji="⏹", custom_id="stop")
        stop_button.callback = self.on_button_click
        self.add_item(stop_button)

    async def on_button_click(self, interaction):
        # Only command initiator can use buttons
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("Only the user who typed the command can use these buttons.😵‍💫 Use the commands instead.", ephemeral=True)
            return

        custom_id = interaction.data.get('custom_id')

        # Route to appropriate handler
        if custom_id == "stop":
            guild_id = interaction.guild.id
            await self.bot.get_cog(self.cog_name).stop_sound(interaction, guild_id)
        else:
            await self.bot.get_cog(self.cog_name).on_button_click(interaction)

# Base cog providing shared audio playback functionality
class BaseSoundCog(commands.Cog):
    def __init__(self, bot, sound_type, sounds, sound_labels, description):
        self.bot = bot
        self.sound_type = sound_type
        self.sounds = sounds
        self.sound_labels = sound_labels
        self.description = description
        self.guild_states = {}
        self.connection_locks = {}  # Prevent simultaneous connection attempts per guild

    async def play_sound_command(self, interaction, prompt_message):
        await interaction.response.defer()

        if interaction.user.voice is None:
            await interaction.followup.send(content="You need to be in a voice channel to use this command.😵", ephemeral=True)
            return

        user_channel = interaction.user.voice.channel
        guild_state = self.get_guild_state(interaction.guild.id)
        guild_state['target_channel'] = user_channel

        view = BaseSoundView(self.sounds, self.sound_labels, interaction.user.id, self.bot, self.__class__.__name__)
        await interaction.followup.send(prompt_message, view=view)

    # Clear playing states for other audio cogs
    def clear_other_cog_states(self, guild_id):
        global global_playing_states

        audio_cogs = []
        for cog_name in self.bot.cogs:
            cog = self.bot.get_cog(cog_name)
            if hasattr(cog, 'guild_states') and cog != self:
                audio_cogs.append(cog)

        # Clear states and cancel any pending restart tasks
        for cog in audio_cogs:
            if guild_id in cog.guild_states:
                cog.guild_states[guild_id]['is_playing'] = False
                cog.guild_states[guild_id]['current_sound'] = None
                # Cancel loop task if exists
                if cog.guild_states[guild_id].get('loop_task'):
                    try:
                        cog.guild_states[guild_id]['loop_task'].cancel()
                    except:
                        pass
                    cog.guild_states[guild_id]['loop_task'] = None
        global_playing_states[guild_id] = self.__class__.__name__

    # Get or initialize guild state
    def get_guild_state(self, guild_id):
        if guild_id not in self.guild_states:
            self.guild_states[guild_id] = {
                'is_playing': False,
                'current_sound': None,
                'loop_task': None,
                'target_channel': None,
                'disconnect_timer': None,
            }
        return self.guild_states[guild_id]

    # Audio playback completion callback
    def after_playing(self, error, guild_id):
        guild_state = self.get_guild_state(guild_id)

        if error:
            logging.error(f"❌ Player error: {error}")
            if guild_state['current_sound'] and guild_state['is_playing']:
                self.bot.loop.create_task(self.restart_audio_loop(guild_id))
        else:
            if guild_state['current_sound'] and guild_state['is_playing']:
                self.bot.loop.create_task(self.restart_audio_loop(guild_id))

    async def on_button_click(self, interaction):
        await interaction.response.defer()

        guild_id = interaction.guild.id
        guild_state = self.get_guild_state(guild_id)

        # Update target channel with user's current location (in case they moved)
        if interaction.user.voice:
            guild_state['target_channel'] = interaction.user.voice.channel

        sound_filename = interaction.data.get('custom_id')

        # Prevent playing same sound twice
        voice_client = interaction.guild.voice_client
        if (guild_state.get('current_sound') == sound_filename and
            guild_state.get('is_playing') and
            voice_client and
            voice_client.is_playing()):
            await interaction.followup.send("❌ This sound is already playing! Choose a different sound or stop playback first.", ephemeral=True)
            return

        user_channel = guild_state.get('target_channel')

        # Debug: Log current voice state
        logging.info("")
        logging.info("")
        logging.info(f"🔍 DEBUG: Current voice_client state: exists={voice_client is not None}, connected={voice_client.is_connected() if voice_client else 'N/A'}, channel={voice_client.channel.name if voice_client and voice_client.channel else 'None'}")
        logging.info(f"🔍 DEBUG: User wants to connect to: {user_channel.name if user_channel else 'None'}")
        logging.info(f"🔍 DEBUG: Guild: {interaction.guild.name}, Guild ID: {interaction.guild.id}")

        # Check if voice_client is actually connected, not just exists (fixes ghost connection bug)
        if voice_client and not voice_client.is_connected():
            logging.warning(f"⚠️ Ghost voice_client detected (exists but not connected). Cleaning up...")
            try:
                await voice_client.disconnect()
            except:
                pass
            voice_client = None
            logging.info(f"🔍 DEBUG: After cleanup, voice_client is now None")

        # Connect to voice channel with retry logic
        if voice_client is None:
            logging.info(f"🔍 DEBUG: voice_client is None, will attempt to connect")
            if user_channel:
                # Check channel permissions before connecting
                permissions = user_channel.permissions_for(interaction.guild.me)
                logging.info(f"🔍 DEBUG: Channel '{user_channel.name}' (ID: {user_channel.id}) type: {user_channel.type}")
                logging.info(f"🔍 DEBUG: Permissions - Connect: {permissions.connect}, Speak: {permissions.speak}, View: {permissions.view_channel}")

                if not permissions.connect:
                    await interaction.followup.send("❌ Bot doesn't have 'Connect' permission in this channel.", ephemeral=True)
                    return

                if not permissions.speak:
                    await interaction.followup.send("❌ Bot doesn't have 'Speak' permission in this channel.", ephemeral=True)
                    return

                # Use guild-level lock to prevent simultaneous connection attempts
                if guild_id not in self.connection_locks:
                    self.connection_locks[guild_id] = asyncio.Lock()

                async with self.connection_locks[guild_id]:
                    # Double-check if already connected (another request might have connected while waiting for lock)
                    voice_client = interaction.guild.voice_client
                    if voice_client and voice_client.is_connected():
                        logging.info(f"✅ Another request already connected to {voice_client.channel.name} while waiting for lock")
                    else:
                        max_retries = 3
                        retry_delay = 2.0  # Start with 2 seconds

                        for attempt in range(max_retries):
                            try:
                                logging.info(f"🔍 DEBUG: Attempting to connect (attempt {attempt + 1}/{max_retries})")
                                # Increased timeout to 30 seconds for better reliability with slow Discord servers
                                voice_client = await asyncio.wait_for(user_channel.connect(), timeout=30.0)
                                logging.info(f"🔍 DEBUG: Connected to channel, voice_client.is_connected(): {voice_client.is_connected()}")

                                # Wait briefly for voice state to stabilize
                                await asyncio.sleep(1.0)
                                logging.info(f"🔍 DEBUG: After delay, voice_client.is_connected(): {voice_client.is_connected()}")

                                logging.info(f"🔍 DEBUG: About to start disconnect timer")
                                await self.start_disconnect_timer(guild_id)
                                logging.info(f"🔍 DEBUG: Disconnect timer started successfully")
                                break
                            except asyncio.TimeoutError:
                                logging.error(f"❌ DEBUG: Connection attempt {attempt + 1} timed out")

                                # Check if bot connected anyway despite timeout (stuck session bug workaround)
                                await asyncio.sleep(1.0)
                                voice_client = interaction.guild.voice_client
                                if voice_client and voice_client.is_connected():
                                    logging.warning(f"⚠️ Connection timed out but bot is physically connected to {voice_client.channel.name}, continuing...")
                                    logging.info(f"🔍 DEBUG: After timeout workaround, voice_client.is_connected(): {voice_client.is_connected()}")

                                    logging.info(f"🔍 DEBUG: About to start disconnect timer (timeout workaround)")
                                    await self.start_disconnect_timer(guild_id)
                                    logging.info(f"🔍 DEBUG: Disconnect timer started successfully (timeout workaround)")
                                    break

                                # Really not connected, retry or fail
                                if attempt == max_retries - 1:
                                    await interaction.followup.send("❌ Connection to voice channel timed out after multiple attempts. Discord voice servers may be unstable.", ephemeral=True)
                                    return

                                # Exponential backoff
                                logging.info(f"⏳ Waiting {retry_delay}s before retry...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 1.5  # Increase delay for next retry
                            except Exception as e:
                                logging.error(f"❌ DEBUG: Connection attempt {attempt + 1} failed with exception: {type(e).__name__}: {str(e)}")
                                # Handle "Already connected" error by graceful cleanup
                                if "already connected" in str(e).lower():
                                    logging.warning(f"⚠️ Already connected error detected, checking existing connection...")
                                    try:
                                        existing_vc = interaction.guild.voice_client
                                        if existing_vc:
                                            # If it's actually connected, use it
                                            if existing_vc.is_connected():
                                                logging.info(f"✅ Using existing valid connection to {existing_vc.channel.name}")
                                                voice_client = existing_vc
                                                await self.start_disconnect_timer(guild_id)
                                                break
                                            else:
                                                # Disconnect ghost connection gracefully
                                                logging.warning(f"🧹 Cleaning up ghost connection...")
                                                await existing_vc.disconnect()
                                                await asyncio.sleep(2)
                                    except Exception as cleanup_error:
                                        logging.error(f"❌ Cleanup error: {cleanup_error}")
                                        await asyncio.sleep(2)

                                logging.error(f"❌ Connection attempt {attempt + 1} failed: {str(e)}")
                                if attempt == max_retries - 1:
                                    await interaction.followup.send(f"❌ Failed to connect to voice channel: {str(e)}", ephemeral=True)
                                    return

                                # Exponential backoff
                                logging.info(f"⏳ Waiting {retry_delay}s before retry...")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 1.5
            else:
                logging.error(f"❌ DEBUG: No target voice channel found")
                await interaction.followup.send("❌ No target voice channel found", ephemeral=True)
                return

            logging.info(f"🔍 DEBUG: Finished connection attempts, voice_client state: exists={voice_client is not None}, connected={voice_client.is_connected() if voice_client else 'N/A'}")
        else:
            # Already connected - check if we need to move
            logging.info(f"🔍 DEBUG: Bot already connected to {voice_client.channel.name}")
            logging.info(f"🔍 DEBUG: Current channel: {voice_client.channel.name}, Target channel: {user_channel.name if user_channel else 'None'}")
            if user_channel and voice_client.channel != user_channel:
                logging.info(f"🔄 Bot needs to move from {voice_client.channel.name} to {user_channel.name}")
                try:
                    await asyncio.wait_for(voice_client.move_to(user_channel), timeout=10.0)
                    logging.info(f"✅ Successfully moved to {user_channel.name}")
                except asyncio.TimeoutError:
                    logging.error(f"❌ Timeout while moving to {user_channel.name}")
                    await interaction.followup.send("❌ Failed to move to voice channel: timeout. Please try again.", ephemeral=True)
                    return
                except Exception as e:
                    logging.error(f"❌ Error moving to {user_channel.name}: {str(e)}")
                    await interaction.followup.send(f"❌ Failed to move to voice channel: {str(e)}", ephemeral=True)
                    return
            elif user_channel:
                logging.info(f"✅ Bot already in correct channel: {voice_client.channel.name}")

        logging.info(f"🔍 DEBUG: About to clear other cog states")
        self.clear_other_cog_states(interaction.guild.id)
        logging.info(f"🔍 DEBUG: Cleared other cog states")

        logging.info(f"🔍 DEBUG: Checking if audio is playing: {voice_client.is_playing()}")
        if voice_client.is_playing():
            voice_client.stop()
            logging.info(f"🔍 DEBUG: Stopped playing audio")

        # Verify voice client is properly connected before playing
        logging.info(f"🔍 DEBUG: Verification checks - voice_client={voice_client is not None}, is_connected={voice_client.is_connected() if voice_client else 'N/A'}")

        if not voice_client:
            await interaction.followup.send("❌ Voice client is None. This shouldn't happen - please report this bug.", ephemeral=True)
            logging.error(f"❌ CRITICAL: voice_client is None after connection logic. Guild: {interaction.guild.name}, User: {interaction.user.name}")
            return

        if not voice_client.is_connected():
            await interaction.followup.send("❌ Bot appears connected but Discord reports not connected. Try disconnecting the bot and trying again.", ephemeral=True)
            logging.error(f"❌ CRITICAL: voice_client.is_connected() is False. Guild: {interaction.guild.name}, Channel: {voice_client.channel if hasattr(voice_client, 'channel') else 'unknown'}")
            return

        logging.info(f"✅ DEBUG: All verification checks passed, proceeding to play audio")

        # Determine sound path and start playback with FFmpeg infinite loop
        try:
            if sound_filename.startswith('rain'):
                sound_path = f"cogs/audio/rain/{sound_filename}"
            elif sound_filename.startswith('sea'):
                sound_path = f"cogs/audio/sea/{sound_filename}"
            elif sound_filename.startswith('sparkles'):
                sound_path = f"cogs/audio/sparkles/{sound_filename}"
            elif sound_filename.startswith('background-music'):
                sound_path = f"cogs/audio/background_music/{sound_filename}"
            elif sound_filename.startswith('white-noise'):
                sound_path = f"cogs/audio/noise/{sound_filename}"
            else:
                sound_path = f"cogs/audio/{sound_filename}"
            if os.path.exists(sound_path):
                logging.info(f"🔍 DEBUG: About to play audio. voice_client.is_connected(): {voice_client.is_connected()}, sound_path: {sound_path}")
                audio_source = FFmpegPCMAudio(sound_path, before_options='-loglevel panic', stderr=open(os.devnull, 'w'))
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
                logging.info(f"🔍 DEBUG: Successfully started playing audio")

                guild_state['is_playing'] = True
                guild_state['current_sound'] = sound_filename

                global global_current_sounds
                global_current_sounds[interaction.guild.id] = sound_filename

                # Track sound for all users in channel
                from cogs.stats.gamification import cozy_gamification
                voice_client = interaction.guild.voice_client
                if voice_client and voice_client.channel:
                    current_users = [member for member in voice_client.channel.members if not member.bot]
                    logging.info("")
                    logging.info("")
                    logging.info(f"🎵 SOUND START: \033[36m{sound_filename}\033[0m in {voice_client.channel.name} ({interaction.guild.name}) - {len(current_users)} users listening")

                    for member in current_users:
                        cozy_gamification.finalize_current_sound(str(member.id))

                    user_ids = [str(member.id) for member in current_users]
                    cozy_gamification.reset_consecutive_time_for_guild(interaction.guild.id, user_ids)

                    for member in current_users:
                        cozy_gamification.update_username(str(member.id), member.name, member.global_name or member.name)
                        cozy_gamification.track_sound_start(member.id, sound_filename)
                        logging.info(f"🎵 Tracking \033[36m{sound_filename}\033[0m for \033[35m{member.name}\033[0m")

                sound_label = self.sound_labels.get(sound_filename, sound_filename)
                await interaction.followup.send(f"🎵 Now playing: {sound_label}")
            else:
                await interaction.followup.send(f"❌ Sound file not found: {sound_filename}", ephemeral=True)
        except Exception as e:
            logging.error(f"❌ Exception during audio playback: {type(e).__name__}: {str(e)}")
            logging.error(f"❌ voice_client state: is_connected={voice_client.is_connected() if voice_client else 'N/A'}, channel={voice_client.channel if voice_client else 'N/A'}")
            import traceback
            logging.error(f"❌ Traceback: {traceback.format_exc()}")
            await interaction.followup.send(
                f"❌ **Error playing sound:** {str(e)}\n\n"
                f"Sorry! We're aware of this issue and working on a fix. 🛠️\n"
                f"**Try this:** Leave the voice channel, rejoin, and try again. Or try a different voice channel.",
                ephemeral=True
            )

    async def start_disconnect_timer(self, guild_id):
        guild_state = self.get_guild_state(guild_id)

        if guild_state['disconnect_timer']:
            guild_state['disconnect_timer'].cancel()

        guild_state['disconnect_timer'] = asyncio.create_task(self.disconnect_timer_task(guild_id))

    # Timer task to auto-disconnect from empty channels
    async def disconnect_timer_task(self, guild_id):
        try:
            while True:
                await asyncio.sleep(120)  # Wait 2 minutes
                
                guild = self.bot.get_guild(guild_id)
                if not guild or not guild.voice_client:
                    break
                
                voice_client = guild.voice_client
                if not voice_client.channel:
                    break
                
                # Check if there are real users (not bots) in the channel
                human_members = [m for m in voice_client.channel.members if not m.bot]
                
                if not human_members:
                    # Channel is empty, disconnect
                    guild_state = self.get_guild_state(guild_id)
                    
                    if voice_client.is_playing():
                        voice_client.stop()
                    await voice_client.disconnect()
                    guild_state['is_playing'] = False
                    guild_state['current_sound'] = None
                    guild_state['disconnect_timer'] = None
                    
                    logging.info(f"👋 AUTO-DISCONNECT: Left empty voice channel in {guild.name}")
                    break
                else:
                    # Still has users, continue monitoring
                    continue
                    
        except asyncio.CancelledError:
            # Timer was cancelled (normal when new user joins or manual stop)
            pass
        except Exception as e:
            logging.error(f"❌ Error in disconnect timer: {e}")

    # Stop audio playback and disconnect from voice
    async def stop_sound(self, interaction, guild_id):
        await interaction.response.defer()
        
        guild_state = self.get_guild_state(guild_id)
        voice_client = interaction.guild.voice_client
        
        # Finalize sound sessions for all users before stopping
        from cogs.stats.gamification import cozy_gamification
        if voice_client and voice_client.channel:
            current_users = [member for member in voice_client.channel.members if not member.bot]
            logging.info("")
            logging.info("")
            logging.info(f"🛑 SOUND STOP: Finalizing sound tracking for {len(current_users)} users in {voice_client.channel.name} ({interaction.guild.name})")
            for member in current_users:
                cozy_gamification.finalize_current_sound(member.id)
                logging.info(f"🛑 Finalized sound tracking for {member.name}")
        
        # Cancel disconnect timer
        if guild_state['disconnect_timer']:
            guild_state['disconnect_timer'].cancel()
            guild_state['disconnect_timer'] = None
        
        if voice_client:
            if voice_client.is_playing():
                voice_client.stop()
            await voice_client.disconnect()
            guild_state['is_playing'] = False
            guild_state['current_sound'] = None
            
            # Clear global state
            global global_current_sounds
            if interaction.guild.id in global_current_sounds:
                del global_current_sounds[interaction.guild.id]
            
            await interaction.followup.send("⏹️ Stopped playing and left voice channel.")
        else:
            await interaction.followup.send("❌ No sound is currently playing.", ephemeral=True)

    # Restart audio loop for continuous playback
    async def restart_audio_loop(self, guild_id):
        try:
            guild_state = self.get_guild_state(guild_id)
            voice_client = guild_state.get('voice_client')
            current_sound = guild_state['current_sound']

            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"guild {guild_id}"
            logging.info("")
            logging.info("")
            logging.info(f"👉 Restarting \033[36m{current_sound}\033[0m in {guild_name}")

            # Get voice client from guild if not in state
            if not voice_client:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    voice_client = guild.voice_client

            # Only restart if we should still be playing
            if not current_sound or not guild_state['is_playing'] or not voice_client:
                logging.info(f"🔄 restart_audio_loop skipped: current_sound=\033[36m{current_sound}\033[0m, is_playing={guild_state['is_playing']}, voice_client={voice_client is not None}")
                return

            # Small delay to avoid rapid restart issues
            await asyncio.sleep(0.1)
            
            # Find the correct sound path - use same logic as on_button_click
            if current_sound.startswith('rain'):
                sound_path = f"cogs/audio/rain/{current_sound}"
            elif current_sound.startswith('sea'):
                sound_path = f"cogs/audio/sea/{current_sound}"
            elif current_sound.startswith('sparkles'):
                sound_path = f"cogs/audio/sparkles/{current_sound}"
            elif current_sound.startswith('background-music'):
                sound_path = f"cogs/audio/background_music/{current_sound}"
            elif current_sound.startswith('white-noise'):
                sound_path = f"cogs/audio/noise/{current_sound}"
            else:
                sound_path = f"cogs/audio/{current_sound}"
            
            # Restart audio if file exists and voice client is ready
            if os.path.exists(sound_path) and voice_client.is_connected() and not voice_client.is_playing():
                audio_source = FFmpegPCMAudio(sound_path, before_options='-loglevel panic', stderr=open(os.devnull, 'w'))
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
            
        except Exception as e:
            logging.error(f"❌ Failed to restart audio loop: {e}")
            # Try again after a longer delay if restart failed
            await asyncio.sleep(1)
            guild_state = self.get_guild_state(guild_id)
            if guild_state['is_playing'] and guild_state['current_sound']:
                self.bot.loop.create_task(self.restart_audio_loop(guild_id))

