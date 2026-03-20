# Safe Call Platform - Flutter Client

This is a minimal Flutter client used to connect to the Safe Call Platform, stream audio, and interact with the LiveKit server.

## Setup

1. Make sure you have the Flutter SDK installed on your system.
2. Navigate to this directory using your terminal.
3. Run `flutter pub get` to install dependencies.
4. Start the application on your desired platform (web, android, ios, desktop) using `flutter run`.

## Notes
- By default, it connects to the FastAPI backend running at `http://127.0.0.1:8000/token`. If you're testing on an Android emulator, you might need to change the `_backendUrl` in `lib/main.dart` to `http://10.0.2.2:8000/token`.
- Audio preprocessing (echo cancellation, noise suppression, and auto gain control) is intentionally disabled for this project so the ML model can evaluate near-raw audio formats.
