#!/bin/bash
set -e

echo "Cleaning up root directory before packaging..."

# Remove any pycache directories
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type d -name "*.egg-info" -exec rm -rf {} +

# Remove build artifacts
rm -rf build/ dist/

# Remove temporary and backup files
rm -f *.pyc *.pyo *~ \#*\# .\#* *.bak *.tmp *.swp

# Remove unnecessary files created during development
rm -f setup.py.new
rm -f update_and_publish.sh

# Remove old build files if they exist
rm -f core.*.so

# Edit setup.py to point to the correct entry point
sed -i 's/shell-llm=__main__:main/shell-llm=shell:main/g' setup.py

echo "Directory cleaned. Ready for building and uploading!"
echo
echo "To build and upload, run:"
echo "python -m build"
echo "twine upload dist/*" 