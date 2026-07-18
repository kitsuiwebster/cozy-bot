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

# Shared per-guild audio mutation locks. The watchdog (main.py) and a user-
# initiated stop_sound can both touch the same guild_state concurrently;
# without a shared lock they can produce duplicated restarts, audio left
# hanging, or stale `current_sound` references. Acquire this around any
# code that starts, stops, or restarts audio for a guild.
_guild_audio_locks: dict = {}


def get_guild_audio_lock(guild_id) -> asyncio.Lock:
    """Returns the shared audio mutation lock for a guild, creating it lazily.

    Safe to call from any async context — single-threaded asyncio means the
    lookup/create sequence is atomic between awaits. Lock instances are kept
    indefinitely (small fixed memory cost; cleared only on bot shutdown).
    """
    lock = _guild_audio_locks.get(guild_id)
    if lock is None:
        lock = asyncio.Lock()
        _guild_audio_locks[guild_id] = lock
    return lock


# All audio cog class names. Stop paths must sweep every cog's state: the
# playing state may live in a different cog than the menu that was clicked.
AUDIO_COG_NAMES = ('RainCog', 'SeaCog', 'SparklesCog', 'BackgroundMusicCog', 'NoiseCog')

# Last VoiceClient we successfully connected, per guild. discord.py wipes its
# own registry on a gateway re-IDENTIFY without stopping the clients; this side
# table lets reap_orphan_voice_clients find those orphans, whose internal tasks
# otherwise keep sending join/leave for the guild and sabotage every new
# connection handshake.
known_voice_clients = {}


async def teardown_voice_client(guild):
    """Force-disconnect and deregister a dead or half-dead voice client.

    A client whose websocket died can keep .channel populated. Leaving it
    registered makes play() raise "Not connected to voice" and blocks the next
    connect() handshake for the guild, so it must be torn down completely
    before reconnecting.
    """
    voice_client = guild.voice_client
    if not voice_client:
        return
    known_voice_clients.pop(guild.id, None)
    try:
        await asyncio.wait_for(voice_client.disconnect(force=True), timeout=10)
    except Exception as e:
        logging.warning(f"⚠️ Voice teardown: disconnect failed in {guild.name}: {e}")
    try:
        voice_client.cleanup()
    except Exception:
        pass


