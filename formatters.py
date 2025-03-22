from rich.console import Console
import textwrap
from typing import List

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
        """Format and print detailed explanations with proper structure."""
        self.console.print("[bold green]Detailed Explanation:[/bold green]")
        
        lines = detailed.split('\n')
        current_section = None
        current_indent = 0
        
        for line in lines:
            if not line.strip():
                if current_section:
                    self.console.print()
                    current_section = None
                continue
            
            clean_line = line.strip()
            indent = len(line) - len(line.lstrip())
            
            # Detect section headers
            if clean_line.startswith('**') and clean_line.endswith('**'):
                current_section = clean_line.strip('*').strip()
                self.console.print(f"\n[bold green_yellow]{current_section}[/bold green_yellow]")
                continue
            
            # Handle bullet points and their content
            if clean_line.startswith(('* ', '- ', '• ')):
                current_indent = indent
                bullet = '•' if indent < 4 else '◦'
                content = clean_line[2:].strip()
                
                # Calculate proper indentation
                padding = '  ' * (indent // 2 + 1)
                
                # Set up wrapper for this bullet point
                self.wrapper.initial_indent = f"{padding}{bullet} "
                self.wrapper.subsequent_indent = f"{padding}   "
                
                # Wrap and print the bullet point
                wrapped = self.wrapper.fill(content)
                self.console.print(f"[green_yellow]{wrapped}[/green_yellow]")
            
            # Handle continuation lines
            elif current_indent > 0:
                padding = '  ' * (current_indent // 2 + 2)
                self.wrapper.initial_indent = padding
                self.wrapper.subsequent_indent = padding
                wrapped = self.wrapper.fill(clean_line)
                self.console.print(f"[green_yellow]{wrapped}[/green_yellow]")
            
            # Regular paragraphs
            else:
                self.wrapper.initial_indent = '  '
                self.wrapper.subsequent_indent = '  '
                wrapped = self.wrapper.fill(clean_line)
                self.console.print(f"[green_yellow]{wrapped}[/green_yellow]")

    def _split_sections(self, text: str) -> List[str]:
        """Split text into logical sections, preserving empty lines."""
        sections = []
        current_section = []
        
        for line in text.split('\n'):
            if not line.strip() and current_section:
                sections.append('\n'.join(current_section))
                sections.append('')  # Keep empty line
                current_section = []
            else:
                current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        return sections

    def _get_indent_level(self, line: str) -> int:
        """Calculate the indentation level of a line."""
        return len(line) - len(line.lstrip())

    def _format_bullet_section(self, lines: List[str]) -> None:
        """Format a bullet point and its sub-points."""
        base_indent = self._get_indent_level(lines[0])
        
        for line in lines:
            indent = self._get_indent_level(line) - base_indent
            clean_line = line.strip()
            
            if not clean_line:
                continue
                
            if clean_line.startswith(('* ', '- ', '• ')):
                bullet = '•' if indent == 0 else '◦'
                content = clean_line[2:].strip()
                padding = '  ' * (indent + 1)
                self.console.print(f"[green_yellow]{padding}{bullet} {content}[/green_yellow]")
            else:
                # Continuation of previous bullet point
                padding = '  ' * (indent + 2)
                wrapped = self.wrapper.fill(clean_line)
                for wrapped_line in wrapped.split('\n'):
                    self.console.print(f"[green_yellow]{padding}{wrapped_line}[/green_yellow]")

    def _format_paragraph(self, lines: List[str], base_indent: int) -> None:
        """Format a regular paragraph with proper indentation."""
        text = ' '.join(line.strip() for line in lines if line.strip())
        self.wrapper.initial_indent = '  ' * (base_indent // 2 + 1)
        self.wrapper.subsequent_indent = self.wrapper.initial_indent
        
        wrapped = self.wrapper.fill(text)
        for line in wrapped.split('\n'):
            self.console.print(f"[green_yellow]{line}[/green_yellow]")

    def format_brief_explanation(self, explanation: str) -> None:
        """Format and print brief explanations."""
        self.console.print("[bold green]Explanation:[/bold green]")
        self.wrapper.initial_indent = '  '
        self.wrapper.subsequent_indent = '  '
        wrapped = self.wrapper.fill(explanation)
        self.console.print(f"[green_yellow]{wrapped}[/green_yellow]") 