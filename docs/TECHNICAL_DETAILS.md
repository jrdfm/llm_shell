# Technical Implementation Details

This document delves deeper into the implementation specifics of the `shell-llm` components, particularly the C core and its interaction with Python.

## Core Shell Implementation (`core/shell.c`)

The C core provides high-performance shell operations through direct system calls and careful state management.

### 1. Shell Context Management

The `ShellContext` struct (defined in `core/shell.h`) maintains the state of the shell environment.

```c
// core/shell.h
typedef struct {
    char *cwd;              // Current working directory
    char **env;             // Environment variables (malloc'd array)
    int last_exit_code;     // Last command's exit code
    bool interactive;       // Whether shell is interactive
    char *last_error;      // Last error message (malloc'd)
} ShellContext;

// core/shell.c
ShellContext* shell_init(void) {
    ShellContext *ctx = malloc(sizeof(ShellContext));
    if (!ctx) return NULL;

    ctx->cwd = getcwd(NULL, 0); // Dynamically get CWD

    // Copy host environment variables
    extern char **environ;
    int env_count = 0;
    while (environ[env_count]) env_count++;
    ctx->env = malloc(sizeof(char*) * (env_count + 1));
    if (ctx->env) { // Check malloc success
        for (int i = 0; i < env_count; i++) {
            ctx->env[i] = strdup(environ[i]); // Duplicate each var
            // TODO: Add error checking for strdup
        }
        ctx->env[env_count] = NULL; // Null-terminate
    } else {
        // Handle env allocation failure
        free(ctx->cwd);
        free(ctx);
        return NULL;
    }

    ctx->last_exit_code = 0;
    ctx->interactive = isatty(STDIN_FILENO);
    ctx->last_error = NULL; // Initialize error pointer

    return ctx;
}

void shell_cleanup(ShellContext *ctx) {
    if (!ctx) return;
    if (ctx->cwd) free(ctx->cwd);
    if (ctx->last_error) free(ctx->last_error);
    if (ctx->env) {
        for (int i = 0; ctx->env[i]; i++) {
            free(ctx->env[i]); // Free each duplicated env string
        }
        free(ctx->env); // Free the array itself
    }
    free(ctx);
}
```

**Key Points:**

*   **State:** The `ShellContext` struct holds the CWD, a dynamically allocated copy of the environment variables, the last command's exit code, and the last captured error message.
*   **Initialization (`shell_init`):** Allocates the context, gets the initial CWD using `getcwd()`, performs a deep copy of the host's environment variables using `strdup`, and sets initial states.
*   **Cleanup (`shell_cleanup`):** Frees all dynamically allocated memory within the context (CWD string, error string, individual environment strings, and the environment array itself).

### 2. Command Execution (`shell_execute`)

This function handles the execution of a single command (provided as a pre-parsed `argv` array from Python).

```c
// core/shell.c (Simplified Snippet)
int shell_execute(ShellContext *ctx, char *const argv[]) {
    if (!argv || !argv[0]) return -1; // Basic validation

    // --- Handle Built-ins ---
    if (strcmp(argv[0], "cd") == 0) {
        // ... cd logic using shell_cd ...
        return ret;
    }
    // ... other potential built-ins (export, unset, etc.) ...


    // --- Execute External Command ---
    int error_pipe[2];
    if (pipe(error_pipe) == -1) { return -1; }

    pid_t pid = fork();
    if (pid < 0) { /* handle fork error, close pipes */ return -1; }

    if (pid == 0) {
        // --- Child Process ---
        close(error_pipe[0]); // Close read end
        dup2(error_pipe[1], STDERR_FILENO); // Redirect stderr to pipe
        close(error_pipe[1]);

        execvp(argv[0], argv); // Execute command

        // If execvp returns, it failed. Write error to the pipe (stderr).
        dprintf(STDERR_FILENO, "%s: %s", argv[0], strerror(errno));
        _exit(127); // Exit child immediately

    } else {
        // --- Parent Process ---
        close(error_pipe[1]); // Close write end

        // Read potential error message from pipe
        char error_buffer[MAX_ERROR_LEN] = {0};
        ssize_t bytes_read = read(error_pipe[0], error_buffer, sizeof(error_buffer) - 1);
        close(error_pipe[0]);

        // Wait for child and get status
        int status;
        waitpid(pid, &status, 0);
        ctx->last_exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;

        // Store error message if one was read and exit code indicates failure
        if (ctx->last_exit_code != 0 && bytes_read > 0) {
            if (ctx->last_error) free(ctx->last_error);
            error_buffer[bytes_read] = '\0';
            ctx->last_error = strdup(error_buffer);
        } else {
             // Clear any previous error if command succeeded
             if (ctx->last_error) {
                 free(ctx->last_error);
                 ctx->last_error = NULL;
             }
        }
        return ctx->last_exit_code;
    }
}
```

