"""Interview skill — Zeus conducts structured interviews to learn about the user.

Interviews are distributed across sessions — not a single marathon, but paced
conversations that build up USER.md and MEMORY.md for each profile.

Topics are tracked so Zeus knows what's been covered and what's next.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

INTERVIEW_SCHEMA = {
    "name": "interview",
    "description": "Conduct or manage a user interview to gather personal knowledge.",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "continue", "complete", "status", "topics"],
                "description": "Action: start a new interview, continue an existing one, complete a topic, check status, or list available topics.",
            },
            "topic": {
                "type": "string",
                "description": "Specific topic to interview about (e.g., 'health', 'relationships', 'business').",
            },
            "session_id": {
                "type": "string",
                "description": "Session ID for continuing an existing interview.",
            },
            "facts_count": {
                "type": "integer",
                "description": "Number of facts extracted from this interview session.",
            },
        },
        "required": ["action"],
    },
}

INTERVIEW_TOPICS = {
    "personal": {
        "name": "Personal Background",
        "description": "Name, age, location, daily routines, preferences",
        "questions": [
            "What's your full name and how old are you?",
            "Where do you live? Describe your home setup.",
            "What does a typical weekday look like for you?",
            "What does a typical weekend look like?",
            "What are your biggest personal priorities right now?",
            "Do you have any daily routines or habits?",
            "What are your communication preferences (email, WhatsApp, phone, in-person)?",
            "What time do you usually wake up and go to sleep?",
            "Do you have any dietary preferences or restrictions?",
            "What are your hobbies and interests?",
        ],
    },
    "health": {
        "name": "Health & Fitness",
        "description": "Health history, fitness goals, medications, sleep patterns",
        "questions": [
            "How would you describe your overall health?",
            "Do you have any chronic conditions or ongoing health concerns?",
            "Are you currently taking any medications or supplements?",
            "What's your exercise routine like?",
            "How is your sleep quality? Any issues?",
            "When was your last doctor visit? Any upcoming appointments?",
            "Do you track any health metrics (weight, heart rate, etc.)?",
            "What are your health and fitness goals?",
            "Do you have any allergies?",
            "Who is your primary doctor?",
        ],
    },
    "relationships": {
        "name": "Relationships & Social",
        "description": "Family, friends, partner, social obligations",
        "questions": [
            "Tell me about your family — parents, siblings, children?",
            "Are you in a relationship? Tell me about your partner.",
            "Who are your closest friends?",
            "Do you have any important social obligations or regular gatherings?",
            "Are there any important dates coming up (birthdays, anniversaries)?",
            "How do you prefer to stay in touch with people?",
            "Do you have any pets?",
            "Are there any relationship dynamics I should be aware of?",
        ],
    },
    "business": {
        "name": "Business & Work",
        "description": "Company, role, projects, goals, challenges",
        "questions": [
            "What do you do for work? Describe your role.",
            "Tell me about your company or companies.",
            "What are your main business priorities right now?",
            "Who are the key people you work with?",
            "What are your biggest business challenges?",
            "Do you have any upcoming deadlines or milestones?",
            "What's your work schedule like?",
            "Are you working on any side projects?",
            "What are your long-term business goals?",
        ],
    },
    "finance": {
        "name": "Financial Situation",
        "description": "Income, investments, budgeting, financial goals",
        "questions": [
            "What's your general approach to managing money?",
            "Do you have investment accounts? Where are they held?",
            "What's your monthly budget like?",
            "Do you have any financial goals (savings, purchases, etc.)?",
            "Are there any recurring bills or payments I should know about?",
            "Do you track expenses? How?",
            "What's your risk tolerance for investments?",
            "Do you have any debt?",
        ],
    },
    "home": {
        "name": "Home & Property",
        "description": "Home setup, appliances, smart home, property management",
        "questions": [
            "Describe your home — type, size, location.",
            "Do you have any smart home devices or automation?",
            "Are there any ongoing maintenance issues?",
            "Do you own or rent?",
            "Do you have any other properties?",
            "What appliances do you have? Any that need attention?",
            "Do you have a preferred handyman or service provider?",
            "What's your home internet/network setup like?",
        ],
    },
    "creative": {
        "name": "Creative Projects",
        "description": "Photography, art, music, design, events",
        "questions": [
            "What creative projects are you working on?",
            "Tell me about your photography — what do you shoot?",
            "Do you make music? What kind?",
            "Any art or design projects?",
            "Are you planning any events?",
            "What creative tools do you use?",
            "Do you have any creative goals or deadlines?",
        ],
    },
}

INTERVIEW_STATE_DIR = Path.home() / ".hermes" / "olympus" / "interviews"


def _load_state() -> dict:
    """Load interview progress state."""
    state_file = INTERVIEW_STATE_DIR / "state.json"
    if state_file.exists():
        with open(state_file) as f:
            return json.load(f)
    return {"completed_topics": [], "current_topic": None, "facts_extracted": 0}


def _save_state(state: dict) -> None:
    """Save interview progress state."""
    INTERVIEW_STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INTERVIEW_STATE_DIR / "state.json", "w") as f:
        json.dump(state, f, indent=2)


def _get_available_topics(state: dict) -> list[dict]:
    """Get topics that haven't been interviewed yet."""
    completed = state.get("completed_topics", [])
    return [
        {"key": key, **topic}
        for key, topic in INTERVIEW_TOPICS.items()
        if key not in completed
    ]


