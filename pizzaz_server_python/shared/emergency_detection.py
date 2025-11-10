"""Emergency detection and red flag identification for triage."""


def detect_er_red_flags(reason: str) -> tuple[bool, str | None]:
    """
    Detect life-threatening symptoms that require immediate ER attention.
    
    Args:
        reason: User's reason for seeking care
    
    Returns:
        (is_emergency, warning_message): True with message if emergency detected
    """
    if not reason or not reason.strip():
        return (False, None)
    
    reason_lower = reason.lower().strip()
    
    # Define emergency red flags with their warning messages
    red_flags = [
        # Cardiac
        (["chest pain", "chest pressure", "chest tightness", "heart attack"], 
         "chest pain or pressure - this could be a heart attack"),
        
        # Respiratory
        (["difficulty breathing", "can't breathe", "cannot breathe", "shortness of breath", "severe breathing"],
         "difficulty breathing - this requires immediate attention"),
        
        # Neurological
        (["stroke", "face drooping", "arm weakness", "slurred speech", "severe headache", "worst headache"],
         "stroke symptoms - time is critical"),
        (["loss of consciousness", "unconscious", "passed out", "unresponsive"],
         "loss of consciousness - call 911 immediately"),
        (["severe confusion", "altered mental state"],
         "altered mental state - needs immediate evaluation"),
        
        # Bleeding/Trauma
        (["severe bleeding", "heavy bleeding", "bleeding won't stop", "severe trauma", "severe injury"],
         "severe bleeding or trauma - needs emergency care"),
        (["severe head injury", "head trauma"],
         "head injury - needs immediate evaluation"),
        
        # Allergic/Respiratory
        (["severe allergic reaction", "anaphylaxis", "throat swelling", "tongue swelling"],
         "severe allergic reaction - use EpiPen if available and call 911"),
        
        # Mental Health
        (["suicidal", "want to die", "kill myself", "suicide"],
         "mental health crisis - call 988 Suicide & Crisis Lifeline or 911"),
        
        # Other Critical
        (["severe abdominal pain", "severe stomach pain"],
         "severe abdominal pain - could indicate serious condition"),
        (["coughing up blood", "vomiting blood", "blood in stool"],
         "bleeding from body - needs emergency evaluation"),
        (["seizure", "convulsion"],
         "seizure - needs immediate medical attention"),
    ]
    
    # Check for red flags
    for keywords, warning in red_flags:
        for keyword in keywords:
            if keyword in reason_lower:
                return (True, warning)
    
    return (False, None)