**Key Points:**

*   **Input:** Takes a `NULL`-terminated `argv` array (e.g., `["ls", "-l", NULL]`).
*   **Built-ins:** Checks for built-in commands like `cd` first and handles them directly within the parent process.
*   **Fork/Exec:** Uses the standard `fork`/`execvp` pattern for external commands.
*   **Stderr Capture:** Creates a pipe (`error_pipe`) before forking. The child redirects its `stderr` to the write end of this pipe. This allows the parent to capture error messages even if `execvp` fails or the command writes to `stderr`.
*   **Error Storage:** The parent reads from the pipe after the child exits. If an error message was read and the command failed (non-zero exit code), the message is stored in `ctx->last_error`.

### 3. Pipeline Execution (`shell_execute_pipeline`)

Handles Unix-style pipelines (`cmd1 | cmd2 | ...`).

```c
// core/shell.c (Simplified Snippet)
int shell_execute_pipeline(ShellContext *ctx, char *const *const *pipeline_argv, int num_commands) {
    if (num_commands <= 0) return 0;
    if (num_commands == 1) return shell_execute(ctx, pipeline_argv[0]); // Use single exec logic

    int pipes[num_commands - 1][2];
    pid_t pids[num_commands];

    // 1. Create all necessary pipes
    for (int i = 0; i < num_commands - 1; i++) {
        if (pipe(pipes[i]) == -1) { /* handle error, close opened pipes */ return -1; }
    }

    // 2. Fork a child process for each command
    for (int i = 0; i < num_commands; i++) {
        pids[i] = fork();
        if (pids[i] < 0) { /* handle error, kill children?, close pipes */ return -1; }

        if (pids[i] == 0) {
            // --- Child Process ---

            // Redirect stdin from previous pipe (if not first command)
            if (i > 0) {
                dup2(pipes[i - 1][0], STDIN_FILENO);
            }
            // Redirect stdout to next pipe (if not last command)
            if (i < num_commands - 1) {
                dup2(pipes[i][1], STDOUT_FILENO);
            }

            // Close *all* pipe fds in the child
            for (int j = 0; j < num_commands - 1; j++) {
                close(pipes[j][0]);
                close(pipes[j][1]);
            }

            // Execute the command for this stage
            execvp(pipeline_argv[i][0], pipeline_argv[i]);
            perror(pipeline_argv[i][0]); // Write exec error to stderr (might be piped)
            _exit(127);
        }
    }

    // --- Parent Process ---

    // 3. Close all pipe fds in the parent
    for (int i = 0; i < num_commands - 1; i++) {
        close(pipes[i][0]);
        close(pipes[i][1]);
    }

    // 4. Wait for all children and get status of the last one
    int last_status = 0;
    for (int i = 0; i < num_commands; i++) {
        int status;
        waitpid(pids[i], &status, 0);
        if (i == num_commands - 1) {
            last_status = status; // Store status of the last command
        }
    }

    // Update context (simplified error handling for pipelines)
    ctx->last_exit_code = WIFEXITED(last_status) ? WEXITSTATUS(last_status) : -1;
    if (ctx->last_error) { free(ctx->last_error); ctx->last_error = NULL; }
    // Note: Pipeline stderr capture is not currently implemented here.

    return ctx->last_exit_code;
}

```

**Key Points:**

