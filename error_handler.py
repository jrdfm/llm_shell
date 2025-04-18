from rich.console import Console
from rich.markdown import Markdown
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
        """Format and print error solutions using Rich Markdown."""
        markdown_output = ""
        problem_str = "Unknown issue"
        solution_list = []

        try:
            # Try to parse as JSON first
            if explanation.startswith('{'):
                try:
                    data = json.loads(explanation)
                    if isinstance(data, dict):
                        # Handle nested error_explanation structure
                        if 'error_explanation' in data and isinstance(data['error_explanation'], dict):
                            data = data['error_explanation']

                        problem_str = data.get('problem', problem_str)
                        solution_data = data.get('solution', [])
                        if isinstance(solution_data, list):
                            solution_list = [str(item).strip().lstrip('- ').lstrip('• ') for item in solution_data if item]
                        elif isinstance(solution_data, str): # Handle single string solution
                            solution_list = [item.strip().lstrip('- ').lstrip('• ') for item in solution_data.split('\n') if item.strip()]
                        else:
                            solution_list = ['No specific solution steps provided.']

                except json.JSONDecodeError:
                    # If JSON parsing fails, treat the whole string as the explanation
                    problem_str = "Could not parse explanation data."
                    solution_list = [explanation] # Show raw explanation as a single bullet

            else:
                 # Fallback to text parsing if not JSON
                 parts = explanation.split('\n', 1)
                 if len(parts) > 1:
                     problem_str = parts[0].replace("1. Problem: ", "").strip()
                     solution_text = parts[1].replace("2. Solution:", "").strip()
                     solution_list = [item.strip().lstrip('- ').lstrip('• ') for item in solution_text.split('\n') if item.strip()]
                 else:
                     # If we can't parse into problem/solution, treat as single bullet
                     problem_str = "Explanation"
                     solution_list = [explanation]

            # --- Construct Markdown Output --- 
            markdown_output += f"**Problem:**\n{problem_str}\n\n"
            if solution_list:
                 markdown_output += "**Solution:**\n"
                 for item in solution_list:
                     markdown_output += f"- {item}\n"
            else:
                 markdown_output += "**Solution:**\n- No specific solution steps provided.\n"

        except Exception as e:
            # Ultimate fallback: Show raw explanation in markdown format
            self.console.print(f"\n[yellow]Could not process explanation fully ({e}). Raw content:[/yellow]")
            markdown_output = explanation # Render the raw string as markdown

        # Render the final markdown
        if markdown_output:
            md = Markdown(markdown_output)
            self.console.print("\n") # Add a newline before the markdown block
            self.console.print(md)
        else:
            # Should not happen if logic above is correct, but just in case
             self.console.print("\n[yellow]Explanation:[/yellow] No explanation available.") 