import threading
import time
import urllib.request


class TradeFriendSystemHealthService:
    """
    Centralized system health monitor.
    Tracks:
        - Internet connectivity
        - Broker connection (future ready)
        - WebSocket connection (future ready)
    """

    def __init__(self, check_interval: int = 10):
        self.check_interval = check_interval

        self.internet_ok = True
        self.broker_ok = True
        self.websocket_ok = True

        self._callbacks = []
        self._running = False

    # =====================================================
    # PUBLIC METHODS
    # =====================================================
    def start(self):
        if self._running:
            return
        self._running = True
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def register_callback(self, callback):
        """
        UI or Engine can register for health updates.
        callback will receive (health_service_instance)
        """
        self._callbacks.append(callback)

    def is_system_ready(self) -> bool:
        """
        System is tradable only if all health flags are True.
        """
        return self.internet_ok and self.broker_ok and self.websocket_ok

    # =====================================================
    # INTERNAL LOOP
    # =====================================================
    def _monitor_loop(self):
        while self._running:
            new_status = self._check_internet()

            if new_status != self.internet_ok:
                self.internet_ok = new_status
                self._notify()

            time.sleep(self.check_interval)

    def _check_internet(self, timeout=3):
        try:
            urllib.request.urlopen("https://www.google.com", timeout=timeout)
            return True
        except:
            return False

    def _notify(self):
        for cb in self._callbacks:
            try:
                cb(self)
            except:
                pass