*   **Input:** Takes an array of `argv` arrays (`char *const *const *pipeline_argv`).
*   **Pipes:** Creates N-1 pipes for N commands.
*   **Forking:** Forks a child process for each command.
*   **Redirection (`dup2`):** Each child redirects its standard input (`STDIN_FILENO`) to the read end of the *previous* command's pipe and its standard output (`STDOUT_FILENO`) to the write end of the *next* command's pipe (adjusting for the first and last commands).
*   **Closing FDs:** It's crucial that *all* processes (parent and children) close *all* pipe file descriptors they don't explicitly need. Children close all of them after `dup2`. The parent closes all of them after launching all children. This prevents processes from hanging waiting for input that will never arrive.
*   **Waiting:** The parent waits for all children to complete.
*   **Exit Status:** The exit status of the *last* command in the pipeline is typically used as the overall exit status of the pipeline.

### 4. Directory Management (`shell_cd`)

Handles changing the shell's current working directory.

```c
// core/shell.c
int shell_cd(ShellContext *ctx, const char *path) {
    if (chdir(path) != 0) {
        // chdir failed, errno is set
        return -errno; // Return negative errno on failure
    }

    // chdir succeeded, update context's cwd
    free(ctx->cwd); // Free old CWD string
    ctx->cwd = getcwd(NULL, 0); // Get new CWD
    if (!ctx->cwd) {
        // Handle getcwd failure (rare)
        perror("getcwd after cd");
        return -1; // Indicate error
    }
    // Clear previous error on successful cd
    if (ctx->last_error) {
        free(ctx->last_error);
        ctx->last_error = NULL;
    }
    return 0; // Success
}
```

**Key Points:**

*   Uses the standard `chdir()` function.
*   If `chdir` succeeds, it updates `ctx->cwd` by freeing the old path and getting the new one with `getcwd()`.
*   Returns `0` on success and `-errno` on failure (allowing the caller to use `strerror` on the absolute value).

### 5. Environment Variable Handling

Provides functions to get and set environment variables within the shell's context.

```c
// core/shell.c
const char* shell_getenv(ShellContext *ctx, const char *name) {
    if (!ctx || !ctx->env || !name) return NULL;
    size_t name_len = strlen(name);
    for (int i = 0; ctx->env[i]; i++) {
        // Check if string starts with "name="
        if (strncmp(ctx->env[i], name, name_len) == 0 && ctx->env[i][name_len] == '=') {
            return ctx->env[i] + name_len + 1; // Return pointer to value part
        }
    }
    return NULL; // Not found
}

int shell_setenv(ShellContext *ctx, const char *name, const char *value) {
    if (!ctx || !name) return -1; // Invalid args

    // Format "name=value" string
    char *new_var;
    int len = asprintf(&new_var, "%s=%s", name, value); // GNU extension
    if (len == -1) { return -1; } // Allocation failure

    size_t name_len = strlen(name);
    int env_count = 0;

    // Try to find and replace existing variable
    for (int i = 0; ctx->env && ctx->env[i]; i++) {
        env_count++;
        if (strncmp(ctx->env[i], name, name_len) == 0 && ctx->env[i][name_len] == '=') {
            free(ctx->env[i]); // Free old string
            ctx->env[i] = new_var; // Assign new string
            return 0; // Success
        }
    }

    // Not found, add new variable - requires reallocating the env array
    // (Ensure MAX_ENV is handled or use dynamic resizing)
    if (env_count >= MAX_ENV -1) { // Check against fixed limit (or resize)
         free(new_var);
         fprintf(stderr, "Environment limit (%d) reached.\n", MAX_ENV);
         return -1; // Or handle resizing
    }

    // Reallocate space for the new pointer + NULL terminator
    char **new_env = realloc(ctx->env, sizeof(char*) * (env_count + 2));
    if (!new_env) {
        free(new_var);
        return -1; // Realloc failed
    }
    ctx->env = new_env;
    ctx->env[env_count] = new_var;      // Add new variable string
    ctx->env[env_count + 1] = NULL; // Add new NULL terminator
    return 0; // Success
}
```

**Key Points:**

*   **Internal Copy:** Operates on the shell's *copy* of the environment (`ctx->env`), not the host process environment.
*   **`shell_getenv`:** Performs a linear search for `NAME=` prefix and returns a pointer to the value part.
*   **`shell_setenv`:**
    *   Formats the `NAME=VALUE` string.
    *   Searches for an existing variable by `NAME=`. If found, frees the old string and replaces the pointer.
    *   If not found, **reallocates** the `ctx->env` array to make space, adds the new variable pointer, and updates the `NULL` terminator. (The original code had a fixed `MAX_ENV` limit, this version shows reallocation which is more robust). Uses `asprintf` (a GNU extension) for easy allocation/formatting.

## CPython Wrapper (`core/shell_python.c`)

This file acts as the bridge between Python and the C core using the CPython API.

### Key Functions

*   **`py_list_to_argv` / `free_argv`**: Helper functions added during refactoring. `py_list_to_argv` takes a Python list of strings, allocates a `NULL`-terminated C `char**` array, duplicates each string using `strdup`, and returns the C array. `free_argv` frees the memory allocated by `py_list_to_argv`.
*   **`Shell_execute` (Python Method)**:
    *   Parses arguments using `PyArg_ParseTuple(args, "O!", &PyList_Type, &py_argv_list)` to expect a Python list.
    *   Calls `py_list_to_argv` to convert the Python list to `char**`.
    *   Calls the C function `shell_execute(self->ctx, argv)`.
    *   Calls `free_argv` to release the C array memory.
    *   Builds and returns the Python result tuple `(exit_code, error_message_or_None)`.
*   **`Shell_execute_pipeline` (Python Method)**:
    *   Parses arguments using `PyArg_ParseTuple(args, "O!", &PyList_Type, &py_pipeline_list)` to expect a Python list (of lists).
    *   Allocates a C `char***` array (`pipeline_argv`).
    *   Iterates through the outer Python list. For each inner list, it calls `py_list_to_argv` and stores the resulting `char**` in the `pipeline_argv`.
    *   Calls the C function `shell_execute_pipeline(self->ctx, (char *const *const *)pipeline_argv, num_commands)`.
    *   Frees the allocated memory by iterating through `pipeline_argv`, calling `free_argv` on each inner `char**`, and finally freeing `pipeline_argv` itself.
    *   Builds and returns the Python result tuple.
*   **Other Methods (`Shell_cd`, `Shell_getenv`, etc.)**: Simpler methods that typically parse basic Python types (string, int), call the corresponding C function, and convert the C result back to a Python object.
*   **Type Definition (`ShellType`, `Shell_methods`, `moduledef`)**: Standard CPython boilerplate to define the `core.Shell` type, its methods, and the `core` module itself for Python import.

## Python Layer (`shell.py`)

### Command Parsing (`shlex`)

The critical change is that `shell.py` now handles parsing *before* calling the C extension.

```python
# shell.py (inside LLMShell.handle_command)
import shlex

# ...
        try:
            query = query.strip()
            # ... handle '#' queries and 'cd' built-in ...

            # --- Core Execution ---
            else:
                if '|' in query:
                    # Handle Pipeline
                    command_description = "Pipeline"
                    commands_str = [cmd.strip() for cmd in query.split('|')]
                    # *** PARSING HAPPENS HERE ***
                    pipeline_args = [shlex.split(cmd) for cmd in commands_str]
                    valid_pipeline_args = [args for args in pipeline_args if args] # Filter empty
                    if not valid_pipeline_args:
                         # Handle error
                         ...
                    else:
                         # *** PASS LIST-OF-LISTS TO CORE ***
                         result = self.core_shell.execute_pipeline(valid_pipeline_args)
                else:
                    # Handle Single Command
                    command_description = "Command"
                    # *** PARSING HAPPENS HERE ***
                    args = shlex.split(query)
                    if not args: # Handle empty input
                         return
                    # *** PASS LIST TO CORE ***
                    result = self.core_shell.execute(args)

            # ... process result / handle errors ...

        except ValueError as e:
            # *** Catch shlex parsing errors ***
            await self.error_handler.handle_error(f"Parsing error: {e}")
        except Exception as e:
            # ... handle other errors ...
```

**Key Points:**

*   **`shlex.split()`:** This standard library function is used to parse the raw command string according to shell-like rules for quoting and escaping.
*   **Input to C Core:** The C extension functions (`execute`, `execute_pipeline`) receive Python lists or lists-of-lists, which are then converted to C arrays (`char**` or `char***`) by the CPython wrapper (`core/shell_python.c`).
*   **Error Handling:** `shlex.split()` raises `ValueError` for parsing errors (like unterminated quotes), which is caught in `shell.py`. Execution errors from the C core are returned via the `(exit_code, error_msg)` tuple. 