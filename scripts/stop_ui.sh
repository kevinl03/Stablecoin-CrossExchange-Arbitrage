#!/bin/bash
# Script to stop the Streamlit UI

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$REPO_DIR"

if [ -f "streamlit.pid" ]; then
    PID=$(cat streamlit.pid)
    if ps -p $PID > /dev/null 2>&1; then
        echo "Stopping Streamlit (PID: $PID)..."
        kill $PID
        rm streamlit.pid
        echo "Streamlit stopped."
        exit 0
    else
        echo "PID file exists but process is not running. Cleaning up..."
        rm streamlit.pid
    fi
fi

if pgrep -f "streamlit run scripts/ui.py" > /dev/null; then
    echo "Stopping Streamlit by process name..."
    pkill -f "streamlit run scripts/ui.py"
    echo "Streamlit stopped."
else
    echo "Streamlit is not running."
fi



