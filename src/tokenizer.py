"""Token counting using tiktoken."""

import tiktoken
from .config import TOKEN_MODEL


def count_tokens(text: str, model: str = TOKEN_MODEL) -> int:
    """
    Count tokens using tiktoken.
    
    Args:
        text: Text to count tokens for
        model: Encoding model (default: cl100k_base)
        
    Returns:
        Token count
    """
    try:
        encoding = tiktoken.get_encoding(model)
        return len(encoding.encode(text))
    except Exception as e:
        # Fallback to rough estimate if tiktoken fails
        # Approximation: ~4 chars per token
        return len(text) // 4


def estimate_session_tokens(session: dict) -> int:
    """
    Estimate tokens for a session including all messages.
    
    Args:
        session: Session dict with messages
        
    Returns:
        Estimated token count
    """
    total = 0
    
    # Session metadata
    metadata = f"""Session: {session.get('key', '')}
Channel: {session.get('channel', '')}
Kind: {session.get('kind', '')}
DisplayName: {session.get('displayName', '')}
"""
    total += count_tokens(metadata)
    
    # Messages
    messages = session.get('messages', [])
    for msg in messages:
        role = msg.get('role', '')
        content = msg.get('content', '')
        timestamp = msg.get('timestamp', '')
        
        msg_text = f"{role}: {content}"
        if timestamp:
            msg_text = f"[{timestamp}] {msg_text}"
        
        total += count_tokens(msg_text)
    
    return total


def estimate_batch_tokens(sessions: list[dict]) -> int:
    """
    Estimate total tokens for a batch of sessions.
    
    Args:
        sessions: List of session dicts
        
    Returns:
        Total estimated token count
    """
    return sum(estimate_session_tokens(s) for s in sessions)
