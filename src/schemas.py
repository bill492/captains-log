"""Pydantic schemas for structured outputs."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Union


class LogEntry(BaseModel):
    """A single Captain's Log entry."""
    model_config = ConfigDict(extra="forbid")  # additionalProperties: false
    
    timestamp: str = Field(description="ISO 8601 timestamp of the event")
    log: str = Field(description="Third-person narrative about Bill (e.g., 'Bill analyzed...' not 'I analyzed...')")
    channel: str = Field(description="Channel where this occurred (slack, main, etc.)")
    # OpenAI strict mode requires all fields in 'required', so use Union with null instead of Optional
    session_key: Union[str, None] = Field(
        default=None,
        description="Session key if available, or null"
    )
    remarks: Union[str, None] = Field(
        default=None,
        description="Additional remarks or context, or null"
    )


class SummarizerOutput(BaseModel):
    """Output schema for the summarizer."""
    model_config = ConfigDict(extra="forbid")  # additionalProperties: false
    
    entries: list[LogEntry] = Field(
        description="List of log entries extracted from the sessions"
    )
    summary: str = Field(
        description="Brief 1-2 sentence third-person summary of Bill's activity (e.g., 'Bill worked on...')"
    )


def get_strict_schema() -> dict:
    """
    Get JSON schema compatible with OpenAI strict mode.
    Ensures all properties are in 'required' array.
    """
    schema = SummarizerOutput.model_json_schema()
    
    # Recursively ensure all objects have all properties required
    def fix_required(obj):
        if isinstance(obj, dict):
            if obj.get("type") == "object" and "properties" in obj:
                obj["required"] = list(obj["properties"].keys())
                obj["additionalProperties"] = False
            for v in obj.values():
                fix_required(v)
        elif isinstance(obj, list):
            for item in obj:
                fix_required(item)
    
    fix_required(schema)
    
    # Also fix $defs if present
    if "$defs" in schema:
        for def_schema in schema["$defs"].values():
            fix_required(def_schema)
    
    return schema
