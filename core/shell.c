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
    
    return ctx;
}

// Parse command into arguments
static char** parse_command(const char *command, int *argc) {
    char **argv = malloc(sizeof(char*) * MAX_ARGS);
    char *cmd = strdup(command);
    char *token = strtok(cmd, " \t\n");
    int i = 0;
    
    while (token && i < MAX_ARGS - 1) {
        argv[i++] = strdup(token);
        token = strtok(NULL, " \t\n");
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

    // Handle built-in cd
    if (strcmp(argv[0], "cd") == 0) {
        int ret = shell_cd(ctx, argc > 1 ? argv[1] : getenv("HOME"));
        for (int i = 0; argv[i]; i++) free(argv[i]);
        free(argv);
        return ret;
    }

    pid_t pid = fork();
    if (pid < 0) {
        return -1;
    } else if (pid == 0) {
        // Child process
        execvp(argv[0], argv);
        _exit(127);  // Command not found
    } else {
        // Parent process
        int status;
        waitpid(pid, &status, 0);
        ctx->last_exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : -1;
        
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

// Clean up shell context
void shell_cleanup(ShellContext *ctx) {
    if (!ctx) return;
    
    free(ctx->cwd);
    
    for (int i = 0; ctx->env[i]; i++) {
        free(ctx->env[i]);
    }
    free(ctx->env);
    
    free(ctx);
} 