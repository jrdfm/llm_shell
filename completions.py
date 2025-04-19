"""
Command completion module for shell command suggestions.
"""

import os
import glob
import threading
from prompt_toolkit.completion import Completer, Completion

# Debug mode - disabled by default
DEBUG = False
def debug(msg):
    if DEBUG:
        import sys
        print(f"DEBUG: {msg}", file=sys.stderr)
        sys.stderr.flush()

class ShellCompleter(Completer):
    """Handles command completion for the shell interface."""
    
    def __init__(self, core_shell):
        self.core_shell = core_shell  # Store the C shell instance
        self._path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        
        # Start with common commands (fast startup)
        self._command_cache = set([
            "cd", "exit", "ls", "grep", "cat", "echo", "find",
            "mkdir", "rm", "cp", "mv", "pwd", "touch", "git",
            "python", "pip", "apt", "sudo", "vim", "nano", "ssh"
        ])
        
        # Scan PATH in background for additional commands
        self._command_cache_complete = False
        threading.Thread(target=self._scan_path, daemon=True).start()
        
        # Common flags for frequently used commands
        self._common_flags = {
            "ls": ["-l", "-a", "-h", "-t", "--all", "--human-readable", "--color=auto"],
            "grep": ["-i", "-v", "-r", "-n", "--color=auto", "--include", "--exclude"],
            "find": ["-name", "-type", "-size", "-mtime", "-exec"],
            "git": ["--help", "--version", "commit", "push", "pull", "checkout", "branch"],
        }

    def _scan_path(self):
        """Scan PATH directories for executables (runs in background)."""
        cache = set()
        for dir_path in self._path_dirs:
            if not dir_path or not os.path.isdir(dir_path):
                continue
            try:
                for filename in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, filename)
                    try:
                        if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                            cache.add(filename)
                    except OSError:
                        continue
            except OSError:
                continue
        self._command_cache.update(cache)
        self._command_cache_complete = True

    def _complete_command(self, word_prefix):
        """Complete command names from PATH cache."""
        if not word_prefix:
            word_prefix = ""
            
        results = []
        for cmd in self._command_cache:
            if cmd.startswith(word_prefix):
                results.append(Completion(cmd, start_position=-len(word_prefix)))
        return results

    def _complete_path(self, document):
        """Complete file and directory paths."""
        path_prefix = document.get_word_before_cursor()
        
        # Expand ~ to home directory
        if path_prefix.startswith('~'):
            expanded = os.path.expanduser(path_prefix)
            dir_name = os.path.dirname(expanded)
            base_name = os.path.basename(expanded)
        else:
            if os.path.isabs(path_prefix) or path_prefix.startswith('./') or path_prefix.startswith('../'):
                # Absolute path or explicit relative path
                dir_name = os.path.dirname(path_prefix)
                base_name = os.path.basename(path_prefix)
            else:
                # Relative path without ./ prefix
                dir_name = self.core_shell.get_cwd()
                base_name = path_prefix
                
        # If directory part is empty, use current directory
        if not dir_name:
            if path_prefix.endswith('/'):
                dir_name = path_prefix
                base_name = ''
            else:
                dir_name = self.core_shell.get_cwd()
                
        # Convert relative paths to absolute
        if not os.path.isabs(dir_name):
            dir_name = os.path.join(self.core_shell.get_cwd(), dir_name)
            
        # Normalize the path
        dir_name = os.path.normpath(dir_name)
            
        results = []
        if os.path.isdir(dir_name):
            pattern = os.path.join(dir_name, base_name + '*')
            for path in glob.glob(pattern):
                name = os.path.basename(path)
                completion_text = name
                
                # Add trailing slash for directories
                if os.path.isdir(path):
                    completion_text += '/'
                    
                results.append(Completion(
                    completion_text,
                    start_position=-len(base_name),
                    display=completion_text
                ))
                
        return results

    def _complete_env_var(self, prefix):
        """Complete environment variables."""
        if not prefix.startswith('$'):
            return []
            
        var_prefix = prefix[1:]  # Remove $ from the beginning
        results = []
        
        for var_name in os.environ:
            if var_name.startswith(var_prefix):
                results.append(Completion(
                    f'${var_name}',
                    start_position=-len(prefix),
                    display=f'${var_name}'
                ))
                
        return results
        
    def _complete_flags(self, command, prefix):
        """Complete command flags."""
        if not prefix.startswith('-') or command not in self._common_flags:
            return []
            
        results = []
        for flag in self._common_flags[command]:
            if flag.startswith(prefix):
                results.append(Completion(
                    flag, 
                    start_position=-len(prefix)
                ))
                
        return results

    def get_completions(self, document, complete_event):
        """Main completion method."""
        text = document.text_before_cursor
        cursor_word = document.get_word_before_cursor()
        
        # 1. Handle environment variables (highest priority)
        if cursor_word.startswith('$'):
            for completion in self._complete_env_var(cursor_word):
                yield completion
            return
            
        # 2. Simple pipe handling - check if we have a pattern with pipe
        if '|' in text:
            pipe_parts = text.split('|')
            last_part = pipe_parts[-1].strip()
            
            # If we're immediately after a pipe or typing the first word after a pipe
            # (no spaces in the part after the last pipe)
            if not last_part or ' ' not in last_part:
                for completion in self._complete_command(last_part):
                    yield completion
                return
        
        # 3. Check if we're completing a command at the start
        words = text.split()
        if not words or (len(words) == 1 and not text.endswith(' ')):
            for completion in self._complete_command(cursor_word):
                yield completion
                
            # For first word, also provide path completions as alternative
            for completion in self._complete_path(document):
                yield completion
            return
                
        # 4. Complete arguments to a command
        if words:
            command = words[0]
            
            # 4a. Flag completion
            if cursor_word.startswith('-'):
                has_flag_match = False
                for completion in self._complete_flags(command, cursor_word):
                    has_flag_match = True
                    yield completion
                
                if has_flag_match:
                    return
                    
            # 4b. Path completion (fallback)
            for completion in self._complete_path(document):
                yield completion 