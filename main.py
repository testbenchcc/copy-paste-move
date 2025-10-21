#!/usr/bin/env python3
"""
CSV-driven UI input CLI for Windows

Features
- Declarative headers like: ctrl+a_1, ctrl+v_1, tab_1, click-100x1200_1, click_2, wait_1, ctrl+shift+d_1
- Per row values supply data for actions that need it:
    ctrl+v_k -> value to paste
    text_k   -> value to type
    tab_k    -> repeat count
    shift+tab_k -> repeat count
    enter_k  -> repeat count
    wait_k   -> milliseconds
    click_k  -> "XxY" or "X,Y"
- Fixed click coords in the header: click-100x1200_1
- Startup delay and per row delay
- Global hotkeys: Ctrl+Alt+P pause/resume, Ctrl+Alt+S stop
- Dry run mode prints planned actions

Dependencies
    pip install pyautogui keyboard pyperclip pygetwindow

Notes
- Run with a maximized TIA Portal window and your caret placed at the known starting field.
- pyautogui failsafe: shove mouse to top-left corner to abort.
"""

import argparse
import csv
import re
import sys
import time
import threading
from typing import Dict, List, Tuple, Optional

import pyautogui
import keyboard
import pyperclip

# Optional window control
try:
    import pygetwindow as gw
except Exception:
    gw = None

pyautogui.FAILSAFE = True

PAUSED = threading.Event()
STOP_REQUESTED = threading.Event()


def parse_args():
    p = argparse.ArgumentParser(description="CSV-driven UI input CLI")
    p.add_argument("csv_path", help="Path to CSV file")
    p.add_argument("--startup-delay", type=float, default=3.0, help="Seconds to wait before starting")
    p.add_argument("--row-delay", type=float, default=0.25, help="Seconds to wait between rows")
    p.add_argument("--action-delay", type=float, default=0.25, help="Seconds to wait between actions")
    p.add_argument("--window-title", default=None, help="Bring to front a window whose title contains this text")
    p.add_argument("--entry-mode", choices=["typing", "clipboard"], default="clipboard",
                   help="How to enter text for text_k columns")
    p.add_argument("--dry-run", action="store_true", help="Do not send any input, just print the plan")
    p.add_argument("--start-row", type=int, default=1, help="Start from this 1-based CSV row, including header on line 1")
    p.add_argument("--max-rows", type=int, default=0, help="If >0, process at most this many data rows")
    return p.parse_args()


# Header grammar
HEADER_RE = re.compile(r"""
    ^
    (?P<action>[a-z0-9\+\-]+)     # action token like ctrl+v, tab, click, click-100x1200
    (?:-(?P<fixparam>[^_]+))?     # optional fixed parameter, ex 100x1200
    _
    (?P<seq>\d+)
    $
""", re.VERBOSE | re.IGNORECASE)

# Coords grammar
COORDS_RE = re.compile(r"^\s*(?P<x>-?\d+)\s*(?:x|,)\s*(?P<y>-?\d+)\s*$", re.IGNORECASE)

# Actions that accept numeric repeat counts in the cell
REPEATABLE_KEYS = {"tab", "shift+tab", "enter", "wait"}

SINGLE_KEYS = {
    "esc",
    "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
    "home", "end", "pageup", "pagedown", "up", "down", "left", "right", "delete", "backspace", "space",
}


def install_hotkeys():
    def toggle_pause():
        if PAUSED.is_set():
            PAUSED.clear()
            print("[HOTKEY] Resuming")
        else:
            PAUSED.set()
            print("[HOTKEY] Paused. Press Ctrl+Alt+P to resume.")

    def request_stop():
        STOP_REQUESTED.set()
        print("[HOTKEY] Stop requested. Finishing current action and exiting.")

    keyboard.add_hotkey("ctrl+alt+p", toggle_pause)
    keyboard.add_hotkey("ctrl+alt+s", request_stop)


