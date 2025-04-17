from rich.console import Console
from rich.markdown import Markdown
import textwrap

class ResponseFormatter:
    def __init__(self, console: Console):
        self.console = console
        self.wrapper = textwrap.TextWrapper(
            width=80,
            expand_tabs=True,
            replace_whitespace=True,
            break_on_hyphens=False
        )

    def format_detailed_explanation(self, detailed: str) -> None:
        """Format and print detailed explanations using markdown."""
        # Convert text to proper markdown if it's not already
        markdown_text = self._ensure_markdown_format(detailed)
        
        # Add title if not present
        if not markdown_text.strip().startswith("# "):
            markdown_text = f"# Detailed Explanation\n\n{markdown_text}"
            
        # Render the markdown
        md = Markdown(markdown_text)
        self.console.print(md)

    def _ensure_markdown_format(self, text: str) -> str:
        """Convert traditional formatting to markdown if needed."""
        # Convert **Section Headers** to markdown headings
        lines = []
        for line in text.split('\n'):
            line = line.rstrip()
            # Convert section headers
            if line.strip().startswith('**') and line.strip().endswith('**'):
                header_text = line.strip().strip('*').strip()
                lines.append(f"## {header_text}")
            # Keep existing markdown headers
            elif line.strip().startswith(('#')):
                lines.append(line)
            # Keep existing bullet points (already markdown compatible)
            elif line.strip().startswith(('* ', '- ', '• ')):
                # Standardize bullet character
                indent = len(line) - len(line.lstrip())
                content = line.strip()[2:].strip()
                # Calculate level based on indentation
                level = indent // 2
                # Add proper indentation for nested lists
                prefix = "  " * level
                lines.append(f"{prefix}- {content}")
            # Regular text
            else:
                lines.append(line)
        
        return "\n".join(lines)

    def format_brief_explanation(self, explanation: str) -> None:
        """Format and print brief explanations using markdown."""
        # Add a heading and render as markdown
        markdown_text = f"# Explanation\n\n{explanation}"
        md = Markdown(markdown_text)
        self.console.print(md) 