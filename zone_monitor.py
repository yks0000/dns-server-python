import time

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import constants
import load_zones
import logpublisher

logger = logpublisher.logger()


class EventHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        path = event.src_path
        file_name = path.split("/")[-1]
        zone_name = ".".join(file_name.split(".")[:-1])
        if str(path).endswith(".json") and zone_name in constants.ALLOWED_ZONES:
            logger.info(
                f"Zone file {file_name} for DNS Zone {zone_name} {event.event_type}. Reloading DNS records"
            )
            load_zones.zone_info = load_zones.load_zones(path)


def monitor():
    path = "zones"
    event_handler = EventHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
