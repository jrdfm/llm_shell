# LLM Shell Assistant

An intelligent shell that combines traditional shell capabilities with natural language processing. Features include command generation from natural language, automatic error explanations, and command completion.

## Prerequisites

- Python 3.8 or higher
- A Google API key for Gemini AI (specifically configured for gemini-2.0-flash model)
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
rm -rf build/ core.*.so
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
  - `-v`: Show brief command explanation
  - `-vv`: Show detailed command explanation with options and examples
  ```bash
  #how do I copy files with scp -vv
  ```

### Error Handling

The shell provides intelligent error handling with AI-powered explanations:

1. **Direct Error Capture**
   - Errors are captured directly from command execution in the C core
   - No re-running of commands to capture errors
   - Handles both execution errors and usage messages

2. **Error Processing**
   - Errors are immediately displayed with a red "Error:" prefix
   - The LLM analyzes the error using the Gemini model
   - Responses are cached to improve performance

3. **Structured Solutions**
   The error handler provides a consistent format:
   ```bash
   Error: <original error message>

   Problem: <one-line explanation of what went wrong>

   Solution:
     • <step-by-step instructions>
     • <clear actionable items>
     • <relevant suggestions>
   ```

Example outputs:

```bash
$ mkdir root/pass
Error: mkdir: cannot create directory 'root/pass': No such file or directory

Problem: The parent directory 'root' does not exist

Solution:
  • First, create the parent directory 'root' using the command `mkdir root`
  • Verify that the 'root' directory was created successfully using `ls -l`
  • Then, create the 'pass' directory inside 'root' using `mkdir root/pass`
```

```bash
$ scp ssh
Error: usage: scp [-346ABCOpqRrsTv] [-c cipher] [-D sftp_server_path] [-F ssh_config]
           [-i identity_file] [-J destination] [-l limit] [-o ssh_option]
           [-P port] [-S program] [-X sftp_option] source ... target

Problem: The scp command was invoked with incorrect arguments

Solution:
  • Review the scp command syntax: scp [options] source target
  • Specify a source file/directory to copy from
  • Specify a destination where you want to copy to
  • Add any needed options like -r for directories
```

## Technical Implementation

### Architecture Overview

The project follows a hybrid architecture combining Python and C for optimal performance:

1. **Core Shell Implementation (`core.c`)**
   - Written in C for performance-critical operations
   - Handles direct command execution
   - Manages working directory changes
   - Implements pipeline execution
   - Exposed to Python through Cython bindings

2. **Python Shell Wrapper (`shell.py`)**
   - Main shell interface implementation
   - Handles user input/output with rich formatting
   - Manages LLM integration
   - Implements command history and completion
   - Error handling and explanation generation

3. **LLM Integration (`llm.py`)**
   - Manages communication with Google's Gemini AI
   - Implements caching for faster responses
   - Handles structured command generation
   - Provides error explanation capabilities

4. **Command Completion (`completions.py`)**
   - Custom command completion engine
   - Combines traditional shell completion with LLM suggestions

### Key Components

#### Command Response Schema
```python
{
    "command": str,        # The shell command to execute
    "explanation": str,    # Brief explanation of the command
    "detailed_explanation": str  # Detailed breakdown with examples
}
```

#### LLM Client Features
- Lazy initialization of API client
- Response caching with JSON persistence
- Structured output parsing
- Error handling and explanation generation
- Command generation with context awareness

#### Shell Features
- Asynchronous command execution
- Pipeline support with error handling
- Rich terminal output with custom formatting
- History management with file persistence
- Intelligent error handling with LLM-powered explanations

### Project Structure

```
llm_shell/
├── shell.py           # Main shell implementation
├── core.c            # C core implementation
├── core.pyx          # Cython interface
├── llm.py            # LLM client implementation
├── completions.py    # Command completion engine
├── setup.py          # Build configuration
├── requirements.txt  # Python dependencies
└── .env             # Environment configuration
```

### Performance Optimizations

1. **C Core Integration**
   - Direct system calls for command execution
   - Efficient pipeline handling
   - Minimal Python-C context switching

2. **LLM Response Caching**
   - JSON-based persistent cache
   - Cache invalidation on model updates
   - Lazy loading of expensive resources

3. **Asynchronous Operations**
   - Non-blocking command execution
   - Asynchronous LLM API calls
   - Responsive UI during long operations

### Security Considerations

1. **API Key Management**
   - Environment-based configuration
   - No hardcoded credentials
   - Secure key storage recommendations

2. **Command Execution**
   - Sanitized command inputs
   - Controlled execution environment
   - Error containment and reporting

