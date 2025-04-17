# Shell-LLM

An intelligent shell wrapper with LLM-powered features, using Google's Gemini model to enhance the command-line experience.

## Installation

### From PyPI (Recommended)

```bash
pip install shell-llm
```

### From Source

```bash
git clone https://github.com/yourusername/shell-llm.git
cd shell-llm
pip install -e .
```

#### Requirements for Building from Source

If you're building from source, you'll need:

- A C compiler (gcc, clang, or MSVC)
- Python development headers (python-dev or python-devel package)

On Ubuntu/Debian:
```bash
sudo apt-get install gcc python3-dev
```

On Fedora/RHEL/CentOS:
```bash
sudo dnf install gcc python3-devel
```

On macOS (with Homebrew):
```bash
brew install gcc
```

On Windows:
Install Visual Studio Build Tools with C++ support.

## Usage

After installation, you can run Shell-LLM with:

```bash
shell-llm
```

Or import it in your Python code:

```python
# Import modules directly
from llm import LLMClient
from formatters import ResponseFormatter

# Initialize client
client = LLMClient(api_key="your_gemini_api_key")

# Generate a command
result = await client.generate_command("find all pdf files older than 7 days")
print(result['command'])
```

## Configuration

Create a `.env` file with the following variables:

```
GEMINI_API_KEY=your_gemini_api_key_here
MAX_TOKENS=65536
TEMPERATURE=0.7
```

## Features

- Natural language to command generation
- Command explanation 
- Error explanation
- Command auto-completion
- Beautiful output formatting with Markdown support
- Fast C core for shell interaction

## Requirements

- Python 3.8+
- Rich library for terminal formatting
- Google Gemini API access 