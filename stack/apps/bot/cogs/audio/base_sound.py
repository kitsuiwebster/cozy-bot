from discord import FFmpegPCMAudio, ButtonStyle, app_commands
import time
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
                'suppress_restart': False,
            }
        return self.guild_states[guild_id]

    # Track sound in background without blocking audio playback
    async def _track_sound_async(self, guild_id, sound_filename, channel):
        try:
            from cogs.stats.gamification import cozy_gamification

            current_users = [member for member in channel.members if not member.bot]
            logging.info("")
            logging.info("")
            logging.info(f"🎵 SOUND START: \033[36m{sound_filename}\033[0m in {channel.name} - {len(current_users)} users listening")

            for member in current_users:
                cozy_gamification.finalize_current_sound(str(member.id))

            user_ids = [str(member.id) for member in current_users]
            cozy_gamification.reset_consecutive_time_for_guild(guild_id, user_ids)

            for member in current_users:
                cozy_gamification.update_username(str(member.id), member.name, member.global_name or member.name, save_immediately=False)
                cozy_gamification.track_sound_start(member.id, sound_filename, save_immediately=False)
                logging.info(f"🎵 Tracking \033[36m{sound_filename}\033[0m for \033[35m{member.name}\033[0m")

            # Save once after processing all users
            if current_users:
                cozy_gamification.save_user_data()
                cozy_gamification.save_usernames()
                try:
                    import main
                    main.schedule_live_stats_update()
                except Exception:
                    pass
        except Exception as e:
            logging.error(f"❌ Error tracking sound: {e}")

    # Audio playback completion callback
    def after_playing(self, error, guild_id):
        guild_state = self.get_guild_state(guild_id)

        if guild_state.get('suppress_restart'):
            guild_state['suppress_restart'] = False
            return

        if error:
            logging.error(f"❌ Player error: {error}")
            if guild_state['current_sound'] and guild_state['is_playing']:
                self.bot.loop.create_task(self.restart_audio_loop(guild_id))
        else:
            if guild_state['current_sound'] and guild_state['is_playing']:
                self.bot.loop.create_task(self.restart_audio_loop(guild_id))

    async def on_button_click(self, interaction):
        perf_enabled = os.getenv("COZY_PERF_LOGS") == "1"
        t0 = time.monotonic()
        await interaction.response.defer()
        if perf_enabled:
            logging.info("⏱️ PERF click->defer: 0ms")

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

        # Check if voice_client is actually connected, not just exists (fixes ghost connection bug)
        if voice_client and not voice_client.channel:
            logging.warning(f"⚠️ Ghost voice_client detected (exists but not in channel). Cleaning up...")
            try:
                await voice_client.disconnect()
            except:
                pass
            voice_client = None
            await asyncio.sleep(0.5)
            logging.info(f"🔍 DEBUG: After cleanup, voice_client is now None")

        # Refresh voice_client reference
        voice_client = interaction.guild.voice_client

        # Connect to voice channel with workaround for discord.py bug
        did_connect = False
        did_move = False

        if voice_client is None:
            if not user_channel:
                await interaction.followup.send("❌ You need to be in a voice channel!", ephemeral=True)
                return

            try:
                logging.info(f"🔍 Connecting to {user_channel.name}...")

                # Connect without timeout (like romeo-bot)
                voice_client = await user_channel.connect()
                logging.info(f"✅ Connected! is_connected={voice_client.is_connected()}")
                did_connect = True
                if perf_enabled:
                    logging.info(f"⏱️ PERF click->connected: {int((time.monotonic() - t0) * 1000)}ms")

                await self.start_disconnect_timer(guild_id)

            except Exception as e:
                import traceback
                logging.error(f"❌ Connection error: {e}")
                logging.error(f"❌ Traceback: {traceback.format_exc()}")
                await interaction.followup.send(f"❌ Connection failed: {str(e)}", ephemeral=True)
                return
        else:
            # Already connected - check if we need to move
            
            if user_channel and voice_client.channel != user_channel:
                logging.info(f"🔄 Bot needs to move from {voice_client.channel.name} to {user_channel.name}")

                # Try to move with retries
                max_move_retries = 2
                for move_attempt in range(max_move_retries):
                    try:
                        await asyncio.wait_for(voice_client.move_to(user_channel), timeout=15.0)
                        await asyncio.sleep(0.5)

                        if voice_client.channel == user_channel:
                            logging.info(f"✅ Successfully moved to {user_channel.name}")
                            did_move = True
                            if perf_enabled:
                                logging.info(f"⏱️ PERF click->moved: {int((time.monotonic() - t0) * 1000)}ms")
                            break
                        else:
                            logging.warning(f"⚠️ move_to() completed but bot not in target channel")
                            if move_attempt == max_move_retries - 1:
                                await interaction.followup.send("❌ Failed to move to voice channel. Please try again.", ephemeral=True)
                                return

                    except asyncio.TimeoutError:
                        logging.error(f"❌ Timeout while moving (attempt {move_attempt + 1})")

                        # Check if move succeeded anyway
                        await asyncio.sleep(1)
                        if voice_client.channel == user_channel:
                            logging.info(f"✅ Move succeeded despite timeout")
                            break

                        if move_attempt == max_move_retries - 1:
                            await interaction.followup.send("❌ Failed to move to voice channel: timeout. Please try again.", ephemeral=True)
                            return
                        await asyncio.sleep(1)

                    except Exception as e:
                        logging.error(f"❌ Error moving (attempt {move_attempt + 1}): {str(e)}")
                        if move_attempt == max_move_retries - 1:
                            await interaction.followup.send(f"❌ Failed to move to voice channel: {str(e)}", ephemeral=True)
                            return
                        await asyncio.sleep(1)

            elif user_channel:
                pass

        self.clear_other_cog_states(interaction.guild.id)

        # Simple verification
        if not voice_client or not voice_client.channel:
            await interaction.followup.send("❌ Not connected to voice", ephemeral=True)
            return

        

        # Warn if bot is server-muted/deafened/suppressed (no audio will be heard)
        try:
            bot_voice = interaction.guild.me.voice if interaction.guild and interaction.guild.me else None
            if bot_voice and (bot_voice.mute or bot_voice.deaf or bot_voice.suppress):
                logging.warning(
                    f"⚠️ Bot voice state: mute={bot_voice.mute}, deaf={bot_voice.deaf}, suppress={bot_voice.suppress} "
                    f"(audio may be inaudible)"
                )
        except Exception as e:
            logging.warning(f"⚠️ Could not read bot voice state: {e}")

        # Stop any playing audio
        was_playing = False
        if voice_client.is_playing():
            guild_state['suppress_restart'] = True
            guild_state['is_playing'] = False
            guild_state['current_sound'] = None
            voice_client.stop()
            was_playing = True
            if perf_enabled:
                logging.info(f"⏱️ PERF click->stopped-prev: {int((time.monotonic() - t0) * 1000)}ms")

        # Short stabilization delay (avoid fixed 2s on every click)
        if did_connect or did_move:
            await asyncio.sleep(0.4)
        elif was_playing:
            await asyncio.sleep(0.1)
        else:
            await asyncio.sleep(0.05)
        if perf_enabled:
            logging.info(f"⏱️ PERF click->after-stabilize: {int((time.monotonic() - t0) * 1000)}ms")

        # Determine sound path and start playback - ignore is_connected() check
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
                # Play audio like romeo-bot - simple and direct
                if perf_enabled:
                    logging.info(f"⏱️ PERF click->before-ffmpeg: {int((time.monotonic() - t0) * 1000)}ms")
                audio_source = FFmpegPCMAudio(sound_path, executable="ffmpeg", options='-loglevel panic')
                if not voice_client.is_playing():
                    voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
                if perf_enabled:
                    logging.info(f"⏱️ PERF click->play-called: {int((time.monotonic() - t0) * 1000)}ms")

                guild_state['is_playing'] = True
                guild_state['current_sound'] = sound_filename

                global global_current_sounds
                global_current_sounds[interaction.guild.id] = sound_filename

                # Track sound in background - don't block audio playback
                asyncio.create_task(self._track_sound_async(interaction.guild.id, sound_filename, voice_client.channel))

                sound_label = self.sound_labels.get(sound_filename, sound_filename)
                await interaction.followup.send(f"🎵 Now playing: {sound_label}")
                if perf_enabled:
                    logging.info(f"⏱️ PERF click->followup: {int((time.monotonic() - t0) * 1000)}ms")
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
                
                # Determine if there are non-bot users in the channel.
                # Use voice_states (more reliable than members cache) and fall back to members.
                voice_states = getattr(voice_client.channel, "voice_states", {}) or {}
                non_bot_voice_ids = [uid for uid in voice_states.keys() if uid != self.bot.user.id]
                human_members = [m for m in voice_client.channel.members if not m.bot]

                logging.info(
                    f"🔍 AUTO-DISCONNECT CHECK: guild={guild.name} "
                    f"voice_states={len(non_bot_voice_ids)} members={len(human_members)}"
                )

                if not non_bot_voice_ids and not human_members:
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
                guild_state['suppress_restart'] = True
                voice_client.stop()
            await voice_client.disconnect()
            guild_state['is_playing'] = False
            guild_state['current_sound'] = None
            
            # Clear global state
            global global_current_sounds
            if interaction.guild.id in global_current_sounds:
                del global_current_sounds[interaction.guild.id]

            try:
                import main
                main.schedule_live_stats_update()
            except Exception:
                pass
            
            await interaction.followup.send("⏹️ Stopped playing and left voice channel.")
        else:
            await interaction.followup.send("❌ No sound is currently playing.", ephemeral=True)

    # Restart audio loop for continuous playback
    async def restart_audio_loop(self, guild_id):
        try:
            guild_state = self.get_guild_state(guild_id)
            voice_client = guild_state.get('voice_client')
            current_sound = guild_state['current_sound']

            # Get voice client from guild if not in state
            if not voice_client:
                guild = self.bot.get_guild(guild_id)
                if guild:
                    voice_client = guild.voice_client
            # Skip if voice is not connected
            if not voice_client or (hasattr(voice_client, "is_connected") and not voice_client.is_connected()):
                logging.info(f"🔄 restart_audio_loop skipped: voice not connected for guild {guild_id}")
                return

            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"guild {guild_id}"
            logging.info("")
            logging.info("")
            logging.info(f"👉 Restarting \033[36m{current_sound}\033[0m in {guild_name}")

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
            # NOTE: Using voice_client.channel check instead of is_connected() due to discord.py 2.3.2 bug
            if os.path.exists(sound_path) and voice_client.channel and not voice_client.is_playing():
                audio_source = FFmpegPCMAudio(sound_path, before_options='-loglevel panic', stderr=open(os.devnull, 'w'))
                voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
            
        except Exception as e:
            if "Not connected to voice" in str(e):
                logging.info("🔄 restart_audio_loop skipped: voice not connected")
                return
            logging.error(f"❌ Failed to restart audio loop: {e}")
            # Try again after a longer delay if restart failed
            await asyncio.sleep(1)
            guild_state = self.get_guild_state(guild_id)
            if guild_state['is_playing'] and guild_state['current_sound']:
                self.bot.loop.create_task(self.restart_audio_loop(guild_id))
