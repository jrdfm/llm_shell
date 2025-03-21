"""
Command completion module for shell command suggestions.
"""

from prompt_toolkit.completion import Completer, Completion

class ShellCompleter(Completer):
    def __init__(self):
        # Common commands for fast completion
        self.commands = {
            'ls', 'cd', 'pwd', 'cat', 'echo', 'mkdir', 'rm', 'cp', 'mv',
            'grep', 'find', 'ps', 'kill', 'top', 'df', 'du', 'tar',
            'git', 'python', 'pip', 'ssh', 'scp'
        }
    
    def get_completions(self, document, complete_event):
        """Get command completions."""
        word = document.get_word_before_cursor()
        
        # Complete commands
        if not document.text[:document.cursor_position].strip():
            for cmd in self.commands:
                if cmd.startswith(word):
                    yield Completion(
                        cmd,
                        start_position=-len(word)
                    )
        
        # Complete paths if word starts with / or ./
        elif word.startswith(('/','./')) or '../' in word:
            import os
            path = word
            if path.startswith('./'):
                path = path[2:]
            elif path.startswith('/'):
                path = path[1:]
            
            try:
                directory = os.path.dirname(path) or '.'
                prefix = os.path.basename(path)
                
                if os.path.isdir(directory):
                    for name in os.listdir(directory):
                        if name.startswith(prefix):
                            full = os.path.join(directory, name)
                            if os.path.isdir(full):
                                name += '/'
                            yield Completion(
                                name,
                                start_position=-len(prefix)
                            )
            except OSError:
                pass 