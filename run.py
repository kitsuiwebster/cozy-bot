#!/usr/bin/env python3
"""
Discord Bot Unified Launcher
Supports both development and production modes
Usage: python run.py -dev | -prod
"""

import os
import sys
import subprocess
import shutil
import time
import argparse
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Global variable for bot process (development mode)
bot_process = None

def check_required_files():
    """Check if all required files exist in the repository"""
    print("🔍 Checking repository structure...")
    
    required_files = {
        # Core files
        "main.py": "Main bot script",
        "requirements.txt": "Python dependencies",
        
        # Command files
        "commands/rain.py": "Rain sound command",
        "commands/sea.py": "Sea sound command",
        "commands/sparkles.py": "Sparkles sound command",
        "commands/top.py": "Top servers command",
        "commands/total.py": "Total users command",
        "commands/background-music.py": "Background music command",
        
        # Reaction handler
        "reactions/reactions.py": "Message reaction handler",
        
        # Documentation
        "README.md": "Project documentation",
        "CHANGELOG.md": "Project changelog",
        "LICENSE": "Project license",
        
        # Docker configuration
        "docker-compose.yml": "Docker compose configuration"
    }
    
    required_directories = {
        "commands": "Bot commands directory",
        "reactions": "Message reactions directory", 
        "sounds": "Audio files directory",
        "assets": "Project assets directory"
    }
    
    missing_files = []
    missing_dirs = []
    
    # Check files
    for file_path, description in required_files.items():
        if not Path(file_path).exists():
            missing_files.append(f"  ❌ {file_path} - {description}")
        else:
            print(f"  ✅ {file_path}")
    
    # Check directories
    for dir_path, description in required_directories.items():
        if not Path(dir_path).exists():
            missing_dirs.append(f"  ❌ {dir_path}/ - {description}")
        else:
            print(f"  ✅ {dir_path}/")
    
    if missing_files or missing_dirs:
        print("\n⚠️  Missing required files/directories:")
        for item in missing_files + missing_dirs:
            print(item)
        return False
    
    print("✅ All required files and directories found!")
    return True

def check_sound_files():
    """Check if sound files are present"""
    print("\n🔊 Checking sound files...")
    
    sound_categories = {
        "rain": ["rain00.mp3", "rain01.mp3", "rain02.mp3", "rain03.mp3", "rain04.mp3"],
        "sea": ["sea00.mp3", "sea01.mp3", "sea02.mp3", "sea03.mp3", "sea04.mp3"],
        "sparkles": ["sparkles00.mp3", "sparkles01.mp3", "sparkles02.mp3", "sparkles03.mp3", "sparkles04.mp3"],
        "background-music": ["background-music00.mp3", "background-music01.mp3", "background-music02.mp3", "background-music03.mp3", "background-music04.mp3"]
    }
    
    sounds_dir = Path("sounds")
    missing_sounds = []
    
    for category, files in sound_categories.items():
        print(f"  🎵 {category.capitalize()} sounds:")
        for sound_file in files:
            sound_path = sounds_dir / sound_file
            if sound_path.exists():
                print(f"    ✅ {sound_file}")
            else:
                print(f"    ❌ {sound_file}")
                missing_sounds.append(f"sounds/{sound_file}")
    
    if missing_sounds:
        print(f"\n⚠️  {len(missing_sounds)} sound files are missing")
        print("🎵 Bot will work but some audio options may not be available")
    else:
        print("✅ All sound files found!")
    
    return len(missing_sounds) == 0

def check_python_dependencies():
    """Check if required Python packages are installed"""
    print("\n📦 Checking Python dependencies...")
    
    try:
        import discord
        print(f"  ✅ discord.py/py-cord: {discord.__version__}")
    except ImportError:
        print("  ❌ discord.py/py-cord not installed")
        return False
    
    dependencies = [
        ("aiohttp", "aiohttp"),
        ("dotenv", "python-dotenv"), 
        ("watchdog", "watchdog")
    ]
    
    missing_deps = []
    
    for module, package in dependencies:
        try:
            __import__(module)
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package}")
            missing_deps.append(package)
    
    if missing_deps:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing_deps)}")
        print("🔧 Run: pip install -r requirements.txt")
        return False
    
    return True

def check_ffmpeg():
    """Check if FFmpeg is available for audio processing"""
    print("\n🎬 Checking FFmpeg availability...")
    
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"  ✅ {version_line}")
            return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    
    print("  ❌ FFmpeg not found or not working")
    print("  🔧 Install FFmpeg for audio functionality:")
    print("     - Ubuntu/Debian: sudo apt install ffmpeg")
    print("     - macOS: brew install ffmpeg") 
    print("     - Windows: Download from https://ffmpeg.org/")
    return False

