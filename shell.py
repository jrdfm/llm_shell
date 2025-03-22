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
import textwrap
import json
from pydantic import BaseModel
from google import genai

from core import Shell  # Import our C core implementation
from llm import LLMClient
from completions import ShellCompleter

# Install rich traceback handler
install()

COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute"
        },
        "explanation": {
            "type": "string", 
            "description": "Brief explanation of what the command does"
        },
        "detailed_explanation": {
            "type": "string",
            "description": "Detailed explanation including command options, examples, and common use cases"
        }
    },
    "required": ["command", "explanation", "detailed_explanation"],
    "propertyOrdering": ["command", "explanation", "detailed_explanation"]
}

class CommandResponse(BaseModel):
    command: str
    explanation: str
    detailed_explanation: str

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
        
        # Initialize our C core shell
        self.core_shell = Shell()
        self._llm_client = None
        
        # Clear the cache on startup to ensure we're using the correct model
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
        cwd = self.core_shell.get_cwd()  # Use C core to get current directory
        return HTML(f'<ansigreen>{self.username}@{self.hostname}</ansigreen>:<ansiblue>{cwd}</ansiblue>$ ')
    
    async def execute_shell_command(self, command: str):
        """Execute a shell command using the C core."""
        try:
            # Use C core for command execution
            result = self.core_shell.execute(command)
            if result != 0:  # Command failed
                # Get the error output from stderr
                error_msg = os.popen(f"{command} 2>&1").read().strip()
                if error_msg:
                    explanation = await self.llm_client.explain_error(error_msg)
                    parts = explanation.split('\n', 1)
                    if len(parts) > 1:
                        # Clean up any accidental numbering
                        solution = parts[1].replace("2. ", "").replace("- ", "• ").strip()
                        self.console.print("\n[bold magenta]How to fix:[/bold magenta]")
                        self.console.print(f"[bright_yellow]{solution}[/bright_yellow]")
                    else:
                        self.console.print(f"[bright_yellow]{parts[0]}[/bright_yellow]")
            return result == 0
        except Exception as e:
            error_msg = str(e)
            explanation = await self.llm_client.explain_error(error_msg)
            parts = explanation.split('\n', 1)
            if len(parts) > 1:
                # Clean up any accidental numbering
                solution = parts[1].replace("2. ", "").replace("- ", "• ").strip()
                self.console.print(f"[green]Solution:[/green] {solution}")
            return False
    
    async def execute_pipeline(self, commands):
        """Execute a pipeline of commands using the C core."""
        try:
            result = self.core_shell.execute_pipeline(commands)
            if result != 0:  # Pipeline failed
                # Get the error output from stderr
                cmd = " | ".join(commands)
                error_msg = os.popen(f"{cmd} 2>&1").read().strip()
                if error_msg:
                    explanation = await self.llm_client.explain_error(error_msg)
                    parts = explanation.split('\n', 1)
                    if len(parts) > 1:
                        # Clean up any accidental numbering
                        solution = parts[1].replace("2. ", "").replace("- ", "• ").strip()
                        self.console.print("\n[bold magenta]How to fix:[/bold magenta]")
                        self.console.print(f"[bright_yellow]{solution}[/bright_yellow]")
                    else:
                        self.console.print(f"[bright_yellow]{parts[0]}[/bright_yellow]")
            return result == 0
        except Exception as e:
            error_msg = str(e)
            explanation = await self.llm_client.explain_error(error_msg)
            parts = explanation.split('\n', 1)
            if len(parts) > 1:
                # Clean up any accidental numbering
                solution = parts[1].replace("2. ", "").replace("- ", "• ").strip()
                self.console.print(f"[green]Solution:[/green] {solution}")
            return False
    
    async def handle_command(self, query: str):
        """Process and execute a shell command."""
        if not query.strip():
            return
        
        try:
            query = query.strip()
            
            # Check if this is a natural language query (starts with #)
            if query.startswith('#'):
                parts = query[1:].split()
                verbose = '-v' in parts
                very_verbose = '-vv' in parts
                
                # Clean query by removing verbosity flags
                clean_query = ' '.join([p for p in parts if p not in ['-v', '-vv']])
                
                try:
                    # Get structured response from LLM
                    response = await self.llm_client.generate_command(clean_query)
                    
                    # Handle string responses (error cases)
                    if isinstance(response, str):
                        if response.startswith('{'):
                            try:
                                response = json.loads(response)
                            except json.JSONDecodeError:
                                response = {
                                    'command': str(response),
                                    'explanation': 'Could not parse response',
                                    'detailed_explanation': 'No detailed explanation available'
                                }
                        else:
                            response = {
                                'command': str(response),
                                'explanation': 'Could not get structured response',
                                'detailed_explanation': 'No detailed explanation available'
                            }
                    
                    # Ensure response is a dictionary with the proper fields
                    if not isinstance(response, dict):
                        response = {
                            'command': str(response),
                            'explanation': 'Could not get structured response',
                            'detailed_explanation': 'No detailed explanation available'
                        }
                    
                    # Extract command from structured response
                    command = str(response.get('command', '')).strip()
                    if not command:
                        command = f"echo 'Could not generate command for: {clean_query}'"
                    
                    self.console.print(f"[bold bright_red]{command}[/bold bright_red]")
                    
                    # Show explanation based on verbosity level
                    if very_verbose and 'detailed_explanation' in response:
                        self.console.print(f"[bold green]Detailed Explanation:[/bold green]")
                        detailed = str(response.get('detailed_explanation', '')).strip()
                        if detailed:
                            for line in detailed.split('\n'):
                                self.console.print(f"[green_yellow]{line.strip()}[/green_yellow]")
                    elif verbose and 'explanation' in response:
                        self.console.print(f"[bold green]Explanation:[/bold green]")
                        explanation = str(response.get('explanation', '')).strip()
                        if explanation:
                            for line in explanation.split('\n'):
                                self.console.print(f"[green_yellow]{line.strip()}[/green_yellow]")
                    
                    return
                
                except Exception as e:
                    self.console.print(f"[red]Error generating command: {str(e)}[/red]")
                    # Try to provide a helpful error message
                    explanation = await self.llm_client.explain_error(str(e))
                    if explanation:
                        self.console.print(f"[bright_yellow]{explanation}[/bright_yellow]")
                    return
            
            # Handle cd command specially
            if query.startswith('cd ') or query == 'cd':
                path = query.split(None, 1)[1] if ' ' in query else os.getenv("HOME")
                self.core_shell.cd(path)
                return
            
            # For all other commands, execute directly
            if '|' in query:
                commands = [cmd.strip() for cmd in query.split('|')]
                await self.execute_pipeline(commands)
            else:
                await self.execute_shell_command(query)
            
        except Exception as e:
            self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
            explanation = await self.llm_client.explain_error(str(e))
            parts = explanation.split('\n', 1)
            if len(parts) > 1:
                # Clean up any accidental numbering
                solution = parts[1].replace("2. ", "").replace("- ", "• ").strip()
                self.console.print(f"[green]Solution:[/green] {solution}")
    
    async def run(self):
        """Run the interactive shell."""
        # ASCII Art welcome banner
        self.console.print("""[bold cyan]
    ╔══════════════════════════════════════╗
    ║  ┌─┐┬ ┬┌─┐┬  ┬    ╔═╗╔═╗╔═╗╦╔═╗╔╦╗ ║
    ║  └─┐├─┤├┤ │  │    ╠═╣╚═╗╚═╗║╚═╗ ║  ║
    ║  └─┘┴ ┴└─┘┴─┘┴─┘  ╩ ╩╚═╝╚═╝╩╚═╝ ╩  ║
    ║                                      ║
    ║     Your AI-Powered Shell Helper     ║
    ╚══════════════════════════════════════╝[/bold cyan]
""")
        self.console.print("[bold]Welcome to LLM Shell Assistant![/bold]")
        self.console.print("Type 'exit' or press Ctrl+D to exit.")
        self.console.print("Start your query with # to use natural language")
        self.console.print("Add -v for brief explanation")
        self.console.print("Add -vv for detailed explanation")
        self.console.print("Example: #how do I copy files with scp -vv\n")
        
        while True:
            try:
                command = await self.session.prompt_async(
                    self.get_prompt,
                )
                
                if command.strip() == "exit":
                    break
                
                await self.handle_command(command)
                
            except EOFError:
                break
            except KeyboardInterrupt:
                continue
            except Exception as e:
                self.console.print(f"[bold red]Error:[/bold red] {str(e)}")
        
        self.console.print("\nGoodbye!")

    def _show_welcome(self):
        self.console.print(
            "[bold green]Natural Language Shell[/green]\n"
            "Start commands with [cyan]#[/cyan] to use natural language\n"
            "Add [cyan]-v[/cyan] to see command explanation\n"
            "Example: [cyan]#list large files -v[/cyan]"
        )

def main():
    """Entry point for the shell."""
    shell = LLMShell()
    asyncio.run(shell.run())

if __name__ == "__main__":
    main() 