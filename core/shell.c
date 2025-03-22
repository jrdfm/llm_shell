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
    
    ctx->env = malloc(sizeof(char*) * (env_count + 1));
    for (int i = 0; i < env_count; i++) {
        ctx->env[i] = strdup(environ[i]);
    }
    ctx->env[env_count] = NULL;
    
    ctx->last_exit_code = 0;
    ctx->interactive = isatty(STDIN_FILENO);
    ctx->last_error = NULL;
    
    return ctx;
}

// Parse command into arguments with quote handling
static char** parse_command(const char *command, int *argc) {
    char **argv = malloc(sizeof(char*) * MAX_ARGS);
    char *cmd = strdup(command);
    int i = 0;
    char *p = cmd;
    int in_quotes = 0;
    char quote_char = 0;
    char *start = p;
    
    while (*p && i < MAX_ARGS - 1) {
        if (*p == '"' || *p == '\'') {
            if (!in_quotes) {
                quote_char = *p;
                in_quotes = 1;
                start = p + 1;
            } else if (*p == quote_char) {
                in_quotes = 0;
                *p = '\0';
                argv[i++] = strdup(start);
                start = p + 1;
            }
        } else if ((*p == ' ' || *p == '\t' || *p == '\n') && !in_quotes) {
            if (p > start) {
                *p = '\0';
                argv[i++] = strdup(start);
            }
            start = p + 1;
        }
        p++;
    }
    
    // Handle last argument
    if (p > start && i < MAX_ARGS - 1) {
        argv[i++] = strdup(start);
    }
    
    argv[i] = NULL;
    *argc = i;
    
    free(cmd);
    return argv;
}

// Execute a single command
int shell_execute(ShellContext *ctx, const char *command) {
    int argc;
    char **argv = parse_command(command, &argc);
    if (!argv || argc == 0) return -1;

    // Free previous error if any
    if (ctx->last_error) {
        free(ctx->last_error);
        ctx->last_error = NULL;
    }

    // Handle built-in cd
    if (strcmp(argv[0], "cd") == 0) {
        int ret = shell_cd(ctx, argc > 1 ? argv[1] : getenv("HOME"));
        if (ret != 0) {
            const char *err = strerror(errno);
            ctx->last_error = strdup(err);
        }
        for (int i = 0; argv[i]; i++) free(argv[i]);
        free(argv);
        return ret;
    }

    // Create pipe for error output
    int error_pipe[2];
    if (pipe(error_pipe) == -1) {
        for (int i = 0; argv[i]; i++) free(argv[i]);
        free(argv);
        return -1;
    }

    pid_t pid = fork();
    if (pid < 0) {
        close(error_pipe[0]);
        close(error_pipe[1]);
        for (int i = 0; argv[i]; i++) free(argv[i]);
        free(argv);
        return -1;
    } else if (pid == 0) {
        // Child process
        close(error_pipe[0]);  // Close read end
        
        // Redirect stderr to pipe
        dup2(error_pipe[1], STDERR_FILENO);
        close(error_pipe[1]);  // Close original write end
        
        execvp(argv[0], argv);
        
        // If execvp fails, write error to pipe
        char error_msg[MAX_ERROR_LEN];
        snprintf(error_msg, sizeof(error_msg), "%s: %s", argv[0], strerror(errno));
        ssize_t bytes_written = write(STDERR_FILENO, error_msg, strlen(error_msg));
        if (bytes_written < 0) {
            snprintf(error_msg, sizeof(error_msg), "Failed to write error message: %s", strerror(errno));
        }
        _exit(127);
    } else {
        // Parent process
        close(error_pipe[1]);  // Close write end
        
        // Read error output
        char error_buffer[MAX_ERROR_LEN] = {0};
        ssize_t bytes_read = read(error_pipe[0], error_buffer, sizeof(error_buffer) - 1);
        close(error_pipe[0]);  // Close read end
        
        // Wait for child
        int status;
        waitpid(pid, &status, 0);
        ctx->last_exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
        
        // Store error if any
        if (bytes_read > 0) {
            error_buffer[bytes_read] = '\0';  // Ensure null termination
            ctx->last_error = strdup(error_buffer);
        }
        
        // Clean up
        for (int i = 0; argv[i]; i++) free(argv[i]);
        free(argv);
        
        return ctx->last_exit_code;
    }
}

// Execute a pipeline of commands
int shell_execute_pipeline(ShellContext *ctx, const char **commands, int num_commands) {
    if (num_commands == 0) return 0;
    if (num_commands == 1) return shell_execute(ctx, commands[0]);

    int pipes[num_commands-1][2];
    pid_t pids[num_commands];

    // Create pipes
    for (int i = 0; i < num_commands-1; i++) {
        if (pipe(pipes[i]) == -1) {
            return -1;
        }
    }

    // Create processes
    for (int i = 0; i < num_commands; i++) {
        pids[i] = fork();
        if (pids[i] < 0) {
            return -1;
        }
        
        if (pids[i] == 0) {
            // Child process
            
            // Setup pipes
            if (i > 0) {
                dup2(pipes[i-1][0], STDIN_FILENO);
            }
            if (i < num_commands-1) {
                dup2(pipes[i][1], STDOUT_FILENO);
            }
            
            // Close all pipe fds
            for (int j = 0; j < num_commands-1; j++) {
                close(pipes[j][0]);
                close(pipes[j][1]);
            }

            // Execute command
            int argc;
            char **argv = parse_command(commands[i], &argc);
            execvp(argv[0], argv);
            _exit(127);
        }
    }

    // Parent: close all pipe fds
    for (int i = 0; i < num_commands-1; i++) {
        close(pipes[i][0]);
        close(pipes[i][1]);
    }

    // Wait for all processes
    int status;
    for (int i = 0; i < num_commands; i++) {
        waitpid(pids[i], &status, 0);
    }

    ctx->last_exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
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