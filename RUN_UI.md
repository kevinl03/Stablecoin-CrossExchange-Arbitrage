# Running Streamlit UI - Background Process Guide

## Quick Start (Recommended)

### Option 1: Use the Helper Scripts

**Start the UI:**
```bash
./run_ui.sh
```

**Stop the UI:**
```bash
./stop_ui.sh
```

**View logs:**
```bash
tail -f streamlit.log
```

The UI will be available at `http://localhost:8501` and will continue running even after you close your terminal.

---

## Alternative Methods

### Option 2: Run in Background with `&`

```bash
# Start
streamlit run scripts/ui.py > streamlit.log 2>&1 &

# Stop (find the PID first)
ps aux | grep "streamlit run"
kill <PID>

# Or stop by name
pkill -f "streamlit run scripts/ui.py"
```

### Option 3: Use `screen` (Persistent Terminal Session)

```bash
# Install screen if needed (macOS)
brew install screen

# Start a screen session
screen -S streamlit

# Inside screen, run:
streamlit run scripts/ui.py

# Detach from screen: Press Ctrl+A, then D
# Reattach: screen -r streamlit
# Kill: screen -X -S streamlit quit
```

### Option 4: Use `tmux` (Modern Alternative to screen)

```bash
# Install tmux if needed (macOS)
brew install tmux

# Start a tmux session
tmux new -s streamlit

# Inside tmux, run:
streamlit run scripts/ui.py

# Detach: Press Ctrl+B, then D
# Reattach: tmux attach -t streamlit
# Kill: tmux kill-session -t streamlit
```

### Option 5: Run Normally (Foreground)

If you just want to run it normally and stop with Ctrl+C:

```bash
streamlit run scripts/ui.py
```

Press `Ctrl+C` to stop when you're done.

---

## Troubleshooting

**Port already in use?**
```bash
# Find what's using port 8501
lsof -i :8501

# Kill it
kill -9 <PID>
```

**Streamlit won't stop?**
```bash
# Force kill all Streamlit processes
pkill -9 -f streamlit
```

**Check if it's running:**
```bash
pgrep -f "streamlit run scripts/ui.py"
```

---

## Notes

- The helper scripts (`run_ui.sh` and `stop_ui.sh`) automatically detect and activate your virtual environment
- Logs are saved to `streamlit.log` when using the helper scripts
- The UI takes about 1 minute to load initially as it fetches live market data
- The process will persist even if you close your terminal when using `nohup` or `screen`/`tmux`