def setup_environment(mode):
    """Setup environment based on mode (dev or prod)"""
    print(f"\n🔧 Setting up {mode} environment...")
    
    env_file = f".env.{mode}"
    env_path = Path(env_file)
    
    if not env_path.exists():
        print(f"❌ {env_file} file not found!")
        print(f"📝 Create a {env_file} file with:")
        print("   DISCORD_BOT_TOKEN=your_bot_token")
        print(f"   ENVIRONMENT={mode}ment")
        return False
    
    # Copy environment file to .env
    try:
        shutil.copy2(env_file, ".env")
        print(f"✅ {mode.capitalize()} configuration copied ({env_file} → .env)")
        return True
    except Exception as e:
        print(f"❌ Error copying .env file: {e}")
        return False

def start_bot():
    """Start the bot process (development mode)"""
    global bot_process

    # Kill the existing bot process if it exists
    if bot_process is not None:
        print("🔄 Restarting bot...")
        try:
            bot_process.terminate()
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            print("⚠️  Force stopping bot...")
            bot_process.kill()
            bot_process.wait()

    # Start new bot process
    print("🚀 Starting bot...")
    try:
        bot_process = subprocess.Popen([sys.executable, "main.py"])
    except Exception as e:
        print(f"❌ Error starting bot: {e}")

class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events for hot-reload"""
    COOLDOWN_PERIOD = 3
    
    def __init__(self):
        self.last_restart_time = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        
        # Only restart for Python files, but exclude __pycache__
        if event.src_path.endswith(".py") and "__pycache__" not in event.src_path:
            current_time = time.time()
            if current_time - self.last_restart_time > self.COOLDOWN_PERIOD:
                print(f"📝 Changes detected in {event.src_path}")
                start_bot()
                self.last_restart_time = current_time

def run_development_mode():
    """Run bot in development mode with hot-reload"""
    print("\n🚀 Starting bot in development mode with hot-reload...")
    print("💡 Press Ctrl+C to stop the bot")
    print("📝 File changes will automatically restart the bot")
    print("-" * 50)
    
    # Start the bot initially
    start_bot()

    # Watch for changes in the current directory
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping hot-reload...")
        observer.stop()
        
        # Ensure the bot process is terminated when the script exits
        if bot_process is not None:
            print("🛑 Stopping bot...")
            try:
                bot_process.terminate()
                bot_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bot_process.kill()
                bot_process.wait()
        
        observer.join()
        print("✅ Bot stopped cleanly")

def run_production_mode():
    """Run bot in production mode"""
    print("\n🚀 Starting bot in production mode...")
    print("💡 Press Ctrl+C to stop the bot")
    print("-" * 50)
    
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching bot: {e}")
        return 1
    except FileNotFoundError:
        print("❌ Python not found. Make sure Python is installed.")
        return 1

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Discord Bot Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--dev", 
        action="store_true",
        help="Development mode with hot-reload and file watching"
    )
    parser.add_argument(
        "--prod", 
        action="store_true",
        help="Production mode for stable deployment"
    )
    
    args = parser.parse_args()
    
    # Determine mode
    if args.dev and args.prod:
        print("❌ Cannot specify both --dev and --prod modes")
        return 1
    elif args.dev:
        mode = "dev"
    elif args.prod:
        mode = "prod"
    else:
        print("🚀 Discord Bot Launcher")
        print("=" * 50)
        print("Usage: python run.py [--dev | --prod]")
        print("  --dev   : Development mode with hot-reload and file watching")
        print("  --prod  : Production mode for stable deployment")
        print("\nExamples:")
        print("  python run.py --dev    # Start in development mode")
        print("  python run.py --prod   # Start in production mode")
        return 1
    
    print(f"🚀 Discord Bot Launcher - {mode.upper()} Mode")
    print("=" * 50)
    
    # Run comprehensive checks only in development mode
    if mode == "dev":
        checks_passed = 0
        total_checks = 4
        
        if check_required_files():
            checks_passed += 1
        
        if check_sound_files():
            checks_passed += 1
        
        if check_python_dependencies():
            checks_passed += 1
            
        if check_ffmpeg():
            checks_passed += 1
        
        print(f"\n📊 Repository Health: {checks_passed}/{total_checks} checks passed")
        
        if checks_passed < 3:
            print("❌ Critical issues found. Please fix them before continuing.")
            return 1
    
    # Setup environment
    if not setup_environment(mode):
        return 1
    
    # Verify main.py exists
    if not Path("main.py").exists():
        print("❌ main.py not found!")
        print("📁 Make sure you're in the correct directory")
        return 1
    
    # Launch bot based on mode
    if mode == "dev":
        run_development_mode()
    else:
        run_production_mode()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())