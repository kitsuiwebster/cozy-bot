# Changelog

All notable changes to this project will be documented in this file.

## [2.1.6] - 2026-07-17

### Fixed

- Audio state is now written to CouchDB synchronously before deploy shutdown; the queued write could be lost when the container was killed, leaving nothing to restore (bot not rejoining voice after a deploy).
- Telegram listener-count pings wait 3s before sampling, so sound emojis match what the website shows (they used to fire mid-transition, before the sound was registered).
- Sound-menu stop button now clears every sound category's state; clicked from another category's menu, it used to leave stale playing state and the bot reconnected seconds later.

## [2.1.5] - 2026-07-16

### Fixed

- Telegram listener-count pings now only skip consecutive duplicates; the previous 5-minute dedup window hid real transitions.

## [2.1.4] - 2026-07-16

### Added

- Telegram listener-count messages now show the playing sound emojis.

### Fixed

- Bot now recovers within seconds when Discord kills a voice connection (server migration, gateway resume failure) instead of staying silently absent.
- Dead voice clients are fully torn down before reconnecting, removing "Not connected to voice." errors and reconnect timeouts.
- Orphaned voice connections no longer sabotage new connection attempts (bot joining then leaving instantly).
- `/stop` no longer gets undone by the playback watchdog reconnecting the bot.
- Sound buttons, watchdog, auto-disconnect timer and audio restore now share one per-guild lock, removing connect/stop races.
- Restored audio sessions now auto-disconnect from empty channels.
- Telegram alerts are no longer dropped during bursts of listener-count pings (separate rate-limit budget).
- Status page no longer shows green during bot outages.

### Changed

- Bumped `discord.py[voice]` to 2.7.1.
- discord.py voice and gateway logs kept at INFO in container logs for post-incident tracing.

## [2.1.3] - 2026-07-07

### Added

- Status page outages now alert on Telegram in real time: `status-api` sends a message the moment a monitored service (public API, live bot, database) goes down, and another when it recovers, so Telegram always reflects what the status page shows.

### Fixed

- Bot presence updates and the playback watchdog no longer crash `on_ready` with "Task is already launched" after a Discord gateway reconnect.
- Telegram no longer receives achievement-unlock alerts or two self-healing conditions that didn't need admin action (a stale voice-state cache read, and periodic cleanup of orphaned listening sessions) — both stay in local logs only.

## [2.1.2] - 2026-05-18

### Fixed

- CouchDB reads now retry on transient network errors (DNS hiccup, connection refused, timeout) instead of silently returning empty data.
- Bot container keeps more log history on disk (250 MB vs 30 MB), so past errors stay visible for investigation.

## [2.1.1] - 2026-05-17

### Fixed

- Global event error handler now includes the exception traceback in logs and Telegram alerts.

## [2.1.0] - 2026-05-16

### Added

- Telegram notifier for warning/error logs, listener count changes, and achievement unlocks (env-driven, with throttling).
- Sound buttons usable by anyone in the bot's voice channel.
- "Now playing" message auto-deletes after 5 minutes.
- Loading skeletons with shimmer animation on the status page.
- Status page favicon matching the CozyBot logo.
- `make help` warning markers on commands that can affect CouchDB data.

### Changed

- Frontend dev environment now points at the local API by default; production unchanged.
- CORS origins and Status API monitor URLs driven by environment variables instead of hardcoded values.
- `status-api` waits for Uptime Kuma to be healthy before starting (was just "started").

### Fixed

