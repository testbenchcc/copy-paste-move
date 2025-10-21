        # copy-past-move

CSV-driven UI input CLI for Windows. Automates typing, hotkeys, and clicks in another application using a CSV that declares actions.

## Features
- **Declarative headers** like `ctrl+a_1`, `ctrl+v_1`, `text_1`, `tab_1`, `click-100x1200_1`, `click_1`, `wait_1`, `ctrl+shift+d_1`, `f9_1`.
- **Per-row values** supply data for actions that need it:
  - **`ctrl+v_k`**: optional value to place on clipboard before paste
  - **`text_k`**: value to type/paste
  - **`tab_k`, `shift+tab_k`, `enter_k`**: repeat counts
  - **`wait_k`**: milliseconds
  - **`click_k`**: coordinates `XxY` or `X,Y`
- **Fixed click coords** directly in header: `click-100x1200_1`
- **Global hotkeys**: `Ctrl+Alt+P` pause/resume, `Ctrl+Alt+S` stop
- **Dry run** mode prints planned actions without sending input
- **F-keys support**: Single-key presses including `f1`–`f12`, `esc`, arrows, navigation keys
- **Multi-section CSVs**: Multiple header+data sections in one file separated by a blank row. Each section must start with a header row.

## Requirements
- Windows, Python 3.9+
- Install dependencies:
```
python -m pip install -r requirements.txt
```

## Usage
Run against a CSV (see example in `pasteData.csv`):
```
python main.py pasteData.csv \
  --startup-delay 3 \
  --row-delay 0.25 \
  --action-delay 0.25 \
  --entry-mode clipboard \
  --window-title "TIA Portal"
```

Common options:
- `--entry-mode typing|clipboard` how `text_k` is entered
- `--dry-run` prints the plan only
- `--start-row N` first 1-based CSV line to process (line 1 is the first line of the file, across all sections)
- `--max-rows N` limit number of data rows

## CSV Header Grammar
Each column header uses: `action[_fixparam]_seq`, e.g.:
- `ctrl+a_1`, `ctrl+shift+d_2`, `esc_3`, `f9_4`
- `text_1`
- `tab_1`, `shift+tab_1`, `enter_1`
- `wait_1`
- `click-100x1200_1` (fixed coords)
- `click_1` (coords in cell, e.g. `100x1200`)

Notes:
- `ctrl+v_k` with a cell value sets clipboard first, then pastes.
- Single-key actions supported: `f1..f12`, `esc`, `home`, `end`, `pageup`, `pagedown`, `up/down/left/right`, `delete`, `backspace`, `space`.

## Multi-section CSVs
Multiple header+data sections in a single CSV are supported. Separate sections with a single blank row. Each section must begin with a header row. Example:
```csv
ctrl+a_1,text_1,tab_1
value1,,1

ctrl+a_1,text_1,enter_1
value2,,
```
- `--start-row N` refers to the absolute CSV line number across the whole file (line 1 is the first line of the file).
- `--max-rows N` limits the total number of data rows processed across all sections.

## Hotkeys and Safety
- Pause/resume: `Ctrl+Alt+P`
- Stop: `Ctrl+Alt+S`
- PyAutoGUI failsafe: move mouse to top-left corner to abort instantly.

If global hotkeys don’t trigger on your system, try running the terminal as Administrator (Windows) due to the `keyboard` library.

## Example
A header like:
```
ctrl+a_1,text_1,tab_1,text_2,tab_2,text_3,tab_3,ctrl+r_1,f9_1,shift+tab_1
```
Means each row will: select all, paste text1, tab, paste text2, tab, paste text3, tab, press Ctrl+R, press F9, Shift+Tab.

## Changelog
- 2025-10-21: Add single-key support (`f1..f12`, navigation keys). Remove stray token at EOF in `main.py`.
- 2025-10-21: Support multi-section CSVs separated by a blank row.
