from rich.console import Console
import json

class ErrorHandler:
    def __init__(self, console: Console, llm_client):
        self.console = console
        self.llm_client = llm_client

    async def handle_error(self, error_msg: str) -> None:
        """Handle and display errors with explanations."""
        # Always show error message first
        self.console.print(f"[bold red]Error:[/bold red] {error_msg}")
        
        # Then get and show the solution
        explanation = await self.llm_client.explain_error(error_msg)
        self._print_error_solution(explanation)

    def _print_error_solution(self, explanation: str) -> None:
        """Format and print error solutions."""
        try:
            # Try to parse as JSON first
            if explanation.startswith('{'):
                try:
                    data = json.loads(explanation)
                    if isinstance(data, dict):
                        # Handle nested error_explanation structure
                        if 'error_explanation' in data:
                            data = data['error_explanation']
                        
                        # Extract problem and solution
                        problem = data.get('problem', '')
                        solution = data.get('solution', [])
                        
                        # Print problem and solution
                        if problem:
                            self.console.print("\n[yellow]Problem:[/yellow] " + problem)
                        
                        if solution:
                            self.console.print("\n[green]Solution:[/green]")
                            if isinstance(solution, list):
                                for item in solution:
                                    # Clean up bullet points
                                    item = item.strip().lstrip('- ').lstrip('• ')
                                    self.console.print(f"  • {item}")
                            else:
                                self.console.print(f"  • {solution}")
                        return
                except json.JSONDecodeError:
                    pass
            
            # Fallback to text parsing if not JSON
            parts = explanation.split('\n', 1)
            if len(parts) > 1:
                problem = parts[0].replace("1. Problem: ", "").strip()
                solution = parts[1].replace("2. Solution:", "").strip()
                
                # Always show both problem and solution
                self.console.print("\n[yellow]Problem:[/yellow] " + problem)
                self.console.print("\n[green]Solution:[/green]")
                
                for line in solution.split('\n'):
                    line = line.strip()
                    if line:
                        line = line.lstrip('- ').lstrip('• ')
                        self.console.print(f"  • {line}")
            else:
                # If we can't parse into problem/solution, show as explanation
                self.console.print(f"\n[yellow]Explanation:[/yellow] {explanation}")
        except Exception:
            # Ultimate fallback
            self.console.print(f"\n[yellow]Explanation:[/yellow] {explanation}") 