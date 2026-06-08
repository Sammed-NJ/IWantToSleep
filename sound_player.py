import sys
import time
import threading

# Platform check
IS_WINDOWS = sys.platform.startswith("win")
if IS_WINDOWS:
    import winsound

class SoundPlayer:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._current_sound = "classic"

    def _play_loop(self):
        """Internal playback loop run in a separate thread."""
        while not self._stop_event.is_set():
            if not IS_WINDOWS:
                # Fallback for non-windows platforms (terminal beep)
                sys.stdout.write("\a")
                sys.stdout.flush()
                time.sleep(1.0)
                continue

            try:
                if self._current_sound == "classic":
                    # Classic alarm: beep-beep, beep-beep
                    winsound.Beep(2500, 150)
                    time.sleep(0.1)
                    winsound.Beep(2500, 150)
                    # Check stop event during sleep
                    for _ in range(10):
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)

                elif self._current_sound == "pulsing":
                    # Pulsing low frequency to high frequency
                    for freq in range(800, 1500, 100):
                        if self._stop_event.is_set():
                            break
                        winsound.Beep(freq, 80)
                    for _ in range(5):
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)

                elif self._current_sound == "retro":
                    # Arcade chiptune arpeggio
                    melody = [523, 659, 784, 1047, 784, 659] # C5, E5, G5, C6, G5, E5
                    for note in melody:
                        if self._stop_event.is_set():
                            break
                        winsound.Beep(note, 100)
                    for _ in range(8):
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)

                elif self._current_sound == "siren":
                    # Wailing siren
                    for freq in range(600, 1200, 40):
                        if self._stop_event.is_set():
                            break
                        winsound.Beep(freq, 30)
                    for freq in range(1200, 600, -40):
                        if self._stop_event.is_set():
                            break
                        winsound.Beep(freq, 30)

                elif self._current_sound == "system":
                    # Windows system notification sound
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)
                    for _ in range(15):
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)

                else:
                    # Generic fallback
                    winsound.Beep(1000, 500)
                    time.sleep(0.5)

            except Exception:
                # Prevent crashing if audio device is missing or busy
                time.sleep(1.0)

    def start(self, sound_name="classic"):
        """Start playing the alarm sound in a background thread."""
        self.stop() # Ensure any previous sound thread is stopped
        self._stop_event.clear()
        self._current_sound = sound_name
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop sound playback and wait for thread to finish."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    @staticmethod
    def get_available_sounds():
        return ["classic", "pulsing", "retro", "siren", "system"]
