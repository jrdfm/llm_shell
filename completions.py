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

    def _extract_path_prefix(self, document):
        """Extract the potential path string immediately before the cursor."""
        text = document.text_before_cursor
        # Find the start of the current word/path segment
        start_index = len(text)
        while start_index > 0 and not text[start_index - 1].isspace():
            start_index -= 1
        return text[start_index:]

    def _complete_path(self, document):
        """Yield completions for file/directory paths.
           Handles: ~, /path, ./path, ../path, partial_name
        """
        path_prefix = self._extract_path_prefix(document)
        # print(f"\nCompleting path prefix: '{path_prefix}'") # Debug: COMMENTED

        # Determine the directory to search in and the partial name to match
        if not path_prefix or path_prefix.endswith('/'):
            # If prefix is empty or ends with /, list contents of the directory
            path = os.path.expanduser(path_prefix or '.') # Expand ~ or use CWD
            if not os.path.isabs(path):
                dir_name = os.path.join(self.core_shell.get_cwd(), path)
            else:
                dir_name = path
            dir_name = os.path.normpath(dir_name)
            partial_name = ''
        else:
            # Completing a partial name
            path = os.path.expanduser(path_prefix) # Expand ~
            dir_name = os.path.dirname(path)
            partial_name = os.path.basename(path)

            if not dir_name: # No directory part, complete in CWD
                dir_name = self.core_shell.get_cwd()
            elif not os.path.isabs(dir_name):
                # Relative path, join with CWD
                dir_name = os.path.join(self.core_shell.get_cwd(), dir_name)
            
            dir_name = os.path.normpath(dir_name)

        # print(f"  Dir: '{dir_name}', Partial: '{partial_name}'") # Debug: COMMENTED

        try:
            # Ensure the base directory exists
            if not os.path.isdir(dir_name):
                # print(f"  Directory not found: {dir_name}") # Debug: COMMENTED
                return

            # Use glob to find matches for the partial name within the directory
            pattern = os.path.join(dir_name, partial_name + '*')
            # print(f"  Globbing: {pattern}") # Debug: COMMENTED

            for match in glob.glob(pattern):
                basename = os.path.basename(match) # Get only the filename/dirname part
                # print(f"    Match found: {match}, Basename: {basename}") # Debug: COMMENTED
                
                # The text to be inserted completes the partial name
                # If partial_name was '', completion is the full basename
                # If partial_name was 'sub_d', completion is 'sub_dir'
                completion_text = basename
                display_text = basename # How it appears in the completion list
                
                # The start position is relative to the beginning of the word/path prefix
                start_pos = -len(partial_name)

                try:
                    # Add slash if it's a directory
                    if os.path.isdir(match):
                        completion_text += '/'
                        display_text += '/' # Also show slash in display
                except OSError:
                    pass 

                # print(f"      Yielding: text='{completion_text}', start={start_pos}, display='{display_text}'") # Debug: COMMENTED
                yield Completion(
                    completion_text,
                    start_position=start_pos,
                    display=display_text
                )
        except OSError as e:
            # print(f"\nOSError during path completion: {e}\n") # Debug: COMMENTED
            pass
        except Exception as e:
            # print(f"\nUnexpected error during path completion: {e}\n") # Debug: COMMENTED
            pass

    def get_completions(self, document, complete_event):
        """Determine completion type and yield results."""
        text = document.text_before_cursor
        word = document.get_word_before_cursor() # Still useful for some checks
        path_prefix = self._extract_path_prefix(document) # Get the full path segment

        # Basic context detection: Is it the first word?
        stripped_text = text.lstrip()
        is_first_word = not stripped_text or stripped_text.startswith(path_prefix)
        # TODO: Improve context detection (e.g., after pipe, command specific args)

        try:
            if path_prefix.startswith('$'):
                # Pass the actual prefix including $ for env var completion
                yield from self._complete_environment_variable(path_prefix)
            elif is_first_word:
                # On the first word, complete commands AND paths
                yield from self._complete_command(word) # Command completion uses the std word
                yield from self._complete_path(document)
            else:
                # Otherwise (likely an argument), only complete paths
                yield from self._complete_path(document)
        except Exception as e:
            # print(f"\nError in get_completions: {type(e).__name__}: {e}\n") # Debug: COMMENTED
            pass # Avoid crashing the prompt 