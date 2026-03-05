#!/bin/bash
# runner.sh - Continuous runner for CLIPPER
# Runs in a loop: sync from GitHub, process one job, wait, repeat

# Configuration
CLIPPER_HOME="${CLIPPER_HOME:-$HOME/clipper}"
VENV_PATH="${VENV_PATH:-$HOME/yt-env}"
SYNC_INTERVAL="${SYNC_INTERVAL:-300}"  # 5 minutes between cycles
PROCESS_INTERVAL="${PROCESS_INTERVAL:-60}"  # 1 minute between jobs

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}CLIPPER Runner Starting...${NC}"
echo "CLIPPER_HOME: $CLIPPER_HOME"
echo "Sync interval: ${SYNC_INTERVAL}s"
echo "Process interval: ${PROCESS_INTERVAL}s"

# Check if virtualenv exists
if [ ! -d "$VENV_PATH" ]; then
    echo -e "${RED}Virtualenv not found at $VENV_PATH${NC}"
    echo "Please create virtualenv: python3 -m venv $VENV_PATH"
    exit 1
fi

# Activate virtualenv
source "$VENV_PATH/bin/activate"

# Ensure we're in the right directory
cd "$CLIPPER_HOME"

# Create required directories
mkdir -p data backups raw transcript rendered logs

# Trap to handle shutdown
cleanup() {
    echo -e "${YELLOW}Shutting down CLIPPER runner...${NC}"
    exit 0
}
trap cleanup SIGINT SIGTERM

# Main loop
while true; do
    echo "========================================"
    echo "$(date): Starting cycle..."
    
    # Sync from GitHub
    echo "$(date): Syncing from GitHub..."
    python backend/github_sync.py
    SYNC_RESULT=$?
    
    if [ $SYNC_RESULT -eq 0 ]; then
        echo -e "${GREEN}Sync completed successfully${NC}"
    else
        echo -e "${RED}Sync failed with code $SYNC_RESULT${NC}"
    fi
    
    # Process one job
    echo "$(date): Processing job..."
    python backend/process.py
    PROCESS_RESULT=$?
    
    if [ $PROCESS_RESULT -eq 0 ]; then
        echo -e "${GREEN}Job processed${NC}"
    else
        echo -e "${RED}Job processing failed with code $PROCESS_RESULT${NC}"
    fi
    
    echo "$(date): Cycle complete. Sleeping for ${SYNC_INTERVAL} seconds..."
    sleep "$SYNC_INTERVAL"
done
