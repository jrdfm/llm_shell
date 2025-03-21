"""
Utility functions for the LLM shell assistant.
"""

import os
import subprocess
from typing import Tuple, Optional

def execute_command(command: str) -> Tuple[str, Optional[str]]:
    """
    Execute a shell command and return its output and error (if any).
    
    Args:
        command: The shell command to execute
    
    Returns:
        Tuple of (output, error)
    """
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        output, error = process.communicate()
        return output.strip(), error.strip() if error else None
    
    except subprocess.CalledProcessError as e:
        return "", str(e)
    except Exception as e:
        return "", str(e)

def get_command_history(limit: int = 10) -> list[str]:
    """
    Get recent command history from the shell.
    
    Args:
        limit: Maximum number of history items to return
    
    Returns:
        List of recent commands
    """
    history_file = os.path.expanduser("~/.bash_history")
    try:
        with open(history_file, "r") as f:
            history = f.readlines()
        return [cmd.strip() for cmd in history[-limit:]]
    except Exception:
        return []

def get_environment_context() -> dict:
    """
    Get relevant environment information for context.
    
    Returns:
        Dictionary containing environment information
    """
    return {
        "cwd": os.getcwd(),
        "home": os.path.expanduser("~"),
        "user": os.getenv("USER"),
        "shell": os.getenv("SHELL"),
        "path": os.getenv("PATH"),
        "term": os.getenv("TERM")
    } 