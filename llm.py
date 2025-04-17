"""
LLM integration module for handling interactions with Google's Gemini model.
"""

import os
import json
import hashlib
import time
from typing import Optional, Dict
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Define the command schema
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
            "description": "Detailed explanation including a very brief explanation of the command options, examples, and common use cases"
        }
    },
    "required": ["command", "explanation", "detailed_explanation"],
    "propertyOrdering": ["command", "explanation", "detailed_explanation"]
}

# Define response schema with Pydantic
class CommandResponse(BaseModel):
    command: str
    explanation: str
    detailed_explanation: str

class LLMClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.max_tokens = int(os.getenv("MAX_TOKENS", "65536"))
        self.temperature = float(os.getenv("TEMPERATURE", "0.7"))
        
        # Configure the Gemini API
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"
        
        # Pre-configure common settings
        self.default_config = types.GenerateContentConfig(
            temperature=self.temperature,
            top_p=0.95,
            top_k=64,
            max_output_tokens=self.max_tokens,
            response_mime_type="application/json",
        )
        
        # Initialize cache with debounced save
        self.cache_file = Path.home() / '.llm_shell_cache.json'
        self._dirty = False
        self._last_save = 0
        self._save_interval = 60  # Save at most once per minute
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
    
    def _save_cache(self):
        """Save the persistent cache to disk with debouncing."""
        current_time = time.time()
        if not self._dirty or (current_time - self._last_save) < self._save_interval:
            return
            
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.persistent_cache, f)
            self._last_save = current_time
            self._dirty = False
        except Exception:
            pass  # Fail silently if we can't save cache
    
    def _cache_key(self, query_type: str, text: str) -> str:
        version = "v2"  # Increment when changing prompts
        return hashlib.sha256(f"{version}|{query_type}|{text}".encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict | str]:
        """Get a response from the in-memory cache."""
        return self.persistent_cache.get(cache_key)
    
    def _add_to_cache(self, cache_key: str, response):
        """Add a response to both memory and persistent cache."""
        self.persistent_cache[cache_key] = response
        self._dirty = True
        
        # Try to save cache if enough time has passed
        self._save_cache()
    
    async def complete_command(self, partial_command: str, context: Optional[dict] = None) -> str:
        """Complete a partial shell command."""
        cache_key = self._cache_key("complete", f"{partial_command}:{context}")
        cached = self._get_from_cache(cache_key)
        if cached:
            return str(cached)
        
        contents = [
            types.Content(
                role="user",
                parts=[{"text": "You are a shell command generator. Provide only the command, no explanations or decorations.\n\n" + 
                       f"Complete this shell command: {partial_command}\nContext: {context if context else 'None'}"}]
            )
        ]
        
        response = ""
        async for chunk in self._generate_stream(contents):
            response += chunk
        
        result = response.strip()
        self._add_to_cache(cache_key, result)
        return result
    
    async def explain_error(self, error_message: str) -> str:
        """Explain a shell error message in plain English."""
        cache_key = self._cache_key("error", error_message)
        cached = self._get_from_cache(cache_key)
        if cached:
            return str(cached)
        
        contents = [
            types.Content(
                role="user",
                parts=[{"text": "You are a shell error explainer. Given a shell error, explain it in a structured format using Markdown.\n" +
                       "ALWAYS return a JSON object with this exact structure:\n" +
                       "{\n" +
                       '  "problem": "One line explanation of what went wrong",\n' +
                       '  "solution": ["**Step 1**: Fix details here", "**Step 2**: More details here", "**Step 3**: Additional instructions"]\n' +
                       "}\n\n" +
                       "Rules:\n" +
                       "1. problem must be a single line\n" +
                       "2. solution must be an array of 2-4 steps with Markdown formatting\n" +
                       "3. steps should be clear, actionable, and use Markdown formatting (bold, code blocks with ```)\n" +
                       "4. use code blocks for command examples (```bash ... ```)\n" +
                       "5. MUST return valid JSON with properly escaped Markdown\n\n" +
                       f"Error: {error_message}"}]
            )
        ]
        
        response = ""
        async for chunk in self._generate_stream(contents):
            response += chunk
        
        result = response.strip()
        self._add_to_cache(cache_key, result)
        return result
    
    async def explain_command(self, command: str) -> str:
        """Explain what a shell command does in plain English."""
        cache_key = self._cache_key("explain", command)
        cached = self._get_from_cache(cache_key)
        if cached:
            return str(cached)
        
        contents = [
            types.Content(
                role="user",
                parts=[{"text": 
                    "Explain this command in markdown format with 4 sections:\n"
                    "1. Primary purpose\n"
                    "2. Key components\n"
                    "3. Common use cases\n"
                    "4. Important notes\n"
                    f"Command: {command}\n"
                    "Format response in markdown like:\n"
                    "## Purpose\n"
                    "...\n\n"
                    "## Components\n"
                    "- component1: what it does\n"
                    "- component2: what it does\n\n"
                    "## Use cases\n"
                    "- use case 1\n"
                    "- use case 2\n\n"
                    "## Important Notes\n"
                    "- note 1\n"
                    "- note 2"}]
            )
        ]
        
        response = ""
        async for chunk in self._generate_stream(contents):
            response += chunk
        
        result = response.strip()
        self._add_to_cache(cache_key, result)
        return result
    
    async def generate_command(self, natural_language: str, context: Optional[dict] = None) -> Dict:
        """Generate a shell command from natural language, using structured output."""
        cache_key = self._cache_key("generate", f"{natural_language}:{context}")
        cached = self._get_from_cache(cache_key)
        if cached and isinstance(cached, dict):
            return cached
        
        try:
            # Use structured output with schema
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=f"""Convert this natural language query to a shell command and provide two levels of explanation:
1. A brief explanation of what the command does
2. A detailed explanation including:
   - All important command options and flags used (use `code` format for flags)
   - What each part of the command does (use **bold** for command parts) 
   - Common variations and use cases (use markdown lists)
   - Any relevant examples (use ```bash ... ``` code blocks)
   - Important notes or warnings

Format the response using markdown with sections like:
## Command Options
+- `-f`: force option that does X

## Examples
```bash
example command here
```

## Important Notes and Warnings
+- Warning about potential issues

Query: {natural_language}"""
                        )
                    ],
                )
            ]
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=self.temperature,
                    top_p=0.95,
                    top_k=64,
                    max_output_tokens=self.max_tokens,
                    response_mime_type="application/json",
                    response_schema=COMMAND_SCHEMA
                )
            )
            
            # Parse the JSON response
            try:
                # Handle possible code block formatting in response
                response_text = response.text.strip()
                
                # Try to parse as JSON first
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    # If direct JSON parsing fails, try to extract from code blocks
                    if '```json' in response_text:
                        json_str = response_text.split('```json')[1].split('```')[0].strip()
                    elif '```' in response_text:
                        json_str = response_text.split('```')[1].strip()
                    else:
                        # Try to find JSON object in the text
                        start = response_text.find('{')
                        end = response_text.rfind('}') + 1
                        if start >= 0 and end > start:
                            json_str = response_text[start:end]
                        else:
                            raise ValueError("Could not find JSON in response")
                    
                    result = json.loads(json_str)
                
                # Ensure we have the required fields
                if not isinstance(result, dict):
                    raise ValueError("Response is not a dictionary")
                
                if 'command' not in result:
                    result['command'] = f"echo 'Could not generate command for: {natural_language}'"
                
                if 'explanation' not in result:
                    result['explanation'] = "No explanation available"
                    
                if 'detailed_explanation' not in result:
                    result['detailed_explanation'] = "No detailed explanation available"
                
                # Clean up the response
                result['command'] = result['command'].strip()
                result['explanation'] = result['explanation'].strip()
                result['detailed_explanation'] = result['detailed_explanation'].strip()
                
            except (json.JSONDecodeError, ValueError) as e:
                # Fallback for parsing errors - extract command using a simpler approach
                text = response.text.strip()
                parts = text.split('\n', 1)
                command = parts[0].strip()
                explanation = parts[1].strip() if len(parts) > 1 else "No explanation available"
                
                result = {
                    'command': command,
                    'explanation': explanation,
                    'detailed_explanation': "No detailed explanation available"
                }
            
        except Exception as e:
            # Handle API errors
            result = {
                'command': f"echo 'Error generating command: {str(e)}'",
                'explanation': f"API Error: {str(e)}",
                'detailed_explanation': "No detailed explanation available"
            }
        
        # Cache the result and return
        self._add_to_cache(cache_key, result)
        return result
    
    async def _generate_stream(self, contents):
        """Helper method to handle streaming responses."""
        for chunk in self.client.models.generate_content_stream(
            model=self.model,
            contents=contents,
            config=self.default_config,
        ):
            yield chunk.text 

    def clear_cache(self):
        """Call this after making prompt changes"""
        self.persistent_cache = {}
        self._save_cache() 