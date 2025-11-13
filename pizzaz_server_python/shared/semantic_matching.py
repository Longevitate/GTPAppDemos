"""
Semantic matching using vector embeddings for intelligent service matching.

This module provides AI-powered similarity matching between user queries and 
location services. It's more intelligent than keyword matching but requires
additional dependencies.

Installation:
    pip install sentence-transformers

Usage:
    To enable semantic matching, set USE_SEMANTIC_MATCHING=True in your environment.
"""

from typing import Dict, Any, Optional, List
import os

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False

# Global model cache
_model = None
_service_embeddings_cache = {}


def get_model():
    """Lazy load the sentence transformer model."""
    global _model
    if _model is None and SEMANTIC_AVAILABLE:
        # Use a lightweight medical-domain model
        # Options: 'all-MiniLM-L6-v2' (fast, general), 'dmis-lab/biobert-base-cased-v1.2' (medical)
        _model = SentenceTransformer('all-MiniLM-L6-v2')
    return _model


def cosine_similarity(vec1, vec2):
    """Calculate cosine similarity between two vectors."""
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    return dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0


def get_service_embedding(service_text: str):
    """Get or compute embedding for a service description."""
    if service_text in _service_embeddings_cache:
        return _service_embeddings_cache[service_text]
    
    model = get_model()
    if model is None:
        return None
    
    embedding = model.encode(service_text, convert_to_numpy=True)
    _service_embeddings_cache[service_text] = embedding
    return embedding


def semantic_location_match(location: Dict[str, Any], reason: str, threshold: float = 0.5) -> tuple[bool, Optional[str]]:
    """
    Check if a location matches the user's reason using semantic similarity.
    
    Args:
        location: Location dictionary with services
        reason: User's reason for seeking care
        threshold: Similarity threshold (0.0-1.0), higher = stricter
    
    Returns:
        (matches, best_match_service): True if similarity > threshold, with the best matching service
    """
    if not SEMANTIC_AVAILABLE:
        # Fall back to False if library not available
        return (False, None)
    
    if not reason or not reason.strip():
        return (True, None)
    
    model = get_model()
    if model is None:
        return (False, None)
    
    # Get reason embedding
    reason_embedding = model.encode(reason, convert_to_numpy=True)
    
    # Check all services
    services = location.get("services", [])
    best_similarity = 0.0
    best_service = None
    
    for service_category in services:
        values = service_category.get("values", [])
        
        for service_item in values:
            service_val = service_item.get("val", "")
            if not service_val:
                continue
            
            # Get service embedding
            service_embedding = get_service_embedding(service_val)
            if service_embedding is None:
                continue
            
            # Calculate similarity
            similarity = cosine_similarity(reason_embedding, service_embedding)
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_service = service_val
    
    # Return match if above threshold
    if best_similarity >= threshold:
        return (True, f"{best_service} (similarity: {best_similarity:.2f})")
    
    return (False, None)


def hybrid_location_match(location: Dict[str, Any], reason: str, 
                          keyword_fn, 
                          semantic_weight: float = 0.7) -> tuple[bool, Optional[str]]:
    """
    Hybrid matching: combines keyword matching with semantic matching.
    
    Args:
        location: Location dictionary
        reason: User's reason for seeking care
        keyword_fn: Keyword-based matching function to use as fallback
        semantic_weight: Weight for semantic vs keyword (0.0-1.0)
    
    Returns:
        (matches, explanation): True if either method matches, with explanation
    """
    # Try semantic first if available
    if SEMANTIC_AVAILABLE and os.getenv("USE_SEMANTIC_MATCHING", "false").lower() == "true":
        semantic_match, semantic_service = semantic_location_match(location, reason, threshold=0.5)
        if semantic_match:
            return (True, f"Semantic match: {semantic_service}")
    
    # Fall back to keyword matching
    keyword_match, keyword_reason = keyword_fn(location, reason)
    if keyword_match:
        return (True, keyword_reason or "Keyword match")
    
    return (False, None)

