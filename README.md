# LLM Shell Assistant

An intelligent shell that combines traditional shell capabilities with natural language processing. Features include command generation from natural language, automatic error explanations, and command completion.

## Prerequisites

- Python 3.8 or higher
- A Google API key for Gemini AI (the specific model used can be configured, check `llm.py`)
- GCC compiler (for the C core extension)

## Setup

### Method 1: Install from PyPI (Recommended)

Install directly using pip:
```bash
pip install shell-llm
```

Set up your Google API key (see "Post-Installation Setup" below).

### Method 2: Install from Source (for Development)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/jrdfm/shell-llm.git # Update URL if needed
    cd shell-llm
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3.  **Install dependencies (including build/test tools):**
    ```bash
    pip install -r requirements.txt
    pip install build twine cibuildwheel pytest pytest-asyncio pytest-mock
    ```

4.  **Build the C extension:**
    ```bash
    # Build the C extension module and place it in the source tree
    python -m build --wheel --outdir . --no-isolation
    # Or build and install into the venv (needed to run `shell-llm` command directly)
    # pip install . --force-reinstall
    ```

5.  **Set up your Google API key** (see "Post-Installation Setup" below).

## Running the Shell

1.  **Activate Virtual Environment** (if installed from source):
    ```bash
    source venv/bin/activate
    ```

2.  **Run:**
    ```bash
    shell-llm
    ```

## Usage

-   **Standard Shell Commands:** Most standard shell commands work as expected. Pipelines (`|`) are supported. **Note:** Redirection (`>`, `<`, `>>`, etc.) is **not** currently implemented by the shell wrapper; these characters will likely be treated as literal arguments by commands.
-   **Natural Language Queries:** Start your query with `#`.
    ```bash
    # how do I find large files?
    ```
-   **Verbosity Flags (for NL Queries):** Add `-v` or `-vv` after `#` for more detailed explanations of the generated command.
    ```bash
    # -v list files sorted by size
    # -vv copy files securely between servers
    ```
-   **Exit:** Type `exit` or press `Ctrl+D`.

## Features

*   **Natural Language to Command:** Generate shell commands from plain English.
*   **Command Execution:** Executes commands using a performant C core extension.
*   **Pipeline Support:** Handles command pipelines (`cmd1 | cmd2`).
*   **AI-Powered Error Explanations:** Captures stderr and exit codes, providing explanations and potential solutions using an LLM.
*   **Command History:** Persistent history across sessions (`~/.llm_shell_history`).
*   **Auto-Suggestion:** Suggests commands based on history.
*   **(Experimental) Command Completion:** Basic file/directory completion.

## Technical Implementation

### Architecture Overview

The project uses a hybrid architecture:

1.  **Core Shell Logic (`core/shell.c`)**: Written in C for executing commands and pipelines efficiently using `fork`, `execvp`, `pipe`, and `waitpid`. Manages the shell's internal state (CWD, environment variables, last exit code). Exposed to Python via CPython API bindings.
2.  **CPython Wrapper (`core/shell_python.c`)**: Provides the Python interface (`core.Shell` class) to the C functions using the CPython API. Handles type conversions (e.g., Python lists to C `argv` arrays) and memory management for interacting with the C layer.
3.  **Python Shell Interface (`shell.py`)**: The main interactive loop using `prompt_toolkit`. Handles user input, calls the `core.Shell` extension for execution, manages history and completions, and orchestrates LLM interactions.
4.  **Command Parsing (`shell.py`)**: User input strings are parsed into argument lists using Python's standard `shlex` module *before* being passed to the C extension. This ensures correct handling of quotes and escapes according to POSIX shell rules.
5.  **LLM Integration (`llm.py`)**: Manages communication with the Google Generative AI API (Gemini) for natural language command generation and error explanation.
6.  **Supporting Modules**: `completions.py`, `formatters.py`, `error_handler.py`, `ui.py`, `models.py`, `utils.py` provide specific functionalities.

For more in-depth details on the C core and Python wrapper implementation, please see [docs/TECHNICAL_DETAILS.md](docs/TECHNICAL_DETAILS.md).

### Build System

*   The project uses `setuptools` as the build backend, configured primarily via `pyproject.toml`.
*   `setup.py` exists mainly to define the C extension module (`core`).
*   Dependencies and project metadata (like version) are defined in `pyproject.toml`.
*   The standard `python -m build` command is used to create source distributions and wheels.
*   `cibuildwheel` is recommended for building cross-platform compatible Linux wheels for PyPI distribution.

### Testing

*   **Unit Tests (`test_core.py`):** Use `pytest` to test the Python interface (`core.Shell`) provided by the C extension. Ensures the C functions behave as expected when called from Python with pre-parsed arguments.
*   **Integration Tests (`test_shell_integration.py`):** Use `pytest`, `pytest-asyncio`, and `pytest-mock` to test the main `LLMShell` class in `shell.py`. These tests verify the interaction between the Python shell logic (including `shlex` parsing) and the C core, as well as error handling pathways.

## Contributing

Please refer to [`INSTRUCTIONS.md`](INSTRUCTIONS.md) for detailed development, building, testing, and contribution guidelines.

## License

[Specify Your License Here - e.g., MIT License] 