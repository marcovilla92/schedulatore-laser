"""Config hot-reload service using file polling.

Watches ``config.json`` for changes (by mtime) and triggers a callback
with the new configuration dictionary when the file is modified.
"""
import json
import logging
import os
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class ConfigWatcher:
    """Watches config.json for changes and triggers reload.

    Uses polling (checks mtime every interval seconds).
    Thread-safe: callback is called from the watcher thread.
    """

    def __init__(self, config_path: str, callback: Callable[[dict], None],
                 interval: float = 2.0):
        """Initialize watcher.

        Args:
            config_path: path to config.json
            callback: function called with new config dict when file changes
            interval: polling interval in seconds
        """
        self.config_path = config_path
        self.callback = callback
        self.interval = interval
        self._last_mtime = 0.0
        self._running = False
        self._thread = None

        # Initialize last mtime
        if os.path.isfile(config_path):
            self._last_mtime = os.path.getmtime(config_path)

    def start(self):
        """Start watching in background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        logger.info("ConfigWatcher avviato: %s (intervallo: %.1fs)",
                    self.config_path, self.interval)

    def stop(self):
        """Stop watching."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=self.interval + 1)
            self._thread = None
        logger.info("ConfigWatcher fermato")

    def _poll(self):
        """Poll loop running in background thread."""
        while self._running:
            try:
                if os.path.isfile(self.config_path):
                    current_mtime = os.path.getmtime(self.config_path)
                    if current_mtime > self._last_mtime:
                        self._last_mtime = current_mtime
                        logger.info("Config modificato, ricarico...")
                        try:
                            with open(self.config_path, 'r', encoding='utf-8') as f:
                                new_config = json.load(f)
                            self.callback(new_config)
                            logger.info("Config ricaricato con successo")
                        except (json.JSONDecodeError, IOError) as e:
                            logger.error("Errore ricaricamento config: %s", e)
            except Exception as e:
                logger.error("Errore ConfigWatcher: %s", e)

            time.sleep(self.interval)

    @property
    def is_running(self) -> bool:
        """Whether the watcher thread is active."""
        return self._running
