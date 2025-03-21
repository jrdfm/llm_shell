"""
LLM integration module for handling interactions with Google's Gemini model.
"""

import os
import json
import hashlib
from typing import Optional, Dict
from functools import lru_cache
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
            "description": "Detailed explanation including command options, examples, and common use cases"
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
            response_mime_type="text/plain",
        )
        
        # Initialize cache
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
    
    def _save_cache(self):
        """Save the persistent cache to disk."""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.persistent_cache, f)
        except Exception:
            pass  # Fail silently if we can't save cache
    
    def _cache_key(self, query_type: str, text: str) -> str:
        version = "v2"  # Increment when changing prompts
        return hashlib.sha256(f"{version}|{query_type}|{text}".encode()).hexdigest()
    
    @lru_cache(maxsize=1000)
    def _get_from_memory_cache(self, cache_key: str) -> Optional[str]:
        """Get a response from the in-memory cache."""
        return self.persistent_cache.get(cache_key)
    
    def _add_to_cache(self, cache_key: str, response):
        """Add a response to both memory and persistent cache."""
        self.persistent_cache[cache_key] = response
        self._get_from_memory_cache.cache_clear()  # Clear LRU cache to update with new value
        self._save_cache()
    
    def _get_from_cache(self, cache_key: str) -> Optional[Dict]:
        """Get a response from cache."""
        cached = self._get_from_memory_cache(cache_key)
        if cached and isinstance(cached, dict):
            return cached
        return None
    
    async def complete_command(self, partial_command: str, context: Optional[dict] = None) -> str:
        """Complete a partial shell command."""
        cache_key = self._cache_key("complete", f"{partial_command}:{context}")
        cached = self._get_from_memory_cache(cache_key)
        if cached:
            return cached
        
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
        cached = self._get_from_memory_cache(cache_key)
        if cached:
            return cached
        
        contents = [
            types.Content(
                role="user",
                parts=[{"text": "Explain this shell error in two parts:\n" +
                       "1. Problem (one line)\n" +
                       "2. Solution (3-4 steps, use bullet points with - not numbers)\n" +
                       "DO NOT USE NUMBERED LISTS IN THE SOLUTION\n\n" +
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
        cached = self._get_from_memory_cache(cache_key)
        if cached:
            return cached
        
        contents = [
            types.Content(
                role="user",
                parts=[{"text": 
                    "Explain this command in 4 bullet points:\n"
                    "1. Primary purpose\n"
                    "2. Key components\n"
                    "3. Common use cases\n"
                    "4. Important notes\n"
                    f"Command: {command}\n"
                    "Format response exactly like:\n"
                    "- Purpose: ...\n"
                    "- Components: ...\n"
                    "- Use cases: ...\n"
                    "- Notes: ..."}]
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
        if cached:
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
   - All important command options and flags used
   - What each part of the command does
   - Common variations and use cases
   - Any relevant examples
   - Important notes or warnings

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
                response_text = response.text
                if '```json' in response_text:
                    json_str = response_text.split('```json')[1].split('```')[0].strip()
                elif '```' in response_text:
                    json_str = response_text.split('```')[1].strip()
                else:
                    json_str = response_text
                
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
        self._get_from_memory_cache.cache_clear() 