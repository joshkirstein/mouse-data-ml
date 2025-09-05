Mouse Trajectory Capture

Simple desktop app to capture mouse movement trajectories while clicking red dots. Each time you click the red dot, a new one appears at a random location. The path you moved to reach the dot is recorded and appended to a JSONL file on disk.

Quick start

- Option A — Desktop (Tkinter): `python capture_mouse.py`
  - Requires a working Tk/Tcl on your Python build. If you hit a macOS/Tk error, use the web version below.
- Option B — Web (no dependencies):
  - Run the local server: `python web_capture/server.py`
  - Capture: open http://127.0.0.1:8000 in your browser
  - Visualize: open http://127.0.0.1:8000/visualize (choose a session, play/pause, next/prev)

Controls

- Move the mouse and click the red dot.
- Press `Q` to quit.
  - Web version: press `R` to reset trials.

Output

- Desktop: `data/session_YYYYMMDD_HHMMSS.jsonl`.
- Web: `data/session_<uuid>.jsonl` (fixed 750x550 canvas).
- Each line is a JSON object with fields:
  - `session`: session identifier (timestamp-based)
  - `trial`: 1-based trial counter
  - `timestamp`: wall-clock time when the trial was saved
  - `window`: `{width, height}`
  - `target`: `{x, y, radius}` center and size of the red dot
  - `path`: list of samples captured during the trial
    - Each sample: `{t, x, y}`; the final click sample also includes `click: true`
    - `t` is seconds since the trial started (high-resolution monotonic clock).

Notes

- Window size is fixed at 800x600 by default; adjust in `capture_mouse.py` if desired.
- Missed clicks (outside the dot) are ignored and do not advance the trial.
- Data is appended after every successful click; safe to terminate at any time.

Visualization (web)

- Visit `http://127.0.0.1:8000/visualize` while the server is running.
- Use the session dropdown to pick a file in `data/`.
- Controls: Prev, Play/Pause, Next; playback speeds 0.5x/1x/2x/4x.
- The canvas automatically uses the recorded `window.width/height` per trial.

Analysis (Jupyter)

- Notebook: `analyze/trajectory_analysis.ipynb`
- Opens and analyzes a selected `data/session_*.jsonl` file.
- Plots: overlaid centered trajectories, speed profile over normalized time, and distributions for efficiency, movement time, peak speed, path length, and normalized jerk (smoothness).
- Requirements: `numpy`, `pandas`, `matplotlib`, `seaborn`.
- Virtual env (created): `.venv` in repo root.
  - Activate: `source .venv/bin/activate` (macOS/Linux)
  - Deactivate: `deactivate`
- Launch:
  - `source .venv/bin/activate && jupyter lab`
  - In Jupyter, choose kernel: `Python (mouse-data)`

Training (neural generator)

- Notebook: `training/train_human_like_trajectories.ipynb`
- Goal: train a small GRU to predict next (x,y) in a normalized frame and then generate 100 trajectories toward random targets on the 750x550 canvas.
- Data: consumes all `data/session_*.jsonl` files.
- Preprocess: translate→rotate→scale so start=(0,0), target=(1,0); resample to fixed 64 steps.
- Requirements: `torch`.
- Setup:
  - `source .venv/bin/activate`
  - `pip install -r training/requirements.txt`
  - `jupyter lab` and open the notebook.
- Checkpoints:
  - After training, the notebook saves `training/checkpoints/last.pt`.
  - You can set `LOAD = 'last'` (or provide a path) in the "Optional: load checkpoint" cell to restore weights before generation.

Troubleshooting

- If Tkinter fails on macOS with a message about the macOS version or Tk requirements, use the web version (`python web_capture/server.py`) which runs in your browser, uses a fixed 750x550 window, and has no external dependencies.
