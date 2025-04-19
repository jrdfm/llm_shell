#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
RESET='\033[0m' # Reset color

# Function to echo in red color
echo_red() {
    echo -e "${RED}$1${RESET}"
}

echo_green() {
    echo -e "${GREEN}$1${RESET}"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo_red "--- Local Build & Test Script ---"

# 1. Check for prerequisites
echo_red "Checking prerequisites..."
if ! command_exists pip; then
    echo_red "Error: pip is not installed or not in PATH." >&2
    exit 1
fi
if ! command_exists pytest; then
    echo_red "Warning: pytest not found. Skipping tests." >&2
    # Consider installing it: pip install pytest pytest-asyncio pytest-mock
    # exit 1 # Or exit if tests are mandatory
fi

echo_red "Prerequisites check passed."

# 2. Build C Extension and Install Locally
# Using `pip install .` handles the build process automatically.
# `--force-reinstall` ensures the latest code is used.
echo_red "
Building C extension and installing package locally..."
pip install . --force-reinstall

echo_red "Build and local installation complete."

# 3. Run Tests (if pytest is available)
if command_exists pytest; then
    echo_red "
Running tests..."
    
    echo_red "
Running core unit tests (test_core.py)..."
    pytest test_core.py
    
    echo_red "
Running shell integration tests (test_shell_integration.py)..."
    pytest test_shell_integration.py
    
    echo_red "Tests finished."
else
    echo_red "
Skipping tests because pytest was not found."
fi

echo_green "
--- Local Build & Test Finished Successfully ---"

exit 0 