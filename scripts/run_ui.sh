#!/bin/bash
# Script to run Streamlit UI in the background

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$REPO_DIR"

if [ -d "venv312" ]; then
    source venv312/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

if pgrep -f "streamlit run scripts/ui.py" > /dev/null; then
    echo "Streamlit is already running!"
    echo "To stop it, run: scripts/stop_ui.sh"
    echo "Or kill it manually: pkill -f 'streamlit run scripts/ui.py'"
    exit 1
fi

echo "Starting Streamlit UI in the background..."
echo "The UI will be available at http://localhost:8501"
echo ""
echo "To view logs: tail -f streamlit.log"
echo "To stop: scripts/stop_ui.sh"
echo ""

nohup streamlit run scripts/ui.py > streamlit.log 2>&1 &
echo $! > streamlit.pid

echo "Streamlit started with PID: $(cat streamlit.pid)"
echo "Check streamlit.log for output"



