#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/wait.h>
#include <sys/types.h>
#include <fcntl.h>
#include <errno.h>
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
        dprintf(STDERR_FILENO, "%s: %s", argv[0], strerror(errno));
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
    pid_t pids[num_commands];
    int status = 0; // Hold status of last command

    // Create pipes
    for (int i = 0; i < num_commands - 1; i++) {
        if (pipe(pipes[i]) == -1) {
            perror("pipe");
            // TODO: Cleanup any already created pipes/processes
            return -1;
        }
    }

    // Create processes
    for (int i = 0; i < num_commands; i++) {
         // Check if the command itself is valid before forking
        if (!pipeline_argv[i] || !pipeline_argv[i][0]) {
             fprintf(stderr, "Error: Invalid empty command in pipeline stage %d\\n", i);
             // TODO: Proper cleanup of pipes/processes
             // For now, just mark as error and continue cleanup below
             pids[i] = -1; // Mark as invalid pid
             continue;
        }

        pids[i] = fork();
        if (pids[i] < 0) {
            perror("fork");
            // TODO: Cleanup
            return -1; // Or try to kill already started children? Complex.
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
            for (int j = 0; j < num_commands - 1; j++) {
                close(pipes[j][0]);
                close(pipes[j][1]);
            }

            // === Execute directly using execvp ===
            execvp(pipeline_argv[i][0], pipeline_argv[i]);

            // If execvp returns, it failed.
            // Note: Error message goes to stderr, which might be the pipe to the next stage
            perror(pipeline_argv[i][0]); 
            _exit(127);
        }
    }

    // Parent: close all pipe file descriptors
    for (int i = 0; i < num_commands - 1; i++) {
        close(pipes[i][0]);
        close(pipes[i][1]);
    }

    // Parent: Wait for all child processes
    // Store the status of the *last* command in the pipeline
    for (int i = 0; i < num_commands; i++) {
        if (pids[i] > 0) { // Only wait for valid pids
            int child_status;
            waitpid(pids[i], &child_status, 0);
            if (i == num_commands - 1) { // Is this the last command?
                status = child_status;
            }
        } else if (i == num_commands - 1) {
            // Handle case where the last command itself was invalid before fork
             status = -1; // Indicate error
        }
    }

    // Set context's last exit code based on the status of the last command
    // TODO: Pipeline error reporting needs improvement. We don't capture stderr here.
    if (ctx->last_error) {
        free(ctx->last_error);
        ctx->last_error = NULL;
    }

    // Check status from the last command
    if (WIFEXITED(status)) {
        ctx->last_exit_code = WEXITSTATUS(status);
    } else if (status == -1) { // Our custom error marker
         ctx->last_exit_code = -1; // Or some other error code
         ctx->last_error = strdup("Invalid command in pipeline");
    }
     else {
        ctx->last_exit_code = -1; // Indicate non-exit termination (signal?)
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
    int result = asprintf(&new_var, "%s=%s", name, value);
    if (result == -1) {
        return -1;
    }
    
    // Find existing variable
    for (int i = 0; ctx->env[i]; i++) {
        char *equals = strchr(ctx->env[i], '=');
        if (equals && strncmp(ctx->env[i], name, equals - ctx->env[i]) == 0) {
            free(ctx->env[i]);
            ctx->env[i] = new_var;
            return 0;
        }
    }
    
    // Add new variable
    int env_count = 0;
    while (ctx->env[env_count]) env_count++;
    
    if (env_count >= MAX_ENV - 1) {
        free(new_var);
        return -1;
    }
    
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