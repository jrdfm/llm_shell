# Build, Upload, and Setup Instructions for shell-llm

This document provides instructions for developers contributing to `shell-llm` and for users setting up the tool after installation.

## For Developers: Building and Uploading to PyPI

These steps assume you have Python, pip, and Docker installed and running. It's highly recommended to work within a Python virtual environment.

1.  **Activate Virtual Environment:**
    ```bash
    source venv/bin/activate # Or your venv activation command
    ```

2.  **Install/Update Build Tools:**
    ```bash
    pip install --upgrade build twine cibuildwheel
    ```

3.  **Increment Version Number:**
    Before uploading a new version, **edit the `version` field** in the `[project]` section of `pyproject.toml`:
    ```toml
    # pyproject.toml
    [project]
    name = "shell-llm"
    version = "0.1.3" # <-- Increment this number
    # ... rest of file
    ```

4.  **Build Source Distribution (.tar.gz):**
    This creates the source tarball in the `dist/` directory.
    ```bash
    python -m build
    ```
    *(This will also create a `.whl` file in `dist/`, but it likely has an incompatible platform tag for PyPI if built directly on your development machine/WSL).*

5.  **Build Compatible Linux Wheels (.whl) (Recommended):**
    Since this package contains a compiled C extension, you need to build wheels in a standardized `manylinux` environment using Docker. This ensures compatibility across different Linux distributions.
    ```bash
    # Ensure Docker daemon is running
    cibuildwheel --platform linux
    ```
    This command builds wheels for various Python versions inside Docker containers and places the compatible `.whl` files in the `wheelhouse/` directory.

6.  **Upload to PyPI:**
    Upload both the source distribution (`.tar.gz` from `dist/`) and the compatible `manylinux` wheels (`.whl` from `wheelhouse/`).
    ```bash
    # Make sure filenames match your build output (especially version)
    twine upload dist/shell_llm-0.1.3.tar.gz wheelhouse/*.whl
    ```
    *   You will be prompted for your PyPI username and password.
    *   **Security Recommendation:** Use a PyPI API token. Enter `__token__` as the username and the token value as the password.

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