#!/bin/bash
# Script to run Streamlit UI in the background

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "venv312" ]; then
    source venv312/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Check if Streamlit is already running
if pgrep -f "streamlit run scripts/ui.py" > /dev/null; then
    echo "Streamlit is already running!"
    echo "To stop it, run: ./stop_ui.sh"
    echo "Or kill it manually: pkill -f 'streamlit run scripts/ui.py'"
    exit 1
fi

# Run Streamlit in the background
echo "Starting Streamlit UI in the background..."
echo "The UI will be available at http://localhost:8501"
echo ""
echo "To view logs: tail -f streamlit.log"
echo "To stop: ./stop_ui.sh or pkill -f 'streamlit run scripts/ui.py'"
echo ""

# Run with nohup so it persists after terminal closes
nohup streamlit run scripts/ui.py > streamlit.log 2>&1 &

# Save the PID
echo $! > streamlit.pid

echo "Streamlit started with PID: $(cat streamlit.pid)"
echo "Check streamlit.log for output"



