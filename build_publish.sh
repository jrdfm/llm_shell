#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to extract version from pyproject.toml
get_version() {
    grep -E '^version\s*=\s*"(.*)"' pyproject.toml | sed -E 's/^version\s*=\s*"(.*)"/\1/'
}

echo "--- Build & Publish Script ---"

# 1. Check prerequisites
echo "Checking prerequisites..."
if ! command_exists python; then echo "Error: python not found." >&2; exit 1; fi
if ! command_exists pip; then echo "Error: pip not found." >&2; exit 1; fi
# Check if the python build module is runnable instead of checking for a command
if ! python -m build --version >/dev/null 2>&1; then 
echo "Error: python build module not found or unusable (pip install build)." >&2; exit 1; 
fi
if ! command_exists twine; then echo "Error: twine not found (pip install twine)." >&2; exit 1; fi
if [ ! -f pyproject.toml ]; then echo "Error: pyproject.toml not found in current directory." >&2; exit 1; fi
echo "Prerequisites check passed."

# 2. Confirm Version
VERSION=$(get_version)
if [ -z "$VERSION" ]; then
    echo "Error: Could not extract version from pyproject.toml." >&2
    exit 1
fi

read -p "Current version in pyproject.toml is: $VERSION. Is this correct for release? (y/N) " -n 1 -r
echo # Move to a new line
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Aborting. Please update the version in pyproject.toml." >&2
    exit 1
fi

# 3. Clean previous builds
echo "
Cleaning previous build artifacts..."
rm -rf dist/ build/ shell_llm.egg-info/ core.cpython-*.so wheelhouse/
echo "Clean complete."

# 4. Build sdist and platform wheel
echo "
Building source distribution (sdist) and platform wheel..."
python -m build
DIST_FILES=("dist"/*)
if [ ${#DIST_FILES[@]} -eq 0 ]; then
    echo "Error: No distribution files found in dist/ after build." >&2
    exit 1
fi
echo "Build complete. Files in dist/:"
ls -l dist/

# 5. Build manylinux wheels (Optional)
WHEEL_UPLOAD_DIR="dist"
if command_exists cibuildwheel; then
    read -p "Found cibuildwheel. Build manylinux wheels using Docker? (Requires Docker running) (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]
    then
        echo "
Building manylinux wheels with cibuildwheel..."
        # Add options as needed, e.g., --platform linux --arch x86_64
        cibuildwheel --platform linux --output-dir wheelhouse
        if [ -d "wheelhouse" ] && [ "$(ls -A wheelhouse)" ]; then
             echo "Manylinux wheels built successfully in wheelhouse/."
             WHEEL_UPLOAD_DIR="wheelhouse"
             ls -l wheelhouse/
        else
             echo "Warning: cibuildwheel ran but wheelhouse/ directory is empty or missing. Uploading platform wheel from dist/ instead." >&2
        fi
    else
        echo "Skipping manylinux wheel build."
    fi
else
    echo "cibuildwheel not found. Skipping manylinux wheel build (will only upload platform wheel from dist/)."
fi

# 6. Confirm Upload
echo "
Ready to upload to PyPI:"
echo "  Source Dist: dist/*.tar.gz"
echo "  Wheels from: $WHEEL_UPLOAD_DIR/*.whl"
read -p "Proceed with upload? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Upload aborted by user." >&2
    exit 1
fi

# 7. Upload
echo "
Uploading source distribution..."
twine upload dist/*.tar.gz

echo "
Uploading wheels..."
twine upload "$WHEEL_UPLOAD_DIR"/*.whl

echo "
--- Upload to PyPI Finished Successfully ---"

exit 0 