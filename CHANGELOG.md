# Changelog

All notable changes to this project will be documented in this file.

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
