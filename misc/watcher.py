#!/usr/bin/env python3

import argparse
import subprocess
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, command, files_to_watch):
        self.command = command
        self.files_to_watch = set(files_to_watch)

    def on_modified(self, event):
        if event.src_path in self.files_to_watch:
            print(f"{event.src_path} has been modified. Running command: {self.command}")
            subprocess.run(self.command, shell=True)

def watch_files(command, files):
    event_handler = FileChangeHandler(command, files)
    observer = Observer()

    for file in files:
        observer.schedule(event_handler, path=file, recursive=False)

    observer.start()
    print(f"Watching files: {', '.join(files)}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Watch files and run a command on modification.")
    parser.add_argument("--cmd", type=str, required=True, help="Command to run when files are modified.")
    parser.add_argument("--files", nargs='+', required=True, help="List of files to watch.")

    args = parser.parse_args()

    watch_files(args.cmd, args.files)