- CouchDB writes no longer lost silently on concurrent conflicts (retry with backoff up to 5 times).
- API healthchecks now reflect actual dependency state instead of always reporting OK.
- Audio start/stop/restart actions for a guild serialized to remove race conditions on shared state.
- Streak rollover and daily activity now use a consistent UTC day boundary regardless of host timezone.
- User identifiers normalized to a single type across gamification, preventing duplicate keys.
- Leaderboard display names no longer flicker between the global name and the raw username.
- Loyalty bonuses (30 min / 1 h / 12 h on the same sound) reachable again after a quick voice rejoin.
- Sound-master achievements (Rain/Sea/Sparkles/Music) now actually unlock when earned.
- Session credit reordered so concurrent finalize/backup paths no longer double-credit listening time or points.
- 30-minute session cap now logs the user and sound responsible for the trimmed credit.
- Top-N and debug endpoints capped/paginated to prevent unbounded responses.
- Admin endpoints reject out-of-range numbers and return 404 (not 500) for unknown users.
- `simple_deployment/check-status` returns a proper error code on failure (was HTTP 200 with `status: "error"`).
- API error responses no longer leak internal Python tracebacks.
- Duplicate audio control endpoints on the public API removed; canonical routes live under `/api/live/audio/*`.
- Obsolete startup handoff to the removed endpoints cleaned up.
- Playback watchdog no longer warns about "stalled" audio when the voice channel is simply empty.
- Exception tracebacks now appear in logs for Discord.py "Ignoring exception" messages.
- Website fetches now time out after 15 seconds, render a real 404 on unknown URLs, and stop leaking subscriptions in long-running tabs.
- Status page polling cancels in-flight requests under slow networks instead of stacking them.
- Deploy script no longer masks docker build failures as success.
- Re-running the CouchDB migration merges existing docs instead of silently skipping them.
- CI security scan workflow restored.

## [2.0.5] - 2026-03-05

### Fixed

- Fixed voice connections by adding DAVE protocol support (`discord.py[voice]`, `davey`).

## [2.0.4] - 2026-02-28

### Changed

- Updated bot dependency pin to `discord.py==2.7.0` for DAVE voice protocol compatibility.

### Fixed

- Voice restart recovery now avoids false reconnect/disconnect races (`Already connected to a voice channel`) and keeps playback loop more stable.
- User session joins are now recorded in normal voice-join flows, fixing `sessions_joined`/recent activity inconsistencies for newer users.

## [2.0.3] - 2026-02-27

### Fixed

- Fixed Discord `FFmpegPCMAudio` stderr misconfiguration (`stderr=subprocess.DEVNULL`) that caused recurring `Write error` crashes and rapid reconnect/restart loops.
- Prevented concurrent restart races by enforcing a single restart task per guild in audio loop recovery.

## [2.0.2] - 2026-02-19

### Added

- Dedicated Trivy security scan workflow in GitHub Actions (`.github/workflows/trivy-scan.yml`) for CI/CD-only image scanning.

### Fixed

- Audio loop stability by restoring native FFmpeg stream looping (`-stream_loop -1`) to prevent periodic write errors during track rollover.
- FFmpeg cleanup resilience by ignoring sporadic `EBADF` process cleanup failures in Discord player teardown.
- Duplicate bot voice disconnect handling now idempotent to prevent double session finalization and duplicate point/time saves.
- Live API latency serialization now guards against non-finite float values to avoid JSON compliance crashes.
- Public API `/api/public/top-servers` sorting bug causing HTTP 500 (invalid sort key function signature).

## [2.0.1] - 2026-02-03

### Added

- Live stats now expose `active_usernames` and per-sound category counts for the header.

### Fixed

- noise01/white-noise01 normalization across stats aggregation and display.
- Streaks now update during periodic backups if join events were missed.
- API streak calculation now uses fresh user stats to avoid stale in-memory values.
- Bot presence server count now matches CouchDB servernames (aligns with public stats).
- Deployment notifier no longer shows commit hashes in user-facing messages.
- Playback watchdog to restart stalled audio loops (10s interval, 30s cooldown).

## [2.0.0] - 2026-02-01

### Added

- Public/Live API split with explicit `/api/public/*` and `/api/live/*` routes plus endpoint health logging.
- Status API microservice with 90-day history and maintenance tracking (SQLite) for the custom status page.
- Custom status page redesign with live refresh, responsive layout, legends, and maintenance banners.
- Status page proxying for Public API + Status API and Kuma fallback, plus UI link helper (`make ui`).
- Uptime Kuma seed support and status page integration.
- CouchDB view seeding script (`make seed-db`) and organized seed files.
- Deploy script improvements for Live API checks, notifications, and restore flow.
- Status maintenance history tracking and banner metadata (started/ended timestamps).
- Bot voice handling moved to dedicated threads/workers for DB writes and background tasks.
- Leaderboard shared header component and consistent header stats across pages.
- Status API-backed monitor history endpoints and public status API routes.

