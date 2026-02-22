"""Batch sessions into chunks that fit within token limits."""

from .tokenizer import estimate_session_tokens, estimate_batch_tokens
from .config import MAX_TOKENS_PER_BATCH


def create_batches(
    sessions: list[dict],
    max_tokens: int = MAX_TOKENS_PER_BATCH
) -> list[list[dict]]:
    """
    Split sessions into batches that fit within token limit.
    
    Uses a greedy packing algorithm: add sessions to current batch
    until adding the next would exceed the limit.
    
    Args:
        sessions: List of session dicts
        max_tokens: Maximum tokens per batch
        
    Returns:
        List of batches, where each batch is a list of sessions
    """
    if not sessions:
        return []
    
    batches = []
    current_batch = []
    current_tokens = 0
    
    for session in sessions:
        session_tokens = estimate_session_tokens(session)
        
        # If single session exceeds limit, give it its own batch (with warning)
        if session_tokens > max_tokens:
            # Flush current batch if not empty
            if current_batch:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0
            
            # Add oversized session as its own batch
            batches.append([session])
            print(f"Warning: Session {session.get('key')} exceeds token limit "
                  f"({session_tokens} > {max_tokens}). Creating dedicated batch.")
            continue
        
        # Check if adding this session would exceed limit
        if current_tokens + session_tokens > max_tokens and current_batch:
            # Flush current batch and start new one
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        
        # Add session to current batch
        current_batch.append(session)
        current_tokens += session_tokens
    
    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)
    
    return batches


def get_batch_info(batches: list[list[dict]]) -> dict:
    """
    Get summary information about batches.
    
    Args:
        batches: List of batches
        
    Returns:
        Dict with batch statistics
    """
    if not batches:
        return {
            "num_batches": 0,
            "total_sessions": 0,
            "total_tokens": 0,
            "batch_tokens": []
        }
    
    batch_tokens = [estimate_batch_tokens(b) for b in batches]
    total_sessions = sum(len(b) for b in batches)
    
    return {
        "num_batches": len(batches),
        "total_sessions": total_sessions,
        "total_tokens": sum(batch_tokens),
        "batch_tokens": batch_tokens,
        "avg_tokens_per_batch": sum(batch_tokens) / len(batches) if batches else 0,
        "max_batch_tokens": max(batch_tokens) if batch_tokens else 0
    }
