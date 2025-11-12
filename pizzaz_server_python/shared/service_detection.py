"""Service requirement detection based on user's reason for visit."""


def detect_service_requirements(reason: str) -> list[str]:
    """
    Detect what services might be needed based on the reason.
    
    Args:
        reason: User's reason for seeking care
    
    Returns:
        List of required services (e.g., ['x-ray', 'lab'])
    """
    if not reason or not reason.strip():
        return []
    
    reason_lower = reason.lower().strip()
    requirements = []
    
    # X-ray requirements
    xray_keywords = ["fracture", "broken bone", "sprain", "twisted ankle", "chest x-ray", "x-ray"]
    if any(kw in reason_lower for kw in xray_keywords):
        requirements.append("x-ray")
    
    # Lab requirements
    lab_keywords = ["blood test", "lab work", "test results", "cholesterol", "std test", "sti test"]
    if any(kw in reason_lower for kw in lab_keywords):
        requirements.append("lab")
    
    # Procedure room (stitches, wound care)
    procedure_keywords = ["stitches", "sutures", "deep cut", "wound", "laceration"]
    if any(kw in reason_lower for kw in procedure_keywords):
        requirements.append("procedure")
    
    return requirements

