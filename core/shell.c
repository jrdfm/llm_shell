#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <fcntl.h>
#include <errno.h>
#include <signal.h>
#include "shell.h"

#define MAX_ARGS 256
#define MAX_ENV 1024
#define MAX_ERROR_LEN 4096
#define MAX_ARG_LEN 1024 // Define a maximum length for a single argument

// Initialize shell context
ShellContext* shell_init(void) {
    ShellContext *ctx = malloc(sizeof(ShellContext));
    if (!ctx) return NULL;

    // Get current working directory
    ctx->cwd = getcwd(NULL, 0);
    
    // Copy environment
    extern char **environ;
    int env_count = 0;
    while (environ[env_count]) env_count++;
    // Allocate memory for environment variables
    ctx->env = malloc(sizeof(char*) * (env_count + 1));
    for (int i = 0; i < env_count; i++) {
        ctx->env[i] = strdup(environ[i]);
    }
    ctx->env[env_count] = NULL;// Null-terminate the environment array
    
    ctx->last_exit_code = 0;// Initialize last exit code to 0
    ctx->interactive = isatty(STDIN_FILENO);// Check if the shell is interactive
    ctx->last_error = NULL;// Initialize last error to NULL
    
    return ctx;
}

// Execute a single command, taking pre-parsed arguments
// Executes directly using execvp
int shell_execute(ShellContext *ctx, char *const argv[]) {
    if (!argv || !argv[0]) return -1;
    int argc = 0;
    while(argv[argc] != NULL) argc++;
    if (argc == 0) return -1;

    if (ctx->last_error) { free(ctx->last_error); ctx->last_error = NULL; }

    if (strcmp(argv[0], "cd") == 0) {
        // Determine path: argv[1] or HOME if argv[1] is NULL or missing
        const char *path_to_cd = (argc > 1 && argv[1] != NULL) ? argv[1] : getenv("HOME");
        if (path_to_cd == NULL) { // Handle case where HOME is not set
             ctx->last_error = strdup("cd: HOME not set");
             return -1; // Or some other error code
        }
        int ret = shell_cd(ctx, path_to_cd);
        if (ret != 0) {
            // Use strerror_r for thread safety if this were multithreaded,
            // but strerror is fine for now. Capture error before it's overwritten.
            const char *err_msg = strerror(errno);
            ctx->last_error = strdup(err_msg ? err_msg : "Unknown error");
        }
        // No need to free argv here, Python wrapper owns it
        return ret;
    }

    // --- Execute via execvp --- 
    int error_pipe[2];
    if (pipe(error_pipe) == -1) { return -1; }

    pid_t pid = fork();
    if (pid < 0) { close(error_pipe[0]); close(error_pipe[1]); return -1; }

    if (pid == 0) {
        // --- Child Process ---
        close(error_pipe[0]); // Close read end
        dup2(error_pipe[1], STDERR_FILENO); // Redirect stderr to pipe
        close(error_pipe[1]);

        // === Execute directly using execvp ===
        execvp(argv[0], argv);

        // If execvp returns, it failed.
        // Format a more complete error message with the full strerror text
        char error_buf[MAX_ERROR_LEN];
        snprintf(error_buf, sizeof(error_buf), "%s: %s", argv[0], strerror(errno));
        write(STDERR_FILENO, error_buf, strlen(error_buf));
        _exit(127); // Exit child immediately

    } else {
        // --- Parent Process ---
        close(error_pipe[1]);
        char error_buffer[MAX_ERROR_LEN] = {0};
        ssize_t bytes_read = read(error_pipe[0], error_buffer, sizeof(error_buffer) - 1);
        close(error_pipe[0]);
        int status;
        waitpid(pid, &status, 0);
        ctx->last_exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
        if (ctx->last_exit_code != 0 && bytes_read > 0) {
            if (ctx->last_error) free(ctx->last_error);
            error_buffer[bytes_read] = '\0';
            ctx->last_error = strdup(error_buffer);
        } else {
             if (ctx->last_error) { free(ctx->last_error); ctx->last_error = NULL; }
        }
        return ctx->last_exit_code;
    }
}

// Helper function to clean up resources during pipeline setup failure
static void cleanup_pipeline_resources(int num_commands, int pipes[][2], int pipes_to_close_idx, pid_t pids[], int pids_to_kill_idx) {
    // Close pipes created up to the error point
    for (int i = 0; i <= pipes_to_close_idx; i++) {
        close(pipes[i][0]);
        close(pipes[i][1]);
    }

    // Terminate and wait for children forked before the error
    for (int i = 0; i <= pids_to_kill_idx; i++) {
        if (pids[i] > 0) {
            kill(pids[i], SIGTERM); // Send termination signal
            waitpid(pids[i], NULL, 0); // Wait for termination
        }
    }
}

