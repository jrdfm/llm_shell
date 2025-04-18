"""
Command completion module for shell command suggestions.
"""

import os
import stat # For checking executable bits
import glob
from prompt_toolkit.completion import Completer, Completion

class ShellCompleter(Completer):
    def __init__(self, core_shell):
        self.core_shell = core_shell # Store the C shell instance
        self._path_dirs = self._get_path_dirs()
        # Temporarily disable path scanning for debugging startup speed
        # self._path_cache = self._build_path_cache()
        self._path_cache = set() # Use an empty cache for now
        self._path_cache.update(["cd", "exit"]) # Keep builtins

    def _get_path_dirs(self):
        """Get list of directories from PATH environment variable."""
        # Use os.environ for PATH completion, as it's unlikely to change
        # frequently within the shell session itself in a way that matters
        # for command completion.
        path_str = os.environ.get('PATH', '')
        return path_str.split(os.pathsep)

    def _build_path_cache(self):
        """Scan PATH directories for executables."""
        cache = set()
        for dir_path in self._path_dirs:
            if not dir_path:
                continue
            try:
                # Check if dir_path is actually a directory
                if os.path.isdir(dir_path):
                    for filename in os.listdir(dir_path):
                        file_path = os.path.join(dir_path, filename)
                        try:
                             # Check if it's a file and executable by the user
                             if os.path.isfile(file_path) and os.access(file_path, os.X_OK):
                                 cache.add(filename)
                        except OSError: # Handle potential permission errors reading files
                            continue
            except OSError: # Handle potential permission errors reading directories
                continue
        return cache

    def _complete_command(self, word):
        """Yield completions for commands in PATH."""
        # Refresh cache if needed? For now, use initial cache.
        for cmd in self._path_cache:
            if cmd.startswith(word):
                yield Completion(cmd, start_position=-len(word))

    def _complete_environment_variable(self, word):
        """Yield completions for environment variables."""
        # Using os.environ for now. For perfect accuracy, would need
        # access to self.core_shell.env, perhaps via a new C method.
        prefix = word[1:] # Strip leading '$'
        for var_name in os.environ.keys():
            if var_name.startswith(prefix):
                yield Completion(
                    f'${var_name}', # Yield with the $
                    start_position=-len(word), # Start replacing from the $
                    display=f'${var_name}'
                )

    def _complete_path(self, document):
        """Yield completions for file/directory paths.
           Handles: ~, /path, ./path, ../path, partial_name
        """
        word = document.get_word_before_cursor()
        if not word:
            # If triggered on empty space, list CWD
            dir_name = self.core_shell.get_cwd()
            partial_name = ''
        else:
            path = os.path.expanduser(word) # Expand ~
            dir_name = os.path.dirname(path)
            partial_name = os.path.basename(path)

            # If dirname is empty, it means we're completing in the CWD
            if not dir_name:
                dir_name = self.core_shell.get_cwd()
            # If dirname is relative, make it absolute relative to CWD
            elif not os.path.isabs(dir_name):
                current_shell_cwd = self.core_shell.get_cwd()
                dir_name = os.path.join(current_shell_cwd, dir_name)
                # Normalize in case of .. etc.
                dir_name = os.path.normpath(dir_name)

        try:
            # Ensure directory exists before globbing
            if not os.path.isdir(dir_name):
                return

            # Use glob to find matches
            pattern = os.path.join(dir_name, partial_name + '*')
            # print(f"\nGlobbing: {pattern}\n") # Debug print

            for match in glob.glob(pattern):
                basename = os.path.basename(match) # Get only the filename/dirname part
                completion = basename
                start_pos = -len(partial_name) if partial_name else 0

                try:
                    # Check if it's a directory to add a slash
                    if os.path.isdir(match):
                        completion += '/'
                except OSError: # Handle potential permission error on isdir check
                    pass # Just yield without the slash

                yield Completion(
                    completion,
                    start_position=start_pos,
                    display=basename # Show only the basename in the list
                )
        except OSError as e:
            # print(f"\nOSError during path completion: {e}\n") # Debug print
            pass
        except Exception as e:
            # print(f"\nUnexpected error during path completion: {e}\n") # Debug print
            pass

    def get_completions(self, document, complete_event):
        """Determine completion type and yield results."""
        text = document.text_before_cursor
        word = document.get_word_before_cursor()

        # Very basic context detection: Is it the first word?
        # This determines if we should offer commands.
        stripped_text = text.lstrip()
        is_first_word = not stripped_text or stripped_text.startswith(word)
        # TODO: Improve context detection (e.g., after pipe, command specific args)

        try:
            if word.startswith('$'):
                yield from self._complete_environment_variable(word)
            elif is_first_word:
                # On the first word, complete commands AND paths
                yield from self._complete_command(word)
                yield from self._complete_path(document)
            else:
                # Otherwise (likely an argument), only complete paths
                yield from self._complete_path(document)
        except Exception as e:
            # Add broad exception handling for debugging completer issues
            # print(f"\nError in get_completions: {type(e).__name__}: {e}\n")
            pass # Avoid crashing the prompt 