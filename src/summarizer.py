"""Summarize sessions using GPT-5.2 Responses API with structured outputs."""

import json
import time
from openai import OpenAI
from typing import Optional
from .config import (
    MODEL, REASONING_EFFORT, MAX_OUTPUT_TOKENS, PROMPTS_DIR,
    MAX_RETRIES, RETRY_DELAY, RETRY_BACKOFF
)
from .schemas import SummarizerOutput, get_strict_schema


class SummarizerError(Exception):
    """Error during summarization."""
    pass


def load_system_prompt() -> str:
    """Load the system prompt with instructions."""
    prompt_path = PROMPTS_DIR / "captain_log_system.txt"
    
    if not prompt_path.exists():
        raise SummarizerError(f"System prompt not found: {prompt_path}")
    
    return prompt_path.read_text()


def load_user_template() -> str:
    """Load the user prompt template (for data)."""
    prompt_path = PROMPTS_DIR / "captain_log_user.txt"
    
    if not prompt_path.exists():
        raise SummarizerError(f"User prompt template not found: {prompt_path}")
    
    return prompt_path.read_text()


def format_sessions_for_model(sessions: list[dict]) -> str:
    """
    Format sessions into readable text for the model.
    
    Args:
        sessions: List of session dicts (with 'messages' and optional 'context')
        
    Returns:
        Formatted text representation
    """
    output = []
    
    for session in sessions:
        key = session.get('key', 'unknown')
        channel = session.get('channel', 'unknown')
        kind = session.get('kind', 'unknown')
        display_name = session.get('displayName', '')
        
        header = f"\n{'='*60}\nSession: {key}"
        if display_name:
            header += f" ({display_name})"
        header += f"\nChannel: {channel} | Kind: {kind}\n{'='*60}\n"
        
        output.append(header)
        
        # Context messages (for reference only, do not create entries)
        context = session.get('context', [])
        if context:
            output.append("\n--- CONTEXT (for reference, do NOT create entries for these) ---\n")
            for msg in context:
                role = msg.get('role', 'unknown')
                content = msg.get('content', '')
                timestamp = msg.get('timestamp', '')
                if timestamp:
                    output.append(f"[{timestamp}] {role.upper()}: {content}\n")
                else:
                    output.append(f"{role.upper()}: {content}\n")
            output.append("\n--- END CONTEXT ---\n")
        
        # New messages (create entries for these)
        output.append("\n--- NEW ACTIVITY (create entries for these) ---\n")
        messages = session.get('messages', [])
        for msg in messages:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp', '')
            
            if timestamp:
                output.append(f"[{timestamp}] {role.upper()}: {content}\n")
            else:
                output.append(f"{role.upper()}: {content}\n")
        output.append("\n--- END NEW ACTIVITY ---\n")
    
    return '\n'.join(output)


def summarize_batch(
    sessions: list[dict],
    previous_summaries: list[str],
    api_key: Optional[str] = None
) -> dict:
    """
    Call GPT-5.2 to summarize a batch of sessions.
    
    Args:
        sessions: List of session dicts
        previous_summaries: Recent summaries for context
        api_key: OpenAI API key (uses env var if not provided)
        
    Returns:
        Dict with entries and summary
        
    Raises:
        SummarizerError: If API call fails after retries
    """
    if not sessions:
        return {"entries": [], "summary": "No activity"}
    
    # Load prompts
    system_prompt = load_system_prompt()
    user_template = load_user_template()
    conversation_logs = format_sessions_for_model(sessions)
    
    # Format previous summaries
    if previous_summaries:
        summaries_text = "\n".join(f"- {s}" for s in previous_summaries)
    else:
        summaries_text = "(No previous summaries available)"
    
    # Fill in user template with data
    user_prompt = user_template.format(
        previous_summaries=summaries_text,
        conversation_logs=conversation_logs
    )
    
    # Call GPT-5.2 Responses API with structured outputs
    for attempt in range(MAX_RETRIES):
        try:
            client = OpenAI(api_key=api_key, timeout=60.0)
            
            response = client.responses.create(
                model=MODEL,
                input=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "summarizer_output",
                        "strict": True,
                        "schema": get_strict_schema()
                    }
                },
                max_output_tokens=MAX_OUTPUT_TOKENS,
                reasoning={"effort": REASONING_EFFORT}
            )
            
            # Check for refusal
            if response.status == "incomplete":
                reason = response.incomplete_details.reason if response.incomplete_details else "unknown"
                raise SummarizerError(f"Response incomplete: {reason}")
            
            # Parse the JSON output
            output_text = response.output_text
            parsed = json.loads(output_text)
            
            # Validate with Pydantic
            result = SummarizerOutput.model_validate(parsed)
            
            # Convert to dict for compatibility with existing code
            return {
                "entries": [entry.model_dump() for entry in result.entries],
                "summary": result.summary
            }
        
        except Exception as e:
            error_msg = str(e)
            
            # Check if it's a rate limit error
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                    print(f"Rate limited. Retrying in {delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(delay)
                    continue
            
            # For other errors or final retry, raise
            if attempt == MAX_RETRIES - 1:
                raise SummarizerError(
                    f"Failed to summarize batch after {MAX_RETRIES} attempts: {e}"
                )
            else:
                # Retry with backoff for non-rate-limit errors too
                delay = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                print(f"Error: {e}. Retrying in {delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(delay)
                continue
                time.sleep(delay)
    
    # Should not reach here
    raise SummarizerError("Failed to summarize batch")
