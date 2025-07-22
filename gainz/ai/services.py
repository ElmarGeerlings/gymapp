import json
import requests
from django.conf import settings
from django_rq import get_queue


class GeminiAIService:
    """Service for interacting with Google Gemini AI API"""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in settings")

    def generate_content(self, prompt, conversation_history=None):
        """Generate content using Gemini AI"""
        headers = {
            'Content-Type': 'application/json',
        }

        # Build the prompt with conversation history if provided
        full_prompt = prompt
        if conversation_history:
            context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation_history])
            full_prompt = f"Previous conversation:\n{context}\n\nCurrent message: {prompt}"

        data = {
            "contents": [{
                "parts": [{
                    "text": full_prompt
                }]
            }]
        }

        url = f"{self.BASE_URL}?key={self.api_key}"
        response = requests.post(url, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result and len(result['candidates']) > 0:
                return result['candidates'][0]['content']['parts'][0]['text']

        return None


class WorkoutProgramAI:
    """AI service specifically for workout program generation"""

    SYSTEM_PROMPT = """You are a fitness coach assistant. Your job is to ask ONE simple question at a time to understand what workout program the user needs.

CRITICAL RULES:
- NEVER ask multiple questions in one response
- NEVER use bullet points or lists
- NEVER ask "What's your goal?" and "How many days?" in the same message
- Ask ONE thing, wait for answer, then ask the next thing
- After 2-3 questions, generate a program

RESPONSE FORMATS:

Single question only:
{
    "type": "question",
    "question": "How many days per week can you train?",
    "suggestions": ["3 days", "4 days", "5-6 days"]
}

Program generation:
{
    "type": "program_generated",
    "program": {
        "name": "4-Day Bodybuilding Program",
        "description": "Push/pull/legs split for muscle building",
        "scheduling_type": "weekly",
        "routines": [
            {
                "name": "Day 1: Push (Chest, Shoulders, Triceps)",
                "description": "Upper body pushing muscles",
                "exercises": [
                    {
                        "exercise_name": "Bench Press",
                        "order": 1,
                        "sets": [
                            {"reps": 8, "rpe": 7, "notes": "Warm up"},
                            {"reps": 6, "rpe": 8, "notes": "Working set"},
                            {"reps": 6, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Overhead Press",
                        "order": 2,
                        "sets": [
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 6, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Dips",
                        "order": 3,
                        "sets": [
                            {"reps": 10, "rpe": 8, "notes": "Working set"},
                            {"reps": 10, "rpe": 8, "notes": "Working set"},
                            {"reps": 8, "rpe": 9, "notes": "Top set"}
                        ]
                    }
                ]
            },
            {
                "name": "Day 2: Pull (Back, Biceps)",
                "description": "Upper body pulling muscles",
                "exercises": [
                    {
                        "exercise_name": "Pull-ups",
                        "order": 1,
                        "sets": [
                            {"reps": 6, "rpe": 7, "notes": "Warm up"},
                            {"reps": 5, "rpe": 8, "notes": "Working set"},
                            {"reps": 4, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Barbell Row",
                        "order": 2,
                        "sets": [
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 6, "rpe": 9, "notes": "Top set"}
                        ]
                    }
                ]
            },
            {
                "name": "Day 3: Legs (Quads, Glutes, Hamstrings)",
                "description": "Lower body muscles",
                "exercises": [
                    {
                        "exercise_name": "Squat",
                        "order": 1,
                        "sets": [
                            {"reps": 8, "rpe": 7, "notes": "Warm up"},
                            {"reps": 6, "rpe": 8, "notes": "Working set"},
                            {"reps": 6, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Romanian Deadlift",
                        "order": 2,
                        "sets": [
                            {"reps": 10, "rpe": 8, "notes": "Working set"},
                            {"reps": 10, "rpe": 8, "notes": "Working set"},
                            {"reps": 8, "rpe": 9, "notes": "Top set"}
                        ]
                    }
                ]
            },
            {
                "name": "Day 4: Push (Chest, Shoulders, Triceps)",
                "description": "Upper body pushing muscles - variation",
                "exercises": [
                    {
                        "exercise_name": "Incline Bench Press",
                        "order": 1,
                        "sets": [
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 6, "rpe": 9, "notes": "Top set"}
                        ]
                    }
                ]
            }
        ]
    }
}

CONVERSATION FLOW:
User: "bodybuilding" → You ask: "How many days per week can you train?"
User: "4 days" → You ask: "What's your experience level?"
User: "3 years" → You generate a 4-day bodybuilding program

ONE QUESTION AT A TIME. NO EXCEPTIONS."""

    def __init__(self):
        self.ai_service = GeminiAIService()

    def process_conversation(self, user_input, conversation_history=None):
        """Process user input and return AI response for workout program creation"""
        if conversation_history is None:
            conversation_history = []

        # Add system prompt at the beginning if this is the first message
        if not conversation_history:
            full_prompt = f"{self.SYSTEM_PROMPT}\n\nUser says: {user_input}"
        else:
            full_prompt = user_input

        response = self.ai_service.generate_content(full_prompt, conversation_history)

        if response:
            # Try to parse as JSON first
            try:
                # Look for JSON in the response
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1

                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                    parsed_response = json.loads(json_str)
                    return parsed_response
            except json.JSONDecodeError:
                pass

            # If not JSON, treat as a regular question
            return {
                "type": "question",
                "question": response,
                "suggestions": []
            }

        return {
            "type": "error",
            "message": "Sorry, I'm having trouble connecting to the AI service. Please try again."
        }


class ConversationManager:
    """Manages AI conversation state using Redis"""

    def __init__(self):
        queue = get_queue()
        self.redis = queue.connection

    def get_conversation_key(self, user_id, session_id):
        return f"ai_conversation:{user_id}:{session_id}"

    def save_conversation(self, user_id, session_id, conversation_history):
        key = self.get_conversation_key(user_id, session_id)
        self.redis.set(key, json.dumps(conversation_history), ex=3600)  # 1 hour expiry

    def get_conversation(self, user_id, session_id):
        key = self.get_conversation_key(user_id, session_id)
        data = self.redis.get(key)
        if data:
            return json.loads(data.decode('utf-8'))
        return []

    def clear_conversation(self, user_id, session_id):
        key = self.get_conversation_key(user_id, session_id)
        self.redis.delete(key)