#!/bin/bash
set -e

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log "Creating Python virtual environment"
python -m venv venv
source venv/bin/activate

log "Upgrading pip"
pip install --upgrade pip

log "Installing wheel and setuptools"
pip install wheel setuptools

# Read requirements line by line
log "Installing requirements individually with verbose output"
while IFS= read -r line || [[ -n "$line" ]]; do
    # Skip comments and empty lines
    [[ $line =~ ^#.*$ ]] && continue
    [[ -z $line ]] && continue
    
    log "Installing: $line"
    pip install -v "$line"
    if [ $? -eq 0 ]; then
        log "✅ Successfully installed $line"
    else
        log "❌ Failed to install $line"
        exit 1
    fi
done < requirements.txt

log "Validating installation"
pip freeze

log "All packages installed successfully"
