# Changelog

All notable changes to this project will be documented in this file.

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