def bring_window_to_front(fragment: Optional[str]):
    if not fragment:
        return
    if gw is None:
        print("pygetwindow not available. Skipping window focus.")
        return
    matches = [w for w in gw.getAllTitles() if fragment.lower() in w.lower()]
    if not matches:
        print(f"Window title containing '{fragment}' not found.")
        return
    try:
        w = gw.getWindowsWithTitle(matches[0])[0]
        w.activate()
        time.sleep(0.3)
        print(f"Brought window to front: {w.title}")
    except Exception as e:
        print(f"Could not focus window: {e}")


def wait_if_paused_or_stopped():
    while PAUSED.is_set() and not STOP_REQUESTED.is_set():
        time.sleep(0.05)
    if STOP_REQUESTED.is_set():
        raise KeyboardInterrupt("Stop requested")


def parse_header(headers: List[str]) -> List[Dict]:
    parsed = []
    for h in headers:
        m = HEADER_RE.match(h.strip())
        if not m:
            raise ValueError(f"Bad header token: '{h}'. Expected like 'ctrl+v_1' or 'click-100x1200_2'")
        action = m.group("action").lower()
        fixparam = m.group("fixparam")
        seq = int(m.group("seq"))
        parsed.append({"raw": h, "action": action, "seq": seq, "fixparam": fixparam})
    # Keep original left-to-right order, csv reader preserves it
    return parsed


def parse_coords(text: str) -> Tuple[int, int]:
    m = COORDS_RE.match(text)
    if not m:
        raise ValueError(f"Bad coords: '{text}'. Use 'XxY' or 'X,Y'")
    return int(m.group("x")), int(m.group("y"))


def send_hotkey_combo(combo: str):
    # combo like 'ctrl+shift+d' or 'ctrl+a'
    keys = [k.strip() for k in combo.lower().split("+") if k.strip()]
    pyautogui.hotkey(*keys)


def press_key_repeated(key: str, count: int):
    count = max(0, count)
    for _ in range(count):
        pyautogui.press(key)


def paste_value(value: str, entry_mode: str):
    if value is None:
        value = ""
    if entry_mode == "typing":
        # Type directly
        pyautogui.typewrite(value, interval=0.0)
    else:
        # Clipboard mode: set clipboard then paste
        pyperclip.copy(value)
        pyautogui.hotkey("ctrl", "v")


def do_click(coords: Tuple[int, int], clicks: int = 1, button: str = "left"):
    x, y = coords
    pyautogui.click(x=x, y=y, clicks=clicks, button=button)


def do_clickrel(dx: int, dy: int, clicks: int = 1, button: str = "left"):
    x, y = pyautogui.position()
    pyautogui.click(x=x + dx, y=y + dy, clicks=clicks, button=button)


def run_action(token: Dict, cell_value: Optional[str], entry_mode: str, dry_run: bool, action_delay: float):
    action = token["action"]
    fixparam = token["fixparam"]

    def info(msg: str):
        print(f"  {token['raw']}: {msg}")

    wait_if_paused_or_stopped()

    # Normalize empty cell
    val = (cell_value or "").strip()

    # 1) Clicks
    if action in {"click", "doubleclick", "rightclick", "clickrel"}:
        clicks = 2 if action == "doubleclick" else 1
        button = "right" if action == "rightclick" else "left"

        if action == "clickrel":
            if fixparam:
                fx, fy = parse_coords(fixparam)
                dx, dy = fx, fy
            else:
                dx, dy = parse_coords(val)
            info(f"clickrel dx={dx}, dy={dy}, clicks={clicks}, button={button}")
            if not dry_run:
                do_clickrel(dx, dy, clicks=clicks, button=button)

        else:
            if fixparam:
                coords = parse_coords(fixparam)
            else:
                coords = parse_coords(val)
            info(f"click at {coords}, clicks={clicks}, button={button}")
            if not dry_run:
                do_click(coords, clicks=clicks, button=button)

    # 2) Wait
    elif action == "wait":
        ms = int(val) if val else 0
        info(f"wait {ms} ms")
        if not dry_run:
            time.sleep(ms / 1000.0)

    # 3) Tab and Shift+Tab
    elif action in {"tab", "shift+tab"}:
        n = int(val) if val else 1
        info(f"{action} x {n}")
        if not dry_run:
            for _ in range(n):
                if action == "tab":
                    pyautogui.press("tab")
                else:
                    pyautogui.hotkey("shift", "tab")

    # 4) Enter
    elif action == "enter":
        n = int(val) if val else 1
        info(f"enter x {n}")
        if not dry_run:
            press_key_repeated("enter", n)

    # 5) Raw text type
    elif action == "text":
        info(f"text len={len(val)}")
        if not dry_run:
            paste_value(val, entry_mode=entry_mode)

    # 6) Generic combos like ctrl+a, ctrl+v, ctrl+shift+d
    elif "ctrl" in action or "alt" in action or "shift" in action or action in SINGLE_KEYS:
        # Special case for ctrl+v: if the cell has a value, set clipboard first
        if action == "ctrl+v" and val:
            info(f"{action} with clipboard value len={len(val)}")
            if not dry_run:
                pyperclip.copy(val)
                send_hotkey_combo(action)
        else:
            info(f"{action}")
            if not dry_run:
                if "+" in action:
                    send_hotkey_combo(action)
                else:
                    pyautogui.press(action)

    else:
        info("skipped (unknown action)")
        return

    if not dry_run and action_delay > 0:
        time.sleep(action_delay)


