"""
Main entry point for the LLM shell assistant.
"""

import sys
import asyncio
from .shell import main

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0) 