def reap_orphan_voice_clients(bot):
    """Cancel and deregister voice clients discord.py no longer tracks.

    Returns the number of orphans that still had internal tasks running.
    Reaches into VoiceClient._connection (private API) because nothing public
    stops an orphaned client's runner/connector tasks.
    """
    reaped = 0
    for guild_id, vc in list(known_voice_clients.items()):
        guild = bot.get_guild(guild_id)
        current = guild.voice_client if guild else None
        if current is vc:
            continue
        known_voice_clients.pop(guild_id, None)
        connection = getattr(vc, '_connection', None)
        live_tasks = [
            task for task in (
                getattr(connection, '_runner', None) if connection else None,
                getattr(connection, '_connector', None) if connection else None,
            ) if task is not None and not task.done()
        ]
        if not live_tasks:
            continue
        try:
            for task in live_tasks:
                task.cancel()
            vc.cleanup()
            reaped += 1
            guild_name = guild.name if guild else guild_id
            logging.warning(f"⚠️ Reaped orphaned voice client in {guild_name} (internal tasks still running)")
        except Exception as e:
            logging.warning(f"⚠️ Failed to reap orphaned voice client in {guild.name if guild else guild_id}: {e}")
    return reaped

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
        # Anyone in the same voice channel as the bot can use the buttons.
        # This lets the community jointly pick sounds in shared listening rooms,
        # while still blocking randos outside the channel from spam-clicking.
        bot_voice = interaction.guild.voice_client if interaction.guild else None
        bot_channel = bot_voice.channel if bot_voice else None
        user_channel = interaction.user.voice.channel if interaction.user.voice else None

        # Original command author always allowed (covers the initial pick before
        # the bot has joined a channel).
        if interaction.user.id != self.user_id:
            if not bot_channel or not user_channel or bot_channel.id != user_channel.id:
                await interaction.response.send_message(
                    "Join the voice channel where I'm playing to use these buttons.🎧",
                    ephemeral=True,
                )
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
                    except Exception:
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
                cozy_gamification.track_sound_start(str(member.id), sound_filename, save_immediately=False)
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
            # Keep one restart task per guild to avoid watchdog/after concurrency.
            current_loop_task = guild_state.get('loop_task')
            if current_loop_task and not current_loop_task.done():
                return
            loop_task = self.bot.loop.create_task(self.restart_audio_loop(guild_id))
            guild_state['loop_task'] = loop_task
            loop_task.add_done_callback(lambda _: guild_state.update({'loop_task': None}))

    async def on_button_click(self, interaction):
        perf_enabled = os.getenv("COZY_PERF_LOGS") == "1"
        t0 = time.monotonic()
        await interaction.response.defer()
        if perf_enabled:
            logging.info("⏱️ PERF click->defer: 0ms")

        guild_id = interaction.guild.id

        # Serialize with the watchdog/after_playing restart path, stop_sound and
        # the auto-disconnect timer. Button clicks used to run unlocked, racing
        # those paths into double connects and play() on torn-down clients.
        async with get_guild_audio_lock(guild_id):
            await self._on_button_click_locked(interaction, guild_id, t0, perf_enabled)

    async def _on_button_click_locked(self, interaction, guild_id, t0, perf_enabled):
        guild_state = self.get_guild_state(guild_id)

        # Update target channel with user's current location (in case they moved)
        if interaction.user.voice:
            guild_state['target_channel'] = interaction.user.voice.channel

        sound_filename = interaction.data.get('custom_id')

        # Prevent playing same sound twice. is_connected() matters here: a
        # zombie client can keep "playing" into a dead websocket, and without
        # the check the user clicking the same sound to bring the bot back
        # would get "already playing" instead of a reconnect.
        voice_client = interaction.guild.voice_client
        if (guild_state.get('current_sound') == sound_filename and
            guild_state.get('is_playing') and
            voice_client and
            voice_client.is_connected() and
            voice_client.is_playing()):
            await interaction.followup.send("❌ This sound is already playing! Choose a different sound or stop playback first.", ephemeral=True)
            return

        user_channel = guild_state.get('target_channel')

        # A voice_client that lost its channel OR its websocket (is_connected()
        # False while .channel is still set) is dead: playing on it raises
        # "Not connected to voice" and its stale session blocks a fresh
        # handshake. Tear it down so the connect branch below starts clean.
        if voice_client and (not voice_client.channel or not voice_client.is_connected()):
            logging.warning(
                f"⚠️ Stale voice_client detected (channel={voice_client.channel}, "
                f"is_connected={voice_client.is_connected()}). Tearing down..."
            )
            await teardown_voice_client(interaction.guild)
            voice_client = None
            await asyncio.sleep(0.5)

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

                # Default 60s handshake timeout (discord.py waits for both
                # VOICE_STATE_UPDATE and VOICE_SERVER_UPDATE)
                voice_client = await user_channel.connect()
                did_connect = True
                known_voice_clients[guild_id] = voice_client
                if perf_enabled:
                    logging.info(f"⏱️ PERF click->connected: {int((time.monotonic() - t0) * 1000)}ms")

                await self.start_disconnect_timer(guild_id)

            except asyncio.TimeoutError as e:
                # Discord never delivered the voice handshake within 60s: a
                # Discord-side outage (voice server or gateway), not a bot bug.
                # One clear line for Telegram; the full traceback adds nothing.
                logging.warning(
                    f"🌐 DISCORD-SIDE: voice handshake timed out (60s) joining "
                    f"{user_channel.name} in {interaction.guild.name}. "
                    f"Discord voice is having issues, user was asked to retry."
                )
                await interaction.followup.send(f"❌ Connection failed: {str(e)}", ephemeral=True)
                return
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
                            logging.warning("⚠️ move_to() completed but bot not in target channel")
                            if move_attempt == max_move_retries - 1:
                                await interaction.followup.send("❌ Failed to move to voice channel. Please try again.", ephemeral=True)
                                return

                    except asyncio.TimeoutError:
                        logging.error(f"❌ Timeout while moving (attempt {move_attempt + 1})")

                        # Check if move succeeded anyway
                        await asyncio.sleep(1)
                        if voice_client.channel == user_channel:
                            logging.info("✅ Move succeeded despite timeout")
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

        self.clear_other_cog_states(interaction.guild.id)

        # Simple verification: channel AND live websocket
        if not voice_client or not voice_client.channel or not voice_client.is_connected():
            await interaction.followup.send("❌ Not connected to voice", ephemeral=True)
            return

        

        # Warn if bot is server-muted/deafened/suppressed (no audio will be heard)
        try:
            bot_voice = interaction.guild.me.voice if interaction.guild and interaction.guild.me else None
            if bot_voice and (bot_voice.mute or bot_voice.deaf or bot_voice.suppress):
                logging.info(
                    f"ℹ️ Bot voice state: mute={bot_voice.mute}, deaf={bot_voice.deaf}, suppress={bot_voice.suppress} "
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

        # Determine sound path and start playback
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
                audio_source = FFmpegPCMAudio(
                    sound_path,
                    executable="ffmpeg",
                    before_options='-stream_loop -1 -loglevel panic',
                )
                if not voice_client.is_playing():
                    voice_client.play(audio_source, after=lambda e: self.after_playing(e, guild_id))
                if perf_enabled:
                    logging.info(f"⏱️ PERF click->play-called: {int((time.monotonic() - t0) * 1000)}ms")

                guild_state['is_playing'] = True
                guild_state['current_sound'] = sound_filename

                global global_current_sounds
                global_current_sounds[interaction.guild.id] = sound_filename

                # Track sound in background - don't block audio playback
                tracking_task = asyncio.create_task(self._track_sound_async(interaction.guild.id, sound_filename, voice_client.channel))
                guild_state['tracking_task'] = tracking_task

                sound_label = self.sound_labels.get(sound_filename, sound_filename)
                now_playing_msg = await interaction.followup.send(f"🎵 Now playing: {sound_label}", wait=True)

                # Auto-delete the "Now playing" notice after 5 minutes so the
                # channel doesn't pile up announcements during long sessions.
                # The audio keeps playing — only the chat message is removed.
                async def _auto_delete_now_playing():
                    try:
                        await asyncio.sleep(300)
                        await now_playing_msg.delete()
                    except Exception:
                        # Message may already be gone, channel deleted, perms revoked — ignore.
                        pass

                self.bot.loop.create_task(_auto_delete_now_playing())
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

                if not non_bot_voice_ids and not human_members:
                    # Channel is empty. Serialize with the button/restart paths,
                    # then re-check: a user may have joined (or a restart may be
                    # mid-connect) while we waited for the lock.
                    async with get_guild_audio_lock(guild_id):
                        voice_client = guild.voice_client
                        if not voice_client or not voice_client.channel:
                            break
                        if any(not m.bot for m in voice_client.channel.members):
                            continue

                        guild_state = self.get_guild_state(guild_id)
                        # Clear state BEFORE stopping so after_playing and the
                        # voice-drop recovery see a deliberate disconnect and
                        # don't bring the bot back.
                        guild_state['is_playing'] = False
                        guild_state['current_sound'] = None
                        guild_state['disconnect_timer'] = None
                        global_current_sounds.pop(guild_id, None)

                        if voice_client.is_playing():
                            voice_client.stop()
                        await voice_client.disconnect()

                    logging.info(f"👋 AUTO-DISCONNECT: Left empty voice channel in {guild.name}")
                    break
                else:
                    # Still has users, continue monitoring
                    continue
                    
        except asyncio.CancelledError:
            # Timer was cancelled (normal when new user joins or manual stop)
            raise
        except Exception as e:
            logging.error(f"❌ Error in disconnect timer: {e}")

    # Stop audio playback and disconnect from voice
    async def stop_sound(self, interaction, guild_id):
        await interaction.response.defer()

        # Serialize against the watchdog's restart_audio_loop and any concurrent
        # start/stop for the same guild — without this, stopping can race with
        # a watchdog-triggered restart and leave the bot playing or holding a
        # dangling voice connection.
        async with get_guild_audio_lock(guild_id):
            voice_client = interaction.guild.voice_client

            # Finalize sound sessions for all users before stopping
            from cogs.stats.gamification import cozy_gamification
            if voice_client and voice_client.channel:
                current_users = [member for member in voice_client.channel.members if not member.bot]
                logging.info("")
                logging.info("")
                logging.info(f"🛑 SOUND STOP: Finalizing sound tracking for {len(current_users)} users in {voice_client.channel.name} ({interaction.guild.name})")
                for member in current_users:
                    cozy_gamification.finalize_current_sound(str(member.id))
                    logging.info(f"🛑 Finalized sound tracking for {member.name}")

            if voice_client:
                # The stop button lives on ONE cog's menu, but the playing
                # sound may be owned by another cog (old menus stay clickable
                # forever). Clear EVERY audio cog's state, and do it BEFORE
                # disconnecting: any leftover is_playing state makes the
                # watchdog and the voice-drop recovery reconnect the bot
                # seconds after the stop.
                for cog_name in AUDIO_COG_NAMES:
                    cog = self.bot.get_cog(cog_name)
                    if not cog or not hasattr(cog, 'guild_states'):
                        continue
                    state = cog.guild_states.get(guild_id)
                    if not state:
                        continue
                    state['is_playing'] = False
                    state['current_sound'] = None
                    if state.get('loop_task'):
                        try:
                            state['loop_task'].cancel()
                        except Exception:
                            pass
                        state['loop_task'] = None
                    if state.get('disconnect_timer'):
                        state['disconnect_timer'].cancel()
                        state['disconnect_timer'] = None
                global_current_sounds.pop(guild_id, None)

                if voice_client.is_playing():
                    voice_client.stop()
                await voice_client.disconnect()

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
        # Acquire the shared audio mutation lock for this guild. Without it the
        # watchdog (which schedules this) and stop_sound (which clears state)
        # can interleave and produce a restart against torn-down state.
        async with get_guild_audio_lock(guild_id):
            return await self._restart_audio_loop_locked(guild_id)

    async def _restart_audio_loop_locked(self, guild_id):
        try:
            guild_state = self.get_guild_state(guild_id)
            guild = self.bot.get_guild(guild_id)
            voice_client = guild.voice_client if guild else None
            current_sound = guild_state['current_sound']
            guild_name = guild.name if guild else f"guild {guild_id}"

            if not guild:
                logging.info(f"🔄 restart_audio_loop skipped: guild not found for {guild_id}")
                return

            # Recover voice connection if Discord dropped it while users are still present.
            # A usable connection needs a live websocket: zombie clients keep
            # .channel set after a gateway drop, so .channel alone used to let
            # dead sessions pass this check and crash play() downstream.
            voice_is_ready = bool(voice_client and voice_client.channel and voice_client.is_connected())
            if not voice_is_ready:
                target_channel = guild_state.get('target_channel')
                if not target_channel:
                    logging.info(f"🔄 restart_audio_loop skipped: voice not connected in {guild_name}")
                    return

                human_members = [m for m in target_channel.members if not m.bot]
                if not human_members:
                    logging.info(
                        f"🔄 restart_audio_loop skipped: no listeners in target channel in {guild_name}"
                    )
                    return

                if voice_client:
                    # Kill the dead session first: connecting over it either
                    # raises "Already connected" or times out waiting for the
                    # voice handshake Discord will never complete.
                    await teardown_voice_client(guild)

                try:
                    voice_client = await target_channel.connect()
                    known_voice_clients[guild_id] = voice_client
                    await asyncio.sleep(0.3)
                    guild_state['target_channel'] = target_channel
                    await self.start_disconnect_timer(guild_id)
                    logging.info(
                        f"🔗 restart_audio_loop recovered voice connection in {guild_name}"
                    )
                except Exception as reconnect_error:
                    # Race condition: Discord reports already connected while recovering.
                    if "Already connected to a voice channel" in str(reconnect_error):
                        voice_client = guild.voice_client
                        if voice_client and voice_client.channel and voice_client.is_connected():
                            logging.info(
                                f"🔗 restart_audio_loop recovered existing voice connection in {guild_name}"
                            )
                            known_voice_clients[guild_id] = voice_client
                            await self.start_disconnect_timer(guild_id)
                        else:
                            logging.warning(
                                f"🔄 restart_audio_loop reconnect race but no active channel in {guild_name}"
                            )
                            return
                    else:
                        logging.warning(
                            f"🔄 restart_audio_loop reconnect failed in {guild_name}: "
                            f"{type(reconnect_error).__name__}: {reconnect_error!r}"
                        )
                        return

            if not voice_client or not voice_client.channel or not voice_client.is_connected():
                logging.info(f"🔄 restart_audio_loop skipped: voice not connected in {guild_name}")
                return

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
            if os.path.exists(sound_path) and voice_client.is_connected() and not voice_client.is_playing():
                audio_source = FFmpegPCMAudio(
                    sound_path,
                    before_options='-stream_loop -1 -loglevel panic',
                )
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