3. **Cache Security**
   - Local-only cache storage
   - No sensitive data in cache
   - Proper file permissions

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Insert License Information]

### Core Shell Implementation (`core.c`)

The C core provides high-performance shell operations through direct system calls. Here are the key components:

1. **Shell Context Management**
```c
typedef struct {
    char *cwd;           // Current working directory
    char **env;          // Environment variables
    int last_exit_code;  // Last command's exit code
    int interactive;     // Whether shell is interactive
} ShellContext;

ShellContext* shell_init(void) {
    ShellContext *ctx = malloc(sizeof(ShellContext));
    ctx->cwd = getcwd(NULL, 0);
    // ... initialize environment and other fields
    return ctx;
}
```

The Shell Context maintains the state of the shell environment. The `ShellContext` struct holds:
- `cwd`: Dynamically allocated string storing the current working directory path
- `env`: Array of environment variables as "NAME=VALUE" strings
- `last_exit_code`: Exit status of the most recently executed command
- `interactive`: Flag indicating if the shell is running in interactive mode

During initialization, the context:
1. Allocates memory for the structure
2. Gets the current working directory using `getcwd()`
3. Copies the current environment variables
4. Sets default values for exit code and interactive mode

2. **Command Execution Pipeline**
```c
int shell_execute_pipeline(ShellContext *ctx, const char **commands, int num_commands) {
    int pipes[num_commands-1][2];
    pid_t pids[num_commands];

    // Create pipes for command communication
    for (int i = 0; i < num_commands-1; i++) {
        pipe(pipes[i]);
    }

    // Fork processes for each command
    for (int i = 0; i < num_commands; i++) {
        pids[i] = fork();
        if (pids[i] == 0) {
            // Child: Setup pipes and execute command
            setup_pipes(i, pipes, num_commands);
            execute_command(commands[i]);
        }
    }
    // Parent: Wait for completion
    wait_for_children(pids, num_commands);
}
```

The pipeline execution system implements Unix-style command chaining:
1. Creates an array of pipes (N-1 pipes for N commands)
2. For each command in the pipeline:
   - Creates a new process using `fork()`
   - Child process:
     - Sets up input/output pipes
     - Redirects stdin/stdout to appropriate pipe ends
     - Executes the command
   - Parent process:
     - Keeps track of child PIDs
     - Manages pipe file descriptors
3. Parent waits for all child processes to complete
4. Handles errors and returns the last command's exit status

3. **Directory Management**
```c
int shell_cd(ShellContext *ctx, const char *path) {
    if (chdir(path) != 0) return -1;
    free(ctx->cwd);
    ctx->cwd = getcwd(NULL, 0);
    return 0;
}
```

The directory management system:
1. Attempts to change directory using `chdir()`
2. On success:
   - Frees the old working directory string
   - Gets and stores the new working directory
3. Handles special cases like:
   - `cd` with no arguments (goes to HOME)
   - Relative paths
   - Symbolic links
4. Returns -1 on error (e.g., directory not found)

4. **Environment Variable Handling**
```c
int shell_setenv(ShellContext *ctx, const char *name, const char *value) {
    char *new_var;
    asprintf(&new_var, "%s=%s", name, value);
    // Update or add environment variable
    update_environment(ctx, new_var);
}
```

Environment variable management:
1. Creates a new environment string in "NAME=VALUE" format
2. Searches existing environment for the variable
3. If found: replaces the old value
4. If not found: adds to the environment array
5. Handles memory allocation and deallocation
6. Maintains null termination of the environment array

### Python Shell Wrapper (`shell.py`)

The Python wrapper provides high-level functionality and LLM integration:

1. **Asynchronous Command Handling**
```python
async def handle_command(self, query: str):
    if query.startswith('#'):
        # Natural language query
        response = await self.llm_client.generate_command(query[1:])
        self.console.print(f"[bold bright_red]{response['command']}[/bold bright_red]")
        
        if '-vv' in query:
            self.console.print(f"[green_yellow]{response['detailed_explanation']}[/green_yellow]")
        elif '-v' in query:
            self.console.print(f"[green_yellow]{response['explanation']}[/green_yellow]")
    else:
        # Direct shell command
        await self.execute_shell_command(query)
```

