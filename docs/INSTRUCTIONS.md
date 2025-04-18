# Build, Test, Upload, and Setup Instructions for shell-llm

This document provides instructions for developers contributing to `shell-llm` and for users setting up the tool after installation.

## For Developers

These steps assume you have Python, pip, and optionally Docker installed and running. It's highly recommended to work within a Python virtual environment.

### 1. Environment Setup

```bash
# Create and activate a virtual environment (if not already done)
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install build twine cibuildwheel pytest pytest-asyncio pytest-mock
```

### 2. Building the C Extension (Locally)

After making changes to the C code (`core/shell.c`, `core/shell_python.c`) or Python code, you need to rebuild the C extension module.

*   **Recommended Method (using `build`):**
    This command builds the package and places the compiled extension (`.so`/`.pyd`) inside the source tree, allowing you to run tests directly.
    ```bash
    python -m build --wheel --outdir . --no-isolation
    # Or build and install into the venv:
    # pip install . --force-reinstall
    ```
    *Note: Building without `--no-isolation` using `python -m build` is preferred for creating distributable packages (see step 5), but the above is often convenient for local development and testing.*

### 3. Running Tests

We use `pytest` for testing.

*   **Unit Tests (C Core Interface):** These tests verify the Python interface to the C extension (`test_core.py`).
    ```bash
    pytest test_core.py
    ```
*   **Integration Tests (Shell Logic):** These tests verify the main shell logic in `shell.py`, including command handling and interaction with the core module (`test_shell_integration.py`). They use `pytest-asyncio` and `pytest-mock`.
    ```bash
    pytest test_shell_integration.py
    ```
*   **Run All Tests:**
    ```bash
    pytest
    ```

### 3.5. Building and Testing a Local Install (Simulating User Install)

This simulates the actual user installation process from built artifacts and helps catch packaging issues.

```bash
# Optional: Clean old builds
# rm -rf dist/ build/ shell_llm.egg-info/ core.cpython-*.so

# Build using the modern method (creates sdist and wheel in dist/)
python -m build

# Uninstall any old version (if present)
pip uninstall shell-llm -y

# Install the newly built wheel (replace * with actual version/tags)
pip install dist/shell_llm-*.whl

# Run tests against the installed package
pytest test_core.py
pytest test_shell_integration.py

# You can also manually run the installed command
# shell-llm
```

### 4. Incrementing Version Number

Before creating distributable packages for a new release, **edit the `version` field** in the `[project]` section of `pyproject.toml`:

```toml
# pyproject.toml
[project]
name = "shell-llm"
version = "0.1.7" # <-- Increment this number
# ... rest of file
```

*   **Note:** The version number is **only** set in `pyproject.toml`. The `setup.py` file reads the version from there.

### 5. Building Distributable Packages (sdist and wheels)

*   **Clean previous builds (optional but recommended):**
    ```bash
    rm -rf dist/ build/ shell_llm.egg-info/ core.cpython-*.so wheelhouse/
    ```
*   **Build sdist and wheel using `build`:**
    This creates the source tarball (`.tar.gz`) and a platform-specific wheel (`.whl`) in the `dist/` directory.
    ```bash
    python -m build
    ```
*   **Build Compatible Linux Wheels (`manylinux`) (Recommended for PyPI):**
    Since this package contains a compiled C extension, you should build wheels in a standardized `manylinux` environment using Docker via `cibuildwheel`. This ensures compatibility across different Linux distributions.
    ```bash
    # Ensure Docker daemon is running
    cibuildwheel --platform linux
    ```
    This command builds wheels for various Python versions inside Docker containers and places the compatible `.whl` files in the `wheelhouse/` directory.

### 6. Uploading to PyPI

Upload the source distribution (`.tar.gz` from `dist/`) and the compatible `manylinux` wheels (`.whl` from `wheelhouse/`).

```bash
# Upload sdist first
twine upload dist/*.tar.gz

# Upload compatible wheels
twine upload wheelhouse/*.whl
```

*   You will be prompted for your PyPI username and password.
*   **Security Recommendation:** Use a PyPI API token. Enter `__token__` as the username and the token value as the password.

### Important Note on Parsing

Command parsing (handling quotes, escapes, whitespace) is now performed in Python within `shell.py` using the `shlex` module *before* commands are sent to the C extension (`core.Shell`). The C extension methods (`execute`, `execute_pipeline`) now expect pre-parsed lists of arguments.

## For Users: Post-Installation Setup

After installing the package using `pip install shell-llm`, you might need to perform these steps:

1.  **Add Google API Key:**
    The application needs a Google Generative AI API key to function. You need to set the `GOOGLE_API_KEY` environment variable. The recommended way is to create a `.env` file in your home directory or the directory where you run `shell-llm`:
    ```
    # Example ~/.env file content:
    GOOGLE_API_KEY="YOUR_ACTUAL_API_KEY_HERE"
    ```
    The application should automatically load this variable if you have `python-dotenv` installed (which is included as a dependency). Alternatively, you can set the environment variable directly in your shell configuration (e.g., `.bashrc`, `.zshrc`):
    ```bash
    export GOOGLE_API_KEY="YOUR_ACTUAL_API_KEY_HERE"
    ```
    *(Remember to restart your shell or source the file after editing)*

2.  **Ensure Command is in PATH:**
    When pip installs a package with console scripts like `shell-llm`, it places the executable file in a specific directory. Your shell needs to know where to find this directory to run the command directly.
    *   **If installed globally or using `--user`:** The script is often placed in `~/.local/bin` on Linux/macOS. Check if this directory is in your `PATH` environment variable.
        ```bash
        echo $PATH
        ```
        If `~/.local/bin` (or the equivalent for your OS) is missing, add it to your shell configuration file (e.g., `~/.bashrc` or `~/.zshrc`):
        ```bash
        # Add this line to ~/.bashrc or ~/.zshrc
        export PATH="$HOME/.local/bin:$PATH"
        ```
        *(Restart your shell or run `source ~/.bashrc` / `source ~/.zshrc` afterwards)*
    *   **If installed in a Virtual Environment:** Activating the virtual environment (e.g., `source venv/bin/activate`) automatically adds the correct `bin` directory to your `PATH` for the current shell session. The `shell-llm` command should work as long as the venv is active.

Once the API key is set and the command is in your `PATH`, you should be able to run the application simply by typing:
```bash
shell-llm
``` 