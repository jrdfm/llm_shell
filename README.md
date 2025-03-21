# LLM Shell Assistant

An intelligent shell that combines traditional shell capabilities with natural language processing. Features include command generation from natural language, automatic error explanations, and command completion.

## Prerequisites

- Python 3.8 or higher
- A Google API key for Gemini AI
- GCC compiler (for the C core)

## Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd llm_shell
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install Python dependencies:
```bash
pip install -r requirements.txt
```

4. Set up your Google API key:
```bash
echo "GOOGLE_API_KEY=your_api_key_here" > .env
```

5. Build the C core:
```bash
python setup.py build_ext --inplace
```

## Running the Shell

1. Make sure your virtual environment is activated:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Run the shell:
```bash
./shell.py  # On Windows: python shell.py
```

## Usage

- Regular shell commands work as normal
- Start with # for natural language queries:
  ```bash
  #how do I find large files
  ```
- Add verbosity flags for more information:
  - `-v`: Show the conversion process
  - `-vv`: Show conversion and command explanation
  ```bash
  #how do I copy files with scp -v
  ```

## Features

- Natural language command generation
- Automatic error explanations
- Command completion
- Command history
- Pipeline support
- Persistent cache for faster responses
- Rich formatting and color output 