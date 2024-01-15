# Changelog

All notable changes to this project will be documented in this file.

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
