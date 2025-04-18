#! /usr/bin/env python3
"""
Main shell wrapper module that provides an interactive shell with LLM capabilities.
Uses C core for improved performance.
Natural language queries start with '#'.
"""

import os
import sys
import asyncio
import shlex
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.traceback import install
import json
import subprocess

from core import Shell
from llm import LLMClient
from completions import ShellCompleter
from formatters import ResponseFormatter
from error_handler import ErrorHandler
from models import COMMAND_SCHEMA, CommandResponse
from ui import ShellUI

# Install rich traceback handler
install()

class LLMShell:
    def __init__(self):
        self.console = Console(markup=True, highlight=True)
        self.history_file = os.path.expanduser("~/.llm_shell_history")
        
        # Pre-compute static parts of the prompt
        self.username = os.getenv("USER", "user")
        self.hostname = os.uname().nodename
        
        # Initialize components
        self.core_shell = Shell()
        self._llm_client = None
        self.formatter = ResponseFormatter(self.console)
        self.error_handler = ErrorHandler(self.console, self.llm_client)
        self.ui = ShellUI(self.console)

        self.session = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory(),
            completer=ShellCompleter(core_shell=self.core_shell),
            enable_history_search=True,
        )
        
        # Clear the cache on startup
        if self.llm_client:
            self.llm_client.clear_cache()
    
    @property
    def llm_client(self):
        """Lazy initialization of LLM client."""
        if self._llm_client is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable not set")
            self._llm_client = LLMClient(api_key=api_key)
        return self._llm_client
    
    def get_prompt(self):
        """Generate the shell prompt."""
        cwd = self.core_shell.get_cwd()
        return HTML(f'<ansigreen>{self.username}@{self.hostname}</ansigreen>:<ansiblue>{cwd}</ansiblue>$ ')
    
    async def handle_natural_language_query(self, query: str, verbose: bool, very_verbose: bool):
        """Handle natural language query processing."""
        try:
            response = await self.llm_client.generate_command(query)
            
            # Handle string responses
            if isinstance(response, str):
                response = self._parse_string_response(response, query)
            
            # Ensure response is a dictionary
            if not isinstance(response, dict):
                response = {
                    'command': str(response),
                    'explanation': 'Could not get structured response',
                    'detailed_explanation': 'No detailed explanation available'
                }
            
            # Display command and explanations
            command = str(response.get('command', '')).strip() or f"echo 'Could not generate command for: {query}'"
            self.console.print(f"[bold bright_red]{command}[/bold bright_red]")
            
            if very_verbose and 'detailed_explanation' in response:
                self.formatter.format_detailed_explanation(response.get('detailed_explanation', ''))
            elif verbose and 'explanation' in response:
                self.formatter.format_brief_explanation(response.get('explanation', ''))
            
        except Exception as e:
            await self.error_handler.handle_error(e)
    
    def _parse_string_response(self, response: str, query: str) -> dict:
        """Parse string response into structured format."""
        if response.startswith('{'):
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                pass
        return {
            'command': str(response),
            'explanation': 'Could not parse response',
            'detailed_explanation': 'No detailed explanation available'
        }
    
    async def handle_command(self, query: str):
        """Process and execute a shell command."""
        if not query.strip():
            return
        
        result = None
        exit_code = 0
        error_msg = None
        command_description = "Command" # For error reporting

        try:
            query = query.strip()
            
            if query.startswith('#'):
                parts = query[1:].split()
                verbose = '-v' in parts
                very_verbose = '-vv' in parts
                clean_query = ' '.join([p for p in parts if p not in ['-v', '-vv']])
                await self.handle_natural_language_query(clean_query, verbose, very_verbose)
                return
            
            # --- Built-in Handling (before core execution) ---
            # Handle 'cd' separately as it must affect the parent process
            if query.startswith('cd ') or query == 'cd':
                 try:
                     args = shlex.split(query) # Use shlex even for cd for consistency
                     path = args[1] if len(args) > 1 else os.getenv("HOME", ".")
                     # Use core_shell.cd which updates internal CWD
                     exit_code = self.core_shell.cd(path)
                     if exit_code != 0:
                         # cd itself doesn't return error message, use strerror
                         # (Note: core_shell.cd should ideally set last_error in context)
                         error_msg = os.strerror(abs(exit_code)) # Assuming cd returns -errno
                 except Exception as e:
                     error_msg = f"cd error: {e}"
                     exit_code = 1 # Indicate error
                 # Skip core execution for cd

            # --- Core Execution --- 
            else:
                if '|' in query:
                    # Handle Pipeline
                    command_description = "Pipeline"
                    commands_str = [cmd.strip() for cmd in query.split('|')]
                    # Parse each stage using shlex
                    pipeline_args = [shlex.split(cmd) for cmd in commands_str]
                    # Filter out empty commands that might result from parsing (e.g., "echo hi | | wc")
                    valid_pipeline_args = [args for args in pipeline_args if args]
                    if not valid_pipeline_args:
                         error_msg = "Invalid empty pipeline"
                         exit_code = 1
                    else:
                         result = self.core_shell.execute_pipeline(valid_pipeline_args)
                else:
                    # Handle Single Command
                    command_description = "Command"
                    args = shlex.split(query)
                    if not args: # Handle empty input after parsing
                         return # Do nothing
                    result = self.core_shell.execute(args)
            
            # Process result from core shell execution (if not handled by built-in)
            if result is not None:
                if isinstance(result, tuple):
                    exit_code, core_error_msg = result
                    # Prefer error message from core if available
                    error_msg = core_error_msg if core_error_msg else error_msg
                else:
                    exit_code = result

            # --- Error Handling --- 
            # Handle any error message or non-zero exit code from built-ins or core
            if (error_msg and error_msg.strip()) or exit_code != 0:
                error_text = error_msg.strip() if error_msg else f"{command_description} failed with exit code {exit_code}"
                # Call the async error handler
                await self.error_handler.handle_error(error_text)

        except ValueError as e:
            # Catch shlex parsing errors
            await self.error_handler.handle_error(f"Parsing error: {e}")
        except Exception as e:
            # Catch other unexpected errors during handling/execution
            await self.error_handler.handle_error(f"Execution error: {e}")

    async def run(self):
        """Run the interactive shell."""
        self.ui.show_welcome_banner()
        
        while True:
            try:
                command = await self.session.prompt_async(self.get_prompt)
                if command.strip() == "exit":
                    break
                await self.handle_command(command)
            except EOFError:
                break
            except KeyboardInterrupt:
                continue
            except Exception as e:
                await self.error_handler.handle_error(e)
        
        self.ui.show_goodbye()

def main():
    """Entry point for the shell."""
    shell = LLMShell()
    asyncio.run(shell.run())

if __name__ == "__main__":
    main() 