### Changed

- Stack layout reorganized under `stack/` with clear app/infra separation and consistent make targets.
- Dev/prod configuration unified to a single stack with environment-driven values only.
- Docker compose services/ports/volumes renamed for consistency across environments.
- Bot/API logging cleaned up and grouped; new API endpoint listing sections in bot startup logs.
- Status page and web UI typography/colors aligned.
- Status page now reads from `/api/status/*` instead of Public API routes.
- Make targets aligned and expanded per service (status API DB helper, UI links, seeds).
- Status page monitor ordering with Bot (Live API) first.
- Bot presence rotation now alternates server count and `/menu`.
- Noise menu entry uses 📡 icon.
- Web modal UI polish and refreshed leaderboard visuals.
- Web API polling tuned (live stats 5s, header totals 60s, manual refresh for lists).
- Status page mobile layout uses desktop viewport width.
- Credits button removed and streak bonus copy corrected.

### Fixed

- Voice restore pipeline and task cleanup reliability.
- Status page API routing and JSON responses for monitors/history/maintenance.
- CouchDB conflicts, maintenance visibility, and periodic backup stability.
- Makefile command coverage and help output accuracy.
- Audio restore cleanup errors when deleting CouchDB docs without `_rev`.
- Voice connection stability improvements (reliable channel join and consistent playback start).
- Status page uptime percentage calculations and maintenance coloring.
- Status page Nginx proxying with full URI handling.
- CORS handling for public API calls.
- Admin API writes now persist to CouchDB consistently.
- Audio playback change latency and restore write reliability.
- Live stats glow/animation and cached values between page switches.

### Removed

- Legacy dev-only compose files and redundant dev/prod suffix handling in the stack.

## [1.0.22] - 2026-01-24

### Added

- User count validation before voice connection with helpful error message for Discord token limitation workaround.
- Bidirectional merge scripts (merge_to_prod.sh and merge_to_dev.sh) for dev/prod synchronization.

### Fixed

- Voice connection attempts now blocked when 2+ users in channel, preventing timeout issues on production token.

## [1.0.21] - 2026-01-23

### Fixed

- Voice connection stability with instant audio start, race condition prevention, ghost connection cleanup, and improved timeout handling.

### Changed

- Sound filenames now displayed in cyan color across all logs for better readability.
- Audio restoration monitor now logs individual user tracking instead of bulk counts.
- Production deployment now uses code mounting for faster hot-reload like development environment.

## [1.0.20] - 2026-01-22

### Changed

- Complete architecture refactoring with separate `dev/` and `prod/` directories for independent deployments on same VPS.
- Docker volume configuration now uses environment-specific volumes (`cozy-bot-voice-data-dev` and `cozy-bot-voice-data-prod`).
- FFmpeg log level changed from error to panic to suppress bitrate estimation warnings.

### Fixed

- Gamification username tracking bug causing AttributeError when usernames data was None or missing from initialization.
- Server time data merge logic now preserves API modifications during periodic saves by reloading from disk.
- Obsolete reconnect check removed that caused premature disconnections with "hiccup" error messages.

## [1.0.19] - 2026-01-19

### Added

- Admin API endpoint `/api/admin/server-time` to add or remove voice time from servers by guild ID.

### Fixed

- Voice channel connexion wrong status resolved with forced disconnect cleanup and retry logic.
- Audio restoration now properly updates cog guild states to enable sound tracking for users joining after bot restart.
- Server voice time data corruption prevention with improved format validation and preservation logic.

## [1.0.18] - 2026-01-18

### Added

- `/menu` command displaying all available sound commands with categories and counts.
- Extended `/rain` command with 5 additional rain ambiances (rain05-09) for a total of 10 rain sounds.

### Changed

- `/white-noise` command renamed to `/noise` for simplified command naming.
- Production deployment script now performs hard reset from origin/main branch for consistent deployments.
- Development deployment script now skips API notification calls in local environment for faster iteration.
- Streak bonus points now capped at 20 points per 10-minute period to prevent exploitation.

### Fixed