def handle_interview(args: dict, **kw) -> dict[str, Any]:
    """Handle an interview request.

    Args:
        args: Dict with 'action', optional 'topic', optional 'session_id'.

    Returns:
        Dict with interview guidance for Zeus.
    """
    action = args.get("action", "status")
    state = _load_state()

    if action == "topics":
        available = _get_available_topics(state)
        completed = state.get("completed_topics", [])
        return {
            "status": "ok",
            "completed_topics": completed,
            "available_topics": [
                {"key": t["key"], "name": t["name"], "description": t["description"]}
                for t in available
            ],
            "facts_extracted": state.get("facts_extracted", 0),
        }

    if action == "status":
        available = _get_available_topics(state)
        current = state.get("current_topic")
        return {
            "status": "ok",
            "current_topic": current,
            "completed_count": len(state.get("completed_topics", [])),
            "remaining_count": len(available),
            "facts_extracted": state.get("facts_extracted", 0),
            "next_suggested": available[0]["key"] if available else None,
        }

    if action == "start":
        topic_key = args.get("topic")
        if not topic_key:
            available = _get_available_topics(state)
            if not available:
                return {"status": "complete", "message": "All interview topics completed!"}
            topic_key = available[0]["key"]

        if topic_key not in INTERVIEW_TOPICS:
            return {"error": f"Unknown topic: {topic_key}. Available: {list(INTERVIEW_TOPICS.keys())}"}

        if topic_key in state.get("completed_topics", []):
            return {"status": "already_completed", "message": f"Topic '{topic_key}' already completed."}

        topic = INTERVIEW_TOPICS[topic_key]
        state["current_topic"] = topic_key
        _save_state(state)

        return {
            "status": "started",
            "topic": topic_key,
            "topic_name": topic["name"],
            "description": topic["description"],
            "questions": topic["questions"],
            "guidance": (
                f"Start the '{topic['name']}' interview. Ask the questions naturally in conversation — "
                f"not all at once. Spread them across the session. After gathering facts, use "
                f"share_knowledge to write them with scope='personal' and domain='{topic_key}'. "
                f"When done, call interview with action='complete' and topic='{topic_key}'."
            ),
        }

    if action == "continue":
        current = state.get("current_topic")
        if not current or current not in INTERVIEW_TOPICS:
            return {"status": "no_active", "message": "No active interview. Use action='start' to begin."}

        topic = INTERVIEW_TOPICS[current]
        return {
            "status": "continued",
            "topic": current,
            "topic_name": topic["name"],
            "questions": topic["questions"],
            "guidance": f"Continue the '{topic['name']}' interview. Ask remaining questions naturally.",
        }

    if action == "complete":
        topic_key = args.get("topic")
        if not topic_key:
            topic_key = state.get("current_topic")
        if not topic_key or topic_key not in INTERVIEW_TOPICS:
            return {"error": "No topic to complete. Provide 'topic' or have an active interview."}

        if topic_key not in state.get("completed_topics", []):
            state.setdefault("completed_topics", []).append(topic_key)

        facts_count = args.get("facts_count", 0)
        state["facts_extracted"] = state.get("facts_extracted", 0) + facts_count
        state["current_topic"] = None
        _save_state(state)

        topic = INTERVIEW_TOPICS[topic_key]
        available = _get_available_topics(state)
        next_topic = available[0] if available else None

        return {
            "status": "completed",
            "topic": topic_key,
            "facts_extracted_this_session": facts_count,
            "total_facts": state["facts_extracted"],
            "remaining_topics": len(available),
            "next_suggested": next_topic["key"] if next_topic else None,
            "guidance": (
                f"Interview topic '{topic['name']}' completed with {facts_count} facts extracted. "
                f"{'Suggested next topic: ' + next_topic['name'] if next_topic else 'All topics completed!'}"
            ),
        }

    return {"error": f"Unknown action: {action}"}
