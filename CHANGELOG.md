# Changelog

All notable changes to this project will be documented in this file.

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
