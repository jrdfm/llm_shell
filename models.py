from pydantic import BaseModel

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

class CommandResponse(BaseModel):
    command: str
    explanation: str
    detailed_explanation: str 