// Execute a pipeline of commands, taking pre-parsed arguments for each command
int shell_execute_pipeline(ShellContext *ctx, char *const *const *pipeline_argv, int num_commands) {
    if (num_commands <= 0) return 0;

    // If only one command, execute it directly (more efficient)
    if (num_commands == 1) {
        // Need to handle potential NULL argv[0] case if outer list allows empty lists
        if (!pipeline_argv[0] || !pipeline_argv[0][0]) return -1; // Invalid command
        return shell_execute(ctx, pipeline_argv[0]);
    }

    int pipes[num_commands - 1][2];
    // Initialize pipe fds to -1 to track which are open
    for (int i = 0; i < num_commands - 1; i++) {
        pipes[i][0] = -1;
        pipes[i][1] = -1;
    }

    pid_t pids[num_commands];
    // Initialize pids to 0 or -1 (0 = not forked, -1 = error/invalid)
    for (int i = 0; i < num_commands; i++) {
        pids[i] = 0;
    }

    int status = 0; // Hold status of last command
    int setup_error = 0; // Flag to indicate setup failed

    // Create pipes
    for (int i = 0; i < num_commands - 1; i++) {
        if (pipe(pipes[i]) == -1) {
            perror("pipe");
            // Cleanup pipes created so far (up to i-1)
            cleanup_pipeline_resources(num_commands, pipes, i - 1, pids, -1); // No pids to kill yet
            return -1; // Return error after cleanup
        }
    }

    // Create processes
    for (int i = 0; i < num_commands; i++) {
         // Check if the command itself is valid before forking
        if (!pipeline_argv[i] || !pipeline_argv[i][0]) {
             fprintf(stderr, "Error: Invalid empty command in pipeline stage %d\n", i);
             pids[i] = -1; // Mark as invalid
             setup_error = 1; // Mark that setup failed
             break; // Stop creating processes
        }

        pids[i] = fork();
        if (pids[i] < 0) {
            perror("fork");
            // Cleanup pipes and already forked processes (up to i-1)
            cleanup_pipeline_resources(num_commands, pipes, num_commands - 2, pids, i - 1);
            return -1; // Return error after cleanup
        }

        if (pids[i] == 0) {
            // Child process

            // Redirect input from previous command's pipe (if not the first command)
            if (i > 0) {
                if (dup2(pipes[i - 1][0], STDIN_FILENO) == -1) {
                    perror("dup2 stdin");
                    _exit(1);
                }
            }
            // Redirect output to next command's pipe (if not the last command)
            if (i < num_commands - 1) {
                if (dup2(pipes[i][1], STDOUT_FILENO) == -1) {
                    perror("dup2 stdout");
                    _exit(1);
                }
            }

            // Close *all* pipe file descriptors in the child
            // Only close valid pipe fds
            for (int j = 0; j < num_commands - 1; j++) {
                if (pipes[j][0] != -1) close(pipes[j][0]);
                if (pipes[j][1] != -1) close(pipes[j][1]);
            }

            // === Execute directly using execvp ===
            execvp(pipeline_argv[i][0], pipeline_argv[i]);

            // If execvp returns, it failed.
            // Use the same more detailed error format as in shell_execute
            char error_buf[MAX_ERROR_LEN];
            snprintf(error_buf, sizeof(error_buf), "%s: %s", pipeline_argv[i][0], strerror(errno));
            write(STDERR_FILENO, error_buf, strlen(error_buf));
            _exit(127);
        }
    }

    // Parent: close all pipe file descriptors
    for (int i = 0; i < num_commands - 1; i++) {
        if (pipes[i][0] != -1) close(pipes[i][0]);
        if (pipes[i][1] != -1) close(pipes[i][1]);
    }

    // If setup failed partway, clean up processes that were started
    if (setup_error) {
        // Wait for any processes that *were* successfully forked before the error
        for(int i = 0; i < num_commands; ++i) {
            if (pids[i] > 0) {
                 waitpid(pids[i], NULL, 0); // Wait for them to finish (or be killed)
            }
        }
        if (ctx->last_error) free(ctx->last_error);
        ctx->last_error = strdup("Invalid command in pipeline");
        ctx->last_exit_code = -1; // Indicate setup error
        return ctx->last_exit_code;
    }

    // Parent: Wait for all child processes
    // Store the status of the *last* command in the pipeline
    for (int i = 0; i < num_commands; i++) {
        if (pids[i] > 0) { // Only wait for valid pids (should be all if no setup_error)
            int child_status;
            waitpid(pids[i], &child_status, 0);
            if (i == num_commands - 1) { // Is this the last command?
                status = child_status;
            }
        }
        // Note: The case where the last command was invalid (pids[i] == -1)
        // is now handled by the setup_error logic above.
    }

    // Set context's last exit code based on the status of the last command
    // Note: Capturing specific stderr for each failed command in a pipeline
    // would require additional plumbing (e.g., separate error pipes per command).
    if (ctx->last_error) {
        free(ctx->last_error);
        ctx->last_error = NULL;
    }

    // Check status from the last command
    if (WIFEXITED(status)) {
        ctx->last_exit_code = WEXITSTATUS(status);
        // If the last command exited with an error, store a generic message
        if (ctx->last_exit_code != 0) {
             ctx->last_error = strdup("Pipeline command failed");
        }
    } else if (status == -1) { // Our custom error marker from setup_error
         // This case is already handled by the setup_error block earlier
         // where last_error is set to "Invalid command in pipeline"
         // and last_exit_code is set to -1.
         // We just need to ensure we don't overwrite it here.
    } else {
        ctx->last_exit_code = -1; // Indicate non-exit termination (signal?)
        // Store a message indicating abnormal termination
        ctx->last_error = strdup("Pipeline command terminated abnormally");
    }

    // No need to free pipeline_argv, Python wrapper owns it
    return ctx->last_exit_code;
}

