#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

echo "--- Local Build & Test Script ---"

# 1. Check for prerequisites
echo "Checking prerequisites..."
if ! command_exists pip; then
    echo "Error: pip is not installed or not in PATH." >&2
    exit 1
fi
if ! command_exists pytest; then
    echo "Warning: pytest not found. Skipping tests." >&2
    # Consider installing it: pip install pytest pytest-asyncio pytest-mock
    # exit 1 # Or exit if tests are mandatory
fi

echo "Prerequisites check passed."

# 2. Build C Extension and Install Locally
# Using `pip install .` handles the build process automatically.
# `--force-reinstall` ensures the latest code is used.
echo "
Building C extension and installing package locally..."
pip install . --force-reinstall

echo "Build and local installation complete."

# 3. Run Tests (if pytest is available)
if command_exists pytest; then
    echo "
Running tests..."
    
    echo "
Running core unit tests (test_core.py)..."
    pytest test_core.py
    
    echo "
Running shell integration tests (test_shell_integration.py)..."
    pytest test_shell_integration.py
    
    echo "Tests finished."
else
    echo "
Skipping tests because pytest was not found."
fi

echo "
--- Local Build & Test Finished Successfully ---"

exit 0 