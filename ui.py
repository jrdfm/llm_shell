from rich.console import Console

class ShellUI:
    def __init__(self, console: Console):
        self.console = console

    def show_welcome_banner(self):
        """Display the welcome banner and instructions."""
        self.console.print("""[bold cyan]
╔════════════════════════════════════════════════╗
║   _     _     __  __    _____ _          _ _   ║
║  | |   | |   |  \/  |  / ____| |        | | |  ║
║  | |   | |   | \  / | | (___ | |__   ___| | |  ║
║  | |   | |   | |\/| |  \___ \| '_ \ / _ \ | |  ║
║  | |___| |___| |  | |  ____) | | | |  __/ | |  ║
║  |_____|_____|_|  |_| |_____/|_| |_|\___|_|_|  ║
║                                                ║
║        Your AI-Powered Shell Helper            ║
╚════════════════════════════════════════════════╝[/bold cyan]
""")
        self.show_instructions()

    def show_instructions(self):
        """Display usage instructions."""
        self.console.print("[bold]Welcome to LLM Shell Assistant![/bold]")
        self.console.print("• Type 'exit' or press Ctrl+D to exit")
        self.console.print("• Start your query with # to use natural language")
        self.console.print("• Add -v for brief explanation")
        self.console.print("• Add -vv for detailed explanation")
        self.console.print("• Press Tab for smart completions")
        self.console.print("\nExample: #how do I copy files with scp -vv\n")

    def show_goodbye(self):
        """Display goodbye message."""
        self.console.print("\nGoodbye!") 