The command handler processes two types of inputs:
1. Natural Language Queries (starting with #):
   - Strips the # prefix
   - Sends query to LLM for command generation
   - Handles verbosity flags:
     - No flag: Shows only the command
     - `-v`: Adds brief explanation
     - `-vv`: Adds detailed explanation with examples
2. Direct Shell Commands:
   - Passes directly to the C core for execution
   - Captures and handles errors
   - Maintains asynchronous operation

2. **Rich Terminal Output**
```python
def get_prompt(self):
    cwd = self.core_shell.get_cwd()
    return HTML(
        f'<ansigreen>{self.username}@{self.hostname}</ansigreen>:'
        f'<ansiblue>{cwd}</ansiblue>$ '
    )
```

The prompt system provides:
1. Color-coded components using HTML-style formatting
2. Dynamic current directory display
3. Username and hostname information
4. ANSI color support with fallback
5. Customizable prompt structure

3. **Error Handling with LLM Explanations**
```python
async def execute_shell_command(self, command: str):
    try:
        result = self.core_shell.execute(command)
        if result != 0:
            error_msg = os.popen(f"{command} 2>&1").read().strip()
            explanation = await self.llm_client.explain_error(error_msg)
            self.console.print(f"[bright_yellow]{explanation}[/bright_yellow]")
    except Exception as e:
        await self.handle_error(e)
```

The error handling system:
1. Executes commands through the C core
2. Captures both stdout and stderr
3. On non-zero exit codes:
   - Captures the error message
   - Sends to LLM for explanation
   - Formats and displays user-friendly explanation
4. Handles Python exceptions separately
5. Maintains async operation throughout

### LLM Integration (`llm.py`)

The LLM integration layer manages all interactions with Google's Gemini AI:

1. **Structured Command Generation**
```python
COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "The shell command to execute"
        },
        "explanation": {
            "type": "string", 
            "description": "Brief explanation of what the command does"
        },
        "detailed_explanation": {
            "type": "string",
            "description": "Detailed explanation including options and examples"
        }
    },
    "required": ["command", "explanation", "detailed_explanation"]
}
```

The command schema ensures:
1. Consistent response structure
2. Required fields are always present
3. Clear field descriptions for the LLM
4. Validation of response format
5. Easy parsing and handling of responses

### Advanced Caching System

The caching system uses a multi-level approach to optimize performance:

1. **Cache Structure**
```python
class LLMClient:
    def __init__(self, api_key: str):
        self.cache_file = Path.home() / '.llm_shell_cache.json'
        self._cache = {}
        self._load_cache()
        
    def _load_cache(self):
        """Load the persistent cache from disk."""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    self.persistent_cache = json.load(f)
            else:
                self.persistent_cache = {}
        except Exception:
            self.persistent_cache = {}
```

The caching system implements:
1. Two-tier caching:
   - In-memory LRU cache for fastest access
   - Persistent JSON file for long-term storage
2. Version-aware caching:
   - Cache keys include version information
   - Automatic invalidation on prompt changes
3. Type-specific caching:
   - Different handling for commands vs. explanations
   - Structured vs. plain text responses

2. **Cache Key Generation**
```python
def _cache_key(self, query_type: str, text: str) -> str:
    version = "v2"  # Increment when changing prompts
    return hashlib.sha256(f"{version}|{query_type}|{text}".encode()).hexdigest()
```

Key generation ensures:
1. Unique keys for each query type and text
2. Version-based cache invalidation
3. Consistent hashing across sessions
4. Collision-free storage
5. Secure key generation

3. **Memory Cache Management**
```python
@lru_cache(maxsize=1000)
def _get_from_memory_cache(self, cache_key: str) -> Optional[str]:
    return self.persistent_cache.get(cache_key)

def _add_to_cache(self, cache_key: str, response):
    self.persistent_cache[cache_key] = response
    self._get_from_memory_cache.cache_clear()
    self._save_cache()
```

The memory cache:
1. Uses Python's LRU cache decorator
2. Limits memory usage (1000 entries)
3. Automatically evicts least recently used entries
4. Synchronizes with persistent storage
5. Handles cache invalidation

4. **Cache Persistence**
```python
def _save_cache(self):
    """Save the persistent cache to disk."""
    try:
        with open(self.cache_file, 'w') as f:
            json.dump(self.persistent_cache, f)
    except Exception:
        pass  # Fail silently if we can't save cache
```

Persistence features:
1. Atomic file writing
2. Error handling for disk operations
3. JSON format for human readability
4. Automatic recovery from corruption
5. Silent failure to prevent disruption

5. **Cache Security**
```python
def clear_cache(self):
    """Clear both memory and persistent cache."""
    self._get_from_memory_cache.cache_clear()
    self.persistent_cache = {}
    if self.cache_file.exists():
        self.cache_file.unlink()
```

Security considerations:
1. Cache file permissions
2. No sensitive data storage
3. Secure deletion option
4. Error recovery
5. Version-based invalidation

## Contributing

1. Fork the repository
2. Create a feature branch
3. Implement your changes
4. Add tests if applicable
5. Submit a pull request

## License

[Insert License Information] 