- `/top-sounds` command now displays emoji labels instead of raw .mp3 filenames for better readability.
- Audio playback validation when bot connects to voice channel preventing silent connection states.
- Active listener count in stats API route now correctly counts only users with active sessions.
- Session error handling improved to prevent crashes during user tracking operations.
- Audio files retain white-noise naming convention for backward compatibility with session restoration.
- FFmpeg log spam suppressed by setting log level to error-only output.

## [1.0.17] - 2026-01-11

### Fixed

- Username display priority now correctly uses global_name or username fallback instead of server-specific display_name.

## [1.0.16] - 2026-01-10

### Added

- User session restoration system that automatically reconnects users and resumes their gamification tracking after hot deployments.
- Session finalization endpoints to properly save voice time and award points before deployment updates.

### Changed

- Docker build logs now stream in real-time with intelligent filtering for improved deployment visibility.

### Fixed

- SSH connection hanging in CI/CD pipelines causing unnecessary 5-minute delays after successful deployments.
- `make stop-dev` command incorrectly stopping production containers instead of only development containers.

## [1.0.15] - 2026-01-09

### Added

- Zero-downtime hot deployment system with automatic user notifications and seamless audio restoration.
- Pre-deployment Discord notifications sent 30 seconds before updates to all users in active voice channels.
- Automatic audio session persistence and restoration across bot deployments using JSON state management.

### Changed

- Enhanced deployment scripts for both development and production environments.

## [1.0.14] - 2025-11-18

### Added

- New `/credits` command displaying attribution links for all sound creators with a clean embed interface.

### Fixed

- Bot reconnection system properly restores user tracking sessions after timeout disconnections preventing users from disappearing from periodic saves.
- Sound state contamination between different audio cogs (rain, music, sea, etc.) causing false duplicate playback errors.
- User data protection against null pointer exceptions in gamification system initialization.

## [1.0.13] - 2025-11-16

### Added

- AES-256 encryption with PBKDF2 key derivation for GDPR-compliant data storage protection.
- GDPR deletion request command (`/delete-request`) with 30-day data retention notice.

### Changed

- Server members intent restored for global display name access while maintaining security posture.

### Fixed

- Loyalty bonus calculation now based on consecutive session time instead of total accumulated time.
- Empty data handling for fresh container deployments preventing AttributeError crashes.
- Development deployment port conflicts by using separate port 8001 for dev environment.
- CI/CD deployment stability with improved error handling and volume mount corrections.

## [1.0.12] - 2025-11-15

### Changed

- Top sounds API endpoint now returns all sounds instead of limiting results to 10 entries.
- Minimized Discord bot permissions to essential voice and command interactions only.
- Reduced required intents to guilds and voice states for optimal security posture.

### Removed

- Complete reactions system including multilingual rain keyword detection for enhanced security.
- Message content intent requirement by eliminating message processing functionality.

## [1.0.11] - 2025-11-15

### Added

- Streak bonus system awarding additional points based on daily activity streaks during periodic saves.
- Voice connection retry logic with exponential backoff to handle Discord API instability and timeouts.
- Duplicate joining session prevention system with 2-minute cooldown to avoid spam during reconnections.

### Fixed

- Server time accumulation when bot is not connected to voice channels preventing phantom active sessions.
- Discord voice connection timeouts with improved retry mechanisms and connection stability.
- Bot disconnect logging accuracy showing correct final chunk duration and points awarded.

## [1.0.10] - 2025-11-14

### Added

- API endpoints health check system during bot initialization with status validation for all routes.
- Stylized ASCII banner header displaying at bot startup with version and developer credits.
- `/stats` command to provide direct access to statistics website with user rankings and analytics.

### Changed

- Enhanced CozyPoints system with loyalty bonuses, streak bonuses and category completion.
- Sound tracking logging system is now much more detailed and clean.

### Fixed

- Sound tracking time calculation now properly counts listening time when user quits voice channel.
- Duplicate point saves in finalize_current_sound function.
- Session duration validation (30min cap) to prevent corrupted data in periodic and event backups.

## [1.0.9] - 2025-11-13

### Added

- Advanced sound analytics system with per-sound listening time tracking for detailed user preferences.
- `/top-sounds` command to display most listened sounds globally with formatted time and listener counts.
- `/api/top-sounds` endpoint to retrieve sound popularity statistics with emoji display names.
- HTTPS support with Let's Encrypt SSL certificates for secure API access.
- Favorite sound calculation based on listening time instead of session count.

