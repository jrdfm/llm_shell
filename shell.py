#! /usr/bin/env python3
"""
Main shell wrapper module that provides an interactive shell with LLM capabilities.
Uses C core for improved performance.
Natural language queries start with '#'.
"""

import os
import sys
import asyncio
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
        
        self.session = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory(),
            completer=ShellCompleter(),
            enable_history_search=True,
        )
        
        # Initialize components
        self.core_shell = Shell()
        self._llm_client = None
        self.formatter = ResponseFormatter(self.console)
        self.error_handler = ErrorHandler(self.console, self.llm_client)
        self.ui = ShellUI(self.console)
        
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
    
    async def execute_shell_command(self, command: str):
        """Execute a shell command using the C core."""
        try:
            # Execute through C core and get result and error if any
            result = self.core_shell.execute(command)
            if isinstance(result, tuple):
                exit_code, error_msg = result
            else:
                exit_code, error_msg = result, None
            
            # Handle any error message or non-zero exit code
            if (error_msg and error_msg.strip()) or exit_code != 0:
                # Get explanation and solution
                error_text = error_msg.strip() if error_msg else f"Command failed with exit code {exit_code}"
                await self.error_handler.handle_error(error_text)
            return exit_code == 0
        except Exception as e:
            await self.error_handler.handle_error(str(e))
            return False
    
    async def execute_pipeline(self, commands):
        """Execute a pipeline of commands using the C core."""
        try:
            # Execute through C core and get result and error if any
            result = self.core_shell.execute_pipeline(commands)
            if isinstance(result, tuple):
                exit_code, error_msg = result
            else:
                exit_code, error_msg = result, None
            
            # Handle any error message or non-zero exit code
            if (error_msg and error_msg.strip()) or exit_code != 0:
                # Get explanation and solution
                error_text = error_msg.strip() if error_msg else f"Pipeline failed with exit code {exit_code}"
                await self.error_handler.handle_error(error_text)
            return exit_code == 0
        except Exception as e:
            await self.error_handler.handle_error(str(e))
            return False
    
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
        
        try:
            query = query.strip()
            
            if query.startswith('#'):
                parts = query[1:].split()
                verbose = '-v' in parts
                very_verbose = '-vv' in parts
                clean_query = ' '.join([p for p in parts if p not in ['-v', '-vv']])
                await self.handle_natural_language_query(clean_query, verbose, very_verbose)
                return
            
            if query.startswith('cd ') or query == 'cd':
                path = query.split(None, 1)[1] if ' ' in query else os.getenv("HOME")
                self.core_shell.cd(path)
                return
            
            if '|' in query:
                commands = [cmd.strip() for cmd in query.split('|')]
                await self.execute_pipeline(commands)
            else:
                await self.execute_shell_command(query)
            
        except Exception as e:
            await self.error_handler.handle_error(e)
    
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