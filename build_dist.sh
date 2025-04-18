#!/bin/bash
set -e

# Create and use a virtual environment if not already in one
if [ -z "$VIRTUAL_ENV" ]; then
    echo "Creating a virtual environment for building..."
    python3 -m venv build_env
    source build_env/bin/activate
    pip install build twine
fi

# Clean previous builds
rm -rf dist/ build/ *.egg-info/

# Build using PEP 517
python -m build

echo "Build complete. Distribution files are in dist/ directory."
echo
echo "To test the wheel in a virtual environment:"
echo "python -m venv test_env"
echo "source test_env/bin/activate"
echo "pip install dist/*.whl"
echo "shell-llm"
echo
echo "To upload to PyPI, run:"
echo "twine upload dist/*"