### Changed

- User profiles now display favorite sounds with actual listening time duration instead of session counts.
- Daily streak calculation to preserve streaks during bot restarts and only reset after 24+ hours of inactivity.
- Sound preference tracking to monitor actual listening duration per sound for accurate analytics.

### Fixed

- Streak data loss during bot restarts - streaks are now properly preserved across deployments.

## [1.0.8] - 2025-11-12

### Added

- REST API with live data access for bot statistics integration with external websites.
- `/api/top-users` endpoint to retrieve top users by cozy points with usernames and display names.
- `/api/top-servers` endpoint to retrieve top servers by voice time with formatted duration display.
- `/api/total` endpoint for real-time active listener statistics with cozy messages.
- Live bot instance sharing between Discord bot and FastAPI for real-time data access.

### Changed

- Gamification system to cache both Discord usernames and global display names.
- User data structure to support username tracking and display name caching.
- API architecture to run within the same container as the Discord bot for optimal performance.

## [1.0.7] - 2025-10-31

### Fixed

- User listening time tracking not accumulating properly.
- Duplicate sound selection protection triggering when bot is disconnected.

### Changed

- Voice state tracking system to use event-driven approach for better accuracy and performance.

## [1.0.6] - 2025-10-28

### Added

- Configurable startup message system.
- Optional user parameter to `/profile` command for viewing other users' profiles.
- Automated daily backup system for user data preservation.

### Fixed

- Audio stopping issues - sounds now play continuously until manually stopped.
- Display inconsistencies to show actual Discord usernames instead of display names.
- Data persistence issues between different deployment environments.
- Updated `/total` command to show only user counts without revealing usernames.

## [1.0.5] - 2025-10-26

### Added

- Gamification system with `/profile`, `/top-users`, and `/achievements` commands for user engagement tracking.
- Persistent server data with Docker volume implementation.
- Better UX and sound playing logic.
- Reactions in multiple languages.
- `/stop` command for stopping currently playing sounds.

### Fixed

- Fixed total command data persistence issues.
- Resolved deployment script errors (cd error 255).
- Fixed py-cord compatibility issues by migrating to discord.py.

### Changed

- Complete architecture refactoring for all audio commands (`/rain`, `/sea`, `/sparkles`, `/music`).
- Renamed `/background-music` command name to `/music`.
- Renamed `/top` command to `/top-servers`.
- Enhanced file locking implementation with fcntl for better data consistency.
- Refactored codebase structure for better maintainability.

## [1.0.4] - 2024-05-25

### Added

- `/background-music` command for playing ambient background music.
- `/sea` command for playing sea wave sounds in voice channels.
- Added the last sound for the `/sparkles` command.

### Fixed

- Fixed an issue where the `/top` command was not loading.
- Replaced the unsupported log emoji with a tree emoji for Windows users.

### Changed

- Updated the interaction system to prompt users to use commands when they're not permitted to use buttons.
- Modified the `/top` command to display server rankings in days, hours, minutes, and seconds format.

## [1.0.3] - 2024-02-07

### Added

- `/total` command to track the number of people currently interacting with CozyBot.
- The bot now leaves the voice channel if it finds itself alone for more than 30 minutes.

## [1.0.2] - 2024-01-19

### Added

- `/top` command to display the top servers ranked by the time spent with CozyBot.

### Fixed

- Fixed a bug where sounds would stop unexpectedly.


## [1.0.1] - 2024-01-15

### Added

- `/sparkles` command with 4 different sparkles ambiances.

### Fixed

- Resolved an issue where the stop button would cause an error if clicked multiple times in succession.
- The bot now disconnects from the voice channel after the stop button is clicked.

## [1.0.0] - 2023-10-30

### Added

- Ability to join any voice channel the user is in with the `/rain` command.
- Interactive UI with emojis for choosing from 5 types of rain ambiance.
- Error handling to ensure only the command initiator can interact with buttons.
- Check to ensure the user is in a voice channel before executing the `/rain` command.
- Stop functionality to stop the currently playing sound.
- Error handling for voice channel connection and audio playback issues.
- Reacts to keywords related to rain.