def process_csv(
    csv_path: str,
    entry_mode: str,
    startup_delay: float,
    row_delay: float,
    action_delay: float,
    window_title: Optional[str],
    dry_run: bool,
    start_row: int,
    max_rows: int,
):
    print(f"CSV: {csv_path}")
    print(f"Startup delay: {startup_delay}s, Row delay: {row_delay}s, Action delay: {action_delay}s")
    print("Hotkeys: Ctrl+Alt+P pause/resume, Ctrl+Alt+S stop")
    if dry_run:
        print("Dry run: no input will be sent")

    bring_window_to_front(window_title)

    time.sleep(startup_delay)
    wait_if_paused_or_stopped()

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        print("Empty CSV")
        return

    def is_blank_row(r: List[str]) -> bool:
        return all(((c or "").strip() == "") for c in r)

    current_tokens: Optional[List[Dict]] = None
    section_idx = 0
    processed_count = 0

    for i, row in enumerate(rows, start=1):  # i is absolute CSV line number (1-based)
        # Reset section on blank row
        if is_blank_row(row):
            current_tokens = None
            continue

        # If no active header, try to parse this row as a header
        if current_tokens is None:
            try:
                hdr = [c for c in row if (c or "").strip() != ""]
                current_tokens = parse_header(hdr)
            except Exception as e:
                print(f"Line {i}: invalid header row: {e}")
                current_tokens = None
                continue
            section_idx += 1
            print(f"\nSection {section_idx} headers: {hdr}")
            continue

        # From here, it's a data row under the current header
        if STOP_REQUESTED.is_set():
            print("Stop requested. Exiting before next row.")
            break
        if i < max(1, start_row):
            # Respect start_row as absolute CSV line number, but keep tracking headers
            continue
        if max_rows and processed_count >= max_rows:
            print("Reached max-rows limit")
            break

        bring_window_to_front(window_title)

        print(f"\nRow {i}: {row}")
        # Pad or trim to header length
        if len(row) < len(current_tokens):
            row = row + [""] * (len(current_tokens) - len(row))
        elif len(row) > len(current_tokens):
            row = row[: len(current_tokens)]

        try:
            for token, cell in zip(current_tokens, row):
                run_action(token, cell, entry_mode, dry_run, action_delay)
        except KeyboardInterrupt:
            print("Interrupted. Stopping.")
            break
        except Exception as e:
            print(f"Row {i} error: {e}")
            # continue to next row

        processed_count += 1
        if not dry_run and row_delay > 0:
            time.sleep(row_delay)

    print("\nDone.")


def main():
    args = parse_args()
    install_hotkeys()
    try:
        process_csv(
            csv_path=args.csv_path,
            entry_mode=args.entry_mode,
            startup_delay=args.startup_delay,
            row_delay=args.row_delay,
            action_delay=args.action_delay,
            window_title=args.window_title,
            dry_run=args.dry_run,
            start_row=args.start_row,
            max_rows=args.max_rows,
        )
    finally:
        try:
            keyboard.clear_all_hotkeys()
        except Exception:
            pass


if __name__ == "__main__":
    main()
