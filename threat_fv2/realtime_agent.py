import psutil
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import datetime
import os

class RealTimeAgent:
    def __init__(self, target_folder):
        self.events_buffer = []
        self.target_folder = target_folder
        self.lock = threading.Lock()
        self.known_pids = set()
        
        if not os.path.exists(self.target_folder):
            os.makedirs(self.target_folder)

    def start(self):
        # 1. Simple File Watcher
        self.observer = Observer()
        self.observer.schedule(SimpleHandler(self), self.target_folder, recursive=True)
        self.observer.start()
        
        # 2. Simple Process Watcher (Listens for new apps)
        # Initialize with current processes so we only catch NEW ones
        self.known_pids = {p.pid for p in psutil.process_iter()}
        threading.Thread(target=self._watch_processes, daemon=True).start()
        
        print(f"[*] SENSOR ACTIVE: Watching {self.target_folder} and new Apps.")

    def _watch_processes(self):
        last_seen_names = {} # Track when we last saw a process name
        
        while True:
            try:
                for proc in psutil.process_iter(['pid', 'name']):
                    pid = proc.info['pid']
                    name = proc.info['name']
                    
                    if pid not in self.known_pids:
                        self.known_pids.add(pid)
                        
                        # NOISE FILTER: 
                        # If we saw this same app name in the last 3 seconds, ignore it.
                        # This stops browsers like Edge/Chrome from flooding the logs.
                        now = time.time()
                        if name in last_seen_names and (now - last_seen_names[name]) < 3:
                            continue
                        
                        # NOISE FILTER 2: BLOCKLIST (System Background Tasks)
                        # These run automatically by Windows, so we hide them to show only "Manual" user apps.
                        ignore_list = [
                            'svchost.exe', 'conhost.exe', 'RuntimeBroker.exe', 'SearchApp.exe', 
                            'taskhostw.exe', 'DllHost.exe', 'sihost.exe', 'smartscreen.exe',
                            'ctfmon.exe', 'csrss.exe', 'lsass.exe', 'winlogon.exe', 'services.exe',
                            'TextInputHost.exe', 'ApplicationFrameHost.exe', 'System', 'Registry'
                        ]
                        
                        if name in ignore_list:
                            continue

                        last_seen_names[name] = now
                        print(f"[!] New App Started: {name}")
                        self._add_event(f'START: {name}', 1, 0.4)
                time.sleep(1)
            except: pass

    def _add_event(self, action_type, resource_count, complexity):
        with self.lock:
            self.events_buffer.append({
                'timestamp': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'user_id': os.getlogin(),
                'action_type': action_type,
                'resource_access_count': resource_count,
                'cmd_complexity': complexity
            })

    def get_new_events(self):
        with self.lock:
            events = list(self.events_buffer)
            self.events_buffer.clear()
            return events

class SimpleHandler(FileSystemEventHandler):
    def __init__(self, agent): self.agent = agent
    def on_modified(self, event): 
        if not event.is_directory: self.agent._add_event('FILE_WRITE', 5, 0.3)
    def on_created(self, event): self.agent._add_event('FILE_CREATE', 10, 0.5)