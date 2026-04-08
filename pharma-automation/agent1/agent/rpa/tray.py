from __future__ import annotations

"""시스템 트레이 아이콘 + ON/OFF 토글.

M15: pynput 사용 (keyboard 대신, 관리자 권한 불필요).
전역 핫키: Ctrl+Shift+F12
"""

import logging
import threading

logger = logging.getLogger("agent1.rpa.tray")

HOTKEY_COMBO = {
    "ctrl",       # pynput Key modifier
    "shift",
    "f12",
}


class TrayManager:
    def __init__(self, rpa_manager):
        self.rpa_manager = rpa_manager
        self._tray_thread: threading.Thread | None = None
        self._hotkey_thread: threading.Thread | None = None
        self._icon = None
        self._hotkey_listener = None

    def start(self):
        """트레이 아이콘 + 핫키 리스너 시작."""
        self._tray_thread = threading.Thread(target=self._run_tray, daemon=True, name="tray")
        self._tray_thread.start()

        self._hotkey_thread = threading.Thread(target=self._run_hotkey, daemon=True, name="hotkey")
        self._hotkey_thread.start()

        logger.info("Tray manager started (hotkey: Ctrl+Shift+F12)")

    def _run_tray(self):
        """pystray 시스템 트레이 실행."""
        try:
            import pystray
            from PIL import Image

            # 간단한 16x16 아이콘 생성
            image = Image.new("RGB", (16, 16), color=(0, 128, 0))
            menu = pystray.Menu(
                pystray.MenuItem(
                    lambda _: f"RPA: {'ON' if self.rpa_manager.enabled else 'OFF'}",
                    self._on_toggle,
                    default=True,
                ),
                pystray.MenuItem("종료", self._on_quit),
            )
            self._icon = pystray.Icon("PharmRPA", image, "PharmRPA", menu)
            self._icon.run()
        except ImportError:
            logger.warning("pystray/Pillow not installed, tray disabled")
        except Exception as e:
            logger.error("Tray error: %s", e)

    def _run_hotkey(self):
        """pynput 전역 핫키 리스너 (M15: keyboard 대신 pynput)."""
        try:
            from pynput import keyboard

            current_keys = set()

            def on_press(key):
                try:
                    current_keys.add(key)
                    if self._check_hotkey(current_keys):
                        self._on_toggle()
                except (AttributeError, TypeError, OSError) as e:
                    logger.debug("Hotkey press error: %s", e)

            def on_release(key):
                try:
                    current_keys.discard(key)
                except (AttributeError, TypeError) as e:
                    logger.debug("Hotkey release error: %s", e)

            with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
                self._hotkey_listener = listener
                listener.join()
        except ImportError:
            logger.warning("pynput not installed, hotkey disabled")
        except Exception as e:
            logger.error("Hotkey listener error: %s", e)

    def _check_hotkey(self, current_keys) -> bool:
        """현재 눌린 키 조합이 Ctrl+Shift+F12인지 확인."""
        try:
            from pynput.keyboard import Key

            has_ctrl = any(
                k in (Key.ctrl_l, Key.ctrl_r, Key.ctrl) for k in current_keys
            )
            has_shift = any(
                k in (Key.shift_l, Key.shift_r, Key.shift) for k in current_keys
            )
            has_f12 = Key.f12 in current_keys
            return has_ctrl and has_shift and has_f12
        except ImportError:
            return False

    def _on_toggle(self, *_args):
        """RPA ON/OFF 토글."""
        new_state = self.rpa_manager.toggle()
        state_str = "ON" if new_state else "OFF"
        logger.info("RPA toggled: %s", state_str)

        if self._icon:
            try:
                from PIL import Image
                color = (0, 128, 0) if new_state else (128, 0, 0)
                self._icon.icon = Image.new("RGB", (16, 16), color=color)
                self._icon.notify(f"RPA {state_str}", "PharmRPA")
            except (ImportError, OSError) as e:
                logger.debug("Icon update failed: %s", e)

    def _on_quit(self, *_args):
        """트레이 종료."""
        self.rpa_manager.stop()
        if self._icon:
            self._icon.stop()

    def stop(self):
        """Graceful shutdown."""
        if self._hotkey_listener:
            self._hotkey_listener.stop()
        if self._icon:
            self._icon.stop()
