# Shell Core C Extension (`core`)

This directory contains the C source code for the `core` Python extension module, which provides low-level shell functionality like command execution, pipeline handling, and environment management. It is designed to be more efficient and offer finer control than standard Python libraries like `subprocess` for certain shell operations.

## Purpose

The primary motivation for this C extension is to provide:
*   Efficient execution of external commands and pipelines.
*   Direct manipulation of the shell environment (working directory, environment variables) associated with the C context.
*   Capture of `stderr` from executed commands for error reporting.
*   A persistent C-level context (`ShellContext`) to maintain state like the current working directory across Python calls.

## Files

*   `shell.h`: Header file defining the `ShellContext` structure and function prototypes for the core C shell logic.
*   `shell.c`: Implementation of the core shell logic, including command parsing, process creation (`fork`, `execvp`), pipeline setup, `cd` implementation, and environment variable handling.
*   `shell_python.c`: Python C API wrapper code. This file defines the Python `core.Shell` type, wraps the C functions from `shell.c`, handles data conversion between Python types (strings, lists, integers) and C types, and manages the lifecycle of the `ShellContext` within the Python object.

## Key Concepts and Implementation Details

### 1. Shell Context (`ShellContext` in `shell.h`)

This structure holds the state associated with a shell instance:

```c
// core/shell.h
typedef struct {
    char *cwd;              // Current working directory
    char **env;            // Environment variables (currently unused in exec)
    int last_exit_code;    // Last command's exit code
    bool interactive;      // Whether shell is interactive (currently unused)
    char *last_error;     // Last error message from stderr or execvp failure
} ShellContext;
```
*   A `ShellContext` is initialized by `shell_init()` (called from the Python `Shell` object's constructor) and cleaned up by `shell_cleanup()`.
*   It maintains the current working directory (`cwd`), which is updated by `shell_cd()`.
*   It stores the exit code and any captured error message from the last executed command.

### 2. Command Execution (`shell_execute` in `shell.c`)

*   **Parsing:** The `parse_command` static function handles basic command line parsing, splitting the input string into arguments (`argv`) while respecting simple single and double quotes.
*   **Process Creation:** It uses `fork()` to create a child process.
*   **Error Capture:** A `pipe()` is created before forking. The child process redirects its `stderr` to the write end of the pipe using `dup2()`. The parent process reads from the read end of the pipe *after* the child potentially executes the command.
*   **Execution:** The child process uses `execvp()` to replace itself with the requested command. `execvp` searches the system `PATH` for the executable.
*   **Error Handling:** If `execvp` fails (e.g., command not found), the child writes an error message (using `strerror(errno)`) to the pipe (which was its `stderr`). If the command runs but writes to `stderr`, that output is also captured by the parent.
*   **Waiting & Status:** The parent uses `waitpid()` to wait for the child to terminate and retrieve its exit status using `WIFEXITED` and `WEXITSTATUS`.
*   **Storing Results:** The exit code and any captured error message are stored in the `ShellContext`.

```c
// core/shell.c - Simplified snippet from shell_execute
// ... setup argv, setup error_pipe ...
pid_t pid = fork();
if (pid == 0) { // Child
    close(error_pipe[0]); // Close read end
    dup2(error_pipe[1], STDERR_FILENO); // Redirect stderr to pipe
    close(error_pipe[1]);
    execvp(argv[0], argv);
    // If execvp returns, it failed. Write error to stderr (the pipe).
    fprintf(stderr, "%s: %s", argv[0], strerror(errno));
    _exit(127);
} else { // Parent
    close(error_pipe[1]); // Close write end
    char error_buffer[MAX_ERROR_LEN] = {0};
    read(error_pipe[0], error_buffer, sizeof(error_buffer) - 1); // Read stderr
    close(error_pipe[0]);
    int status;
    waitpid(pid, &status, 0); // Wait for child
    ctx->last_exit_code = WEXITSTATUS(status);
    if (strlen(error_buffer) > 0) {
        ctx->last_error = strdup(error_buffer);
    }
    // ... cleanup argv ...
}
```

### 3. Pipeline Execution (`shell_execute_pipeline` in `shell.c`)

*   Creates `num_commands - 1` pipes.
*   Forks `num_commands` child processes.
*   Each child process (except the first and last) redirects its `stdin` from the previous pipe's read end and its `stdout` to the current pipe's write end using `dup2()`.
*   All pipe file descriptors are closed in the parent and children after `dup2` calls.
*   Each child calls `execvp` for its respective command.
*   The parent waits for all children; the exit code of the *last* command in the pipeline is stored.
*   Error capture via `stderr` is **not** currently implemented for pipeline stages in `shell_execute_pipeline`.

### 4. Python Wrapper (`shell_python.c`)

*   **`ShellObject`:** Defines a Python type (`core.Shell`) that holds a pointer to the C `ShellContext`.
*   **Lifecycle (`Shell_new`, `Shell_dealloc`):** Handles creation and destruction, ensuring `shell_init()` and `shell_cleanup()` are called appropriately.
*   **Method Definitions (`Shell_methods`):** Maps Python method names (e.g., `"execute"`) to C wrapper functions (e.g., `Shell_execute`).
*   **Argument Parsing (`PyArg_ParseTuple`):** Converts Python arguments (like strings, lists) into C types needed by the underlying `shell.c` functions. For example, parsing a Python string for `Shell_execute`:
    ```c
    // core/shell_python.c - Snippet from Shell_execute
    const char *command;
    // "s" format code parses one Python string argument into a C char*
    if (!PyArg_ParseTuple(args, "s", &command))
        return NULL; // Raises Python exception on failure
    int result = shell_execute(self->ctx, command); // Call C function
    // ...
    ```
*   **Return Value Building (`Py_BuildValue`, `PyLong_FromLong`, `PyUnicode_FromString`, `Py_RETURN_NONE`):** Converts results from C functions (integers, C strings) back into Python objects (integers, strings, None). Handles returning the tuple `(exit_code, error_message_or_None)`.
*   **Type Definition (`ShellType`):** Defines the structure and behavior of the `core.Shell` class for the Python interpreter.
*   **Module Initialization (`PyInit_core`):** The entry point when Python imports the `core` module. It prepares the `ShellType` and creates the module object.

## Building

This C extension requires:
*   A C compiler (like GCC or Clang).
*   Python development headers (usually installed via packages like `python3-dev` on Debian/Ubuntu or `python3-devel` on Fedora/CentOS).

The build process is typically handled automatically by `pip` when installing the package, using the information in `pyproject.toml` (which specifies `setuptools` and `Cython` as build requirements) and `setup.py` (which defines the `ext_modules`). `setuptools` invokes the C compiler to build the `.c` files into a shared object file (`.so` on Linux, `.pyd` on Windows) that Python can import.

To build compatible Linux wheels for distribution, use `cibuildwheel` as described in `INSTRUCTIONS.md`.

## Modifying

*   **Adding Functionality:** Define new functions in `shell.h` and implement them in `shell.c`.
*   **Exposing to Python:**
    *   Write a corresponding wrapper function in `shell_python.c` (e.g., `Shell_new_function`).
    *   Use `PyArg_ParseTuple` to get arguments from Python.
    *   Call your C function.
    *   Use `Py_BuildValue` or similar functions to return results to Python.
    *   Add an entry to the `Shell_methods` array.
*   **Rebuilding:** After making changes, you need to recompile the extension. The easiest way during development is often to reinstall the package in editable mode:
    ```bash
    pip install -e .
    ``` 

## TODO / Future Enhancements

*   **Improve Command Parsing (`parse_command`):**
    *   Implement handling for I/O redirection operators (`<`, `>`, `>>`, `2>`).
    *   Add support for environment variable expansion (e.g., `$VAR`, `${VAR}`).
    *   Handle more complex quoting and character escaping scenarios.

*   **Enhance Pipeline Execution (`shell_execute_pipeline`):**
    *   Capture and report `stderr` for individual commands within the pipeline, not just the final exit code.
    *   Implement a mechanism to retrieve the exit status of all commands in the pipeline (similar to Bash's `PIPESTATUS`).

*   **Full Environment Control:**
    *   Modify command execution (`shell_execute`, `shell_execute_pipeline`) to use `execve` instead of `execvp`, passing the environment variables stored in `ShellContext->env` to child processes.
    *   Implement `shell_unsetenv` function and expose it to Python.

*   **Signal Handling:**
    *   Define and implement a clear strategy for handling signals like `SIGINT` (Ctrl+C), particularly how they should be propagated to running child processes.

*   **Background Processes:**
    *   Add functionality to execute commands in the background (e.g., triggered by a trailing `&` in the command string). This involves managing child PIDs without immediately calling `waitpid`.

*   **Code Refinement:**
    *   Increase inline comments within `shell.c` and `shell_python.c` to clarify complex logic (e.g., pipe handling, process management).
    *   Review error handling paths for potential resource leaks or unhandled edge cases.
    *   Consider refactoring common process creation/waiting logic between `shell_execute` and `shell_execute_pipeline`. 