// Change directory
int shell_cd(ShellContext *ctx, const char *path) {
    if (chdir(path) != 0) {
        return -1;
    }
    
    // Update current working directory
    free(ctx->cwd);
    ctx->cwd = getcwd(NULL, 0);
    return 0;
}

// Get environment variable
const char* shell_getenv(ShellContext *ctx, const char *name) {
    for (int i = 0; ctx->env[i]; i++) {
        char *equals = strchr(ctx->env[i], '=');
        if (equals && strncmp(ctx->env[i], name, equals - ctx->env[i]) == 0) {
            return equals + 1;
        }
    }
    return NULL;
}

// Set environment variable
int shell_setenv(ShellContext *ctx, const char *name, const char *value) {
    char *new_var;
    // Use snprintf to avoid potential buffer overflows if name/value are huge,
    // though the immediate issue is the realloc below.
    int required_size = snprintf(NULL, 0, "%s=%s", name, value);
    if (required_size < 0) { return -1; } // Encoding error
    new_var = malloc(required_size + 1);
    if (!new_var) { return -1; } // Malloc failed
    sprintf(new_var, "%s=%s", name, value); // sprintf is safe here due to size check

    // Find existing variable
    int i;
    for (i = 0; ctx->env[i]; i++) {
        char *equals = strchr(ctx->env[i], '=');
        // Check for NULL equals just in case env var has no '='
        if (equals && strncmp(ctx->env[i], name, equals - ctx->env[i]) == 0 && name[equals - ctx->env[i]] == '\0') {
            free(ctx->env[i]); // Free the old string
            ctx->env[i] = new_var; // Assign the newly allocated string
            return 0;
        }
    }

    // --- Add new variable --- 
    int env_count = i; // 'i' is now the index of the NULL terminator

    // Resize the environment array: needs space for env_count existing pointers,
    // the new pointer, and the new NULL terminator (env_count + 2 total)
    char **new_env = realloc(ctx->env, sizeof(char*) * (env_count + 2));
    if (!new_env) {
        free(new_var); // Free the variable string we allocated
        // ctx->env is still the old, valid pointer
        return -1; // Realloc failed
    }
    ctx->env = new_env; // Update context pointer to the new array

    // Add the new variable and the null terminator
    ctx->env[env_count] = new_var;
    ctx->env[env_count + 1] = NULL;

    return 0;
}

// Get last error message
const char* shell_get_error(ShellContext *ctx) {
    return ctx->last_error;
}

// Clean up shell context
void shell_cleanup(ShellContext *ctx) {
    if (!ctx) return;
    
    if (ctx->cwd) free(ctx->cwd);
    if (ctx->last_error) free(ctx->last_error);
    
    if (ctx->env) {
        for (int i = 0; ctx->env[i]; i++) {
            free(ctx->env[i]);
        }
        free(ctx->env);
    }
    
    free(ctx);
} 