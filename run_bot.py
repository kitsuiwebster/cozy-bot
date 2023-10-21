import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

bot_process = None

def start_bot():
    global bot_process

    # Kill the existing bot process if it exists
    if bot_process is not None:
        print("Killing the existing bot process...")
        bot_process.kill()
        bot_process.wait()

    # Bubulle
    # bot_process = subprocess.Popen(["C:\\Users\\Aser\\AppData\\Local\\Programs\\Python\\Python311\\python.exe", "main.py"])
    
    # Kitsui
    bot_process = subprocess.Popen(["python3", "main.py"])



class MyHandler(FileSystemEventHandler):
    # Introduce a cooldown period (in seconds)
    COOLDOWN_PERIOD = 5

    def __init__(self):
        self.last_restart_time = 0

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".py"):
            current_time = time.time()
            if current_time - self.last_restart_time > self.COOLDOWN_PERIOD:
                print(f"Changes detected in {event.src_path}, restarting bot...")
                start_bot()
                self.last_restart_time = current_time

if __name__ == "__main__":
    start_bot()

    # Watch for changes in the current directory.
    event_handler = MyHandler()
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        # Ensure the bot process is terminated when the script exits
        if bot_process is not None:
            bot_process.kill()
        observer.join()
