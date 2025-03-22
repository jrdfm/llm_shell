#ifndef SHELL_H
#define SHELL_H

#include <stdbool.h>

// Shell context structure
typedef struct {
    char *cwd;              // Current working directory
    char **env;            // Environment variables
    int last_exit_code;    // Last command's exit code
    bool interactive;      // Whether shell is interactive
    char *last_error;     // Last error message
} ShellContext;

// Initialize shell context
ShellContext* shell_init(void);

// Execute a command with arguments
int shell_execute(ShellContext *ctx, const char *command);

// Execute a pipeline of commands
int shell_execute_pipeline(ShellContext *ctx, const char **commands, int num_commands);

// Change directory
int shell_cd(ShellContext *ctx, const char *path);

// Get environment variable
const char* shell_getenv(ShellContext *ctx, const char *name);

// Set environment variable
int shell_setenv(ShellContext *ctx, const char *name, const char *value);

// Get last error message
const char* shell_get_error(ShellContext *ctx);

// Clean up shell context
void shell_cleanup(ShellContext *ctx);

#endif // SHELL_H 