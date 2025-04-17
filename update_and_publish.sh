#!/bin/bash
set -e

# Update the setup.py file with correct entry point
echo "Updating setup.py..."
cat setup.py.new > setup.py

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Create and activate virtual environment if needed
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv build_env
    source build_env/bin/activate
    pip install build twine
fi

# Build the package
echo "Building package..."
python -m build

# Display instructions
echo "Build complete! To upload to PyPI:"
echo "twine upload dist/*"
echo
echo "After uploading, users can install with:"
echo "pip install shell-llm"
echo
echo "And run with the command:"
echo "shell-llm" 