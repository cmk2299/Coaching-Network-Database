#!/usr/bin/env python3
"""
Node Type Classification
Classifies nodes based on their current_role into proper categories
"""

def classify_node_type(current_role):
    """
    Classify node based on current_role

    Returns: 'head_coach', 'assistant_coach', 'scout', 'sporting_director',
             'executive', 'youth_coach', 'support_staff', 'unclassified'
    """
    if not current_role:
        return 'unclassified'

    role_lower = current_role.lower()

    # Support Staff FIRST (to catch "Performance Manager" before "Manager")
    if any(keyword in role_lower for keyword in [
        'performance manager',
        'team manager',
        'loan manager',
        'loan player manager',
        'video analyst',
        'kit manager',
        'analyst',
        'member of',  # e.g. "Member of Management Board"
        'physiotherapist',
        'masseur',
        'psychologist',
        'doctor',
        'nutritionist',
        'rehabilitation',
        'media',
        'press officer',
        'communications',
        'supervisor'
    ]):
        return 'support_staff'

    # Head Coaches / Managers (but not assistants or youth)
    if any(keyword in role_lower for keyword in ['manager', 'head coach', 'cheftrainer', 'caretaker manager']):
        if 'assistant' not in role_lower and 'youth' not in role_lower and 'u19' not in role_lower and 'u17' not in role_lower:
            # Additional exclusions
            if 'loan' not in role_lower and 'team manager' not in role_lower:
                return 'head_coach'

    # Assistant Coaches
    if 'assistant' in role_lower and ('manager' in role_lower or 'coach' in role_lower or 'trainer' in role_lower):
        return 'assistant_coach'

    # Co-Trainer (German for assistant)
    if 'co-trainer' in role_lower or 'co trainer' in role_lower:
        return 'assistant_coach'

    # Youth Coaches
    if any(keyword in role_lower for keyword in ['youth', 'u19', 'u17', 'u16', 'u15', 'academy']):
        if any(keyword in role_lower for keyword in ['coach', 'trainer', 'manager']):
            return 'youth_coach'

    # Scouts (any type)
    if 'scout' in role_lower:
        return 'scout'

    # Sporting Directors
    if 'sporting director' in role_lower or 'sport director' in role_lower or 'sportdirektor' in role_lower:
        return 'sporting_director'

    # Executives (Managing Directors, Technical Directors, etc.)
    if any(keyword in role_lower for keyword in [
        'managing director',
        'technical director',
        'director of',
        'geschäftsführer',
        'academy director',
        'scouting director'
    ]):
        return 'executive'

    # Goalkeeper Coach (special case - still a coach but specific)
    if 'goalkeeper' in role_lower or 'goalkeeping' in role_lower:
        if 'coach' in role_lower or 'trainer' in role_lower:
            return 'assistant_coach'  # Classify as assistant

    # Fitness Coach
    if 'fitness' in role_lower and ('coach' in role_lower or 'trainer' in role_lower):
        return 'assistant_coach'

    # Other coaching roles
    if any(keyword in role_lower for keyword in ['coach', 'trainer', 'coaching']):
        # Make sure it's not support staff disguised as coach
        if not any(keyword in role_lower for keyword in ['academy coaching', 'head of academy']):
            return 'assistant_coach'

    # Default: unclassified (needs manual review)
    return 'unclassified'


def classify_subcategory(current_role, node_type):
    """
    Further classify into subcategories for more granular analysis
    """
    if not current_role:
        return node_type

    role_lower = current_role.lower()

    if node_type == 'scout':
        if 'chief' in role_lower or 'head of' in role_lower:
            return 'chief_scout'
        elif 'youth' in role_lower:
            return 'youth_scout'
        else:
            return 'scout'

    if node_type == 'executive':
        if 'academy' in role_lower:
            return 'academy_director'
        elif 'technical' in role_lower:
            return 'technical_director'
        elif 'scouting' in role_lower:
            return 'scouting_director'
        elif 'managing' in role_lower or 'geschäftsführer' in role_lower:
            return 'managing_director'
        else:
            return 'executive'

    if node_type == 'assistant_coach':
        if 'goalkeeper' in role_lower or 'goalkeeping' in role_lower:
            return 'goalkeeper_coach'
        elif 'fitness' in role_lower:
            return 'fitness_coach'
        else:
            return 'assistant_coach'

    if node_type == 'youth_coach':
        if 'u19' in role_lower:
            return 'u19_coach'
        elif 'u17' in role_lower:
            return 'u17_coach'
        else:
            return 'youth_coach'

    return node_type


def get_classification_summary():
    """
    Return human-readable descriptions of each classification
    """
    return {
        'head_coach': 'Head Coach / Manager (first team)',
        'assistant_coach': 'Assistant Coach / Co-Trainer (first team)',
        'youth_coach': 'Youth/Academy Coach (U19, U17, etc.)',
        'scout': 'Scout / Talent Scout',
        'sporting_director': 'Sporting Director',
        'executive': 'Executive (Managing Director, Technical Director)',
        'support_staff': 'Support Staff (Performance Manager, Analyst, etc.)',
        'unclassified': 'Unclassified (needs manual review)'
    }


if __name__ == "__main__":
    # Test cases
    test_roles = [
        ('Manager', 'head_coach'),
        ('Assistant Manager', 'assistant_coach'),
        ('Head of Scouting', 'scout'),
        ('Sporting Director', 'sporting_director'),
        ('Managing Director Sport', 'executive'),
        ('Youth Scout', 'scout'),
        ('U19 Coach', 'youth_coach'),
        ('Performance Manager', 'support_staff'),
        ('Co-Trainer', 'assistant_coach'),
        ('Goalkeeper Coach', 'assistant_coach'),
        ('', 'unclassified'),
    ]

    print("Testing Classification Logic:")
    print("=" * 60)

    for role, expected in test_roles:
        result = classify_node_type(role)
        subcategory = classify_subcategory(role, result)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{role}' → {result} ({subcategory})")
        if result != expected:
            print(f"  Expected: {expected}")

    print("\n" + "=" * 60)
    print("Classification Descriptions:")
    print("=" * 60)
    for key, desc in get_classification_summary().items():
        print(f"{key}: {desc}")
