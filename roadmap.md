# Roadmap

## Completed
- Add single-key support for `f1..f12`, navigation keys in `main.py`.
- Keep special `ctrl+v` clipboard behavior.
- Remove stray EOF token from `main.py`.
- Create and update `readme.md`.
- Support multi-section CSVs separated by a blank row in `main.py`; documented in `readme.md`.

## Next
- Validate F-keys across target apps (e.g., TIA Portal) and document any app-specific quirks.
- Add option to disable global hotkeys if needed for restricted environments.
- Add sample CSVs for common workflows.
- Add `--coords-mode` to support relative screen scaling or anchors.
"COMM_WRK".IO.DIM01_02.io.sts   DIM01_02c
## Testing
- Dry-run smoke test: `python main.py pasteData.csv --dry-run --max-rows 1`
- Live test on a focused window with caret in the correct starting field.
