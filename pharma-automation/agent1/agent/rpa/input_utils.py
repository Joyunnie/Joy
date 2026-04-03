from __future__ import annotations

"""키보드/마우스 입력 헬퍼 (pyautogui 래핑)."""

import logging
import time

logger = logging.getLogger("agent1.rpa.input")

# pyautogui fail-safe 설정
try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.1
except ImportError:
    pyautogui = None
    logger.warning("pyautogui not installed")


def click(x: int, y: int, clicks: int = 1, interval: float = 0.1):
    """지정 좌표 클릭."""
    if not pyautogui:
        raise RuntimeError("pyautogui not available")
    pyautogui.click(x, y, clicks=clicks, interval=interval)
    time.sleep(0.1)


def double_click(x: int, y: int):
    """지정 좌표 더블클릭."""
    if not pyautogui:
        raise RuntimeError("pyautogui not available")
    pyautogui.doubleClick(x, y)
    time.sleep(0.1)


def type_text(text: str, interval: float = 0.02):
    """텍스트 입력. 한글은 pyperclip+hotkey 방식 사용."""
    if not pyautogui:
        raise RuntimeError("pyautogui not available")
    try:
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.1)
    except ImportError:
        pyautogui.typewrite(text, interval=interval)


def press_key(key: str):
    """단일 키 입력 (예: 'enter', 'escape', 'tab')."""
    if not pyautogui:
        raise RuntimeError("pyautogui not available")
    pyautogui.press(key)
    time.sleep(0.1)


def hotkey(*keys: str):
    """조합 키 입력 (예: 'ctrl', 'a')."""
    if not pyautogui:
        raise RuntimeError("pyautogui not available")
    pyautogui.hotkey(*keys)
    time.sleep(0.1)


def move_to(x: int, y: int):
    """마우스 이동."""
    if not pyautogui:
        raise RuntimeError("pyautogui not available")
    pyautogui.moveTo(x, y)
