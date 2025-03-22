from rich.console import Console

class ShellUI:
    def __init__(self, console: Console):
        self.console = console

    def show_welcome_banner(self):
        """Display the welcome banner and instructions."""
        self.console.print("""[bold cyan]
    ╔══════════════════════════════════════╗
    ║  ┌─┐┬ ┬┌─┐┬  ┬    ╔═╗╔═╗╔═╗╦╔═╗╔╦╗ ║
    ║  └─┐├─┤├┤ │  │    ╠═╣╚═╗╚═╗║╚═╗ ║  ║
    ║  └─┘┴ ┴└─┘┴─┘┴─┘  ╩ ╩╚═╝╚═╝╩╚═╝ ╩  ║
    ║                                      ║
    ║     Your AI-Powered Shell Helper     ║
    ╚══════════════════════════════════════╝[/bold cyan]
""")
        self.show_instructions()

    def show_instructions(self):
        """Display usage instructions."""
        self.console.print("[bold]Welcome to LLM Shell Assistant![/bold]")
        self.console.print("Type 'exit' or press Ctrl+D to exit.")
        self.console.print("Start your query with # to use natural language")
        self.console.print("Add -v for brief explanation")
        self.console.print("Add -vv for detailed explanation")
        self.console.print("Example: #how do I copy files with scp -vv\n")

    def show_goodbye(self):
        """Display goodbye message."""
        self.console.print("\nGoodbye!") 