import json
import requests
from django.conf import settings
try:
    from django_redis import get_redis_connection
except ImportError:
    get_redis_connection = None


class GeminiAIService:
    """Service for interacting with Google Gemini AI API"""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"

    def __init__(self):
        self.api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in settings")

    def generate_content(self, prompt, conversation_history=None):
        """Generate content using Gemini AI with improved parameters"""
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
            }],
            "generationConfig": {
                "temperature": 0.7,  # More conversational and creative
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": 1024
            }
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

    SYSTEM_PROMPT = """You are a personal fitness trainer. Have a focused conversation to create a workout program.

CRITICAL RULES - FOLLOW EXACTLY:
1. Ask ONLY ONE question per response
2. Keep responses under 20 words maximum
3. Never ask multiple questions in one response
4. No lists, bullet points, or complex explanations

EXAMPLES OF CORRECT RESPONSES:

User: "I want to build muscle"
You: {"type": "question", "question": "Great! How long have you been training?", "suggestions": ["New to this", "About a year", "Several years"]}

User: "I've been training for a year"
You: {"type": "question", "question": "What does your current routine look like?", "suggestions": ["I follow a program", "I do my own thing", "Just machines"]}

User: "I do my own thing"
You: {"type": "question", "question": "How many days per week do you train?", "suggestions": ["3 days", "4 days", "5-6 days"]}

User: "4 days"
You: {"type": "question", "question": "Which days work best for you?", "suggestions": ["Mon/Wed/Fri/Sat", "Tue/Thu/Sat/Sun", "Any 4 days"]}

EXAMPLES OF WRONG RESPONSES (NEVER DO THIS):
❌ "What's your experience? How many days do you train? What equipment do you have?"
❌ "To help you, I need to know your goals, experience level, and training frequency."
❌ Any response longer than 20 words

CONVERSATION FLOW:
1. Goal → 2. Experience → 3. Training days → 4. Preferred days → 5. Equipment → 6. Generate program

WHEN TO GENERATE PROGRAM:
- After asking 5-6 questions about goal, experience, training days, preferred days, equipment
- When user asks for program generation
- When you have basic info: fitness goal + training experience + days per week + preferred days

EXAMPLE PROGRAM GENERATION TRIGGER:
User: "Mon/Wed/Fri/Sat"
You: {"type": "program_generated", "program": {"name": "4-Day Muscle Building Program", "description": "Upper/lower split for intermediate lifters", "scheduling_type": "weekly", "routines": [...]}}

JSON FORMATS:

For questions:
{"type": "question", "question": "Short question only", "suggestions": ["Option 1", "Option 2", "Option 3"]}

For program generation:
{"type": "program_generated", "program": {"name": "Program Name", "description": "Brief description", "scheduling_type": "weekly", "routines": [{"name": "Monday: Push", "description": "Chest, shoulders, triceps", "exercises": [{"exercise_name": "Bench Press", "order": 1, "sets": [{"reps": 8, "rpe": 7, "notes": "Warm up"}, {"reps": 6, "rpe": 8, "notes": "Working set"}]}]}]}}

CRITICAL: When user asks "generate program" or "create program" or similar, ALWAYS return program_generated type, NOT text explanation.

ONE QUESTION. UNDER 20 WORDS. NO EXCEPTIONS."""

    def __init__(self):
        self.ai_service = GeminiAIService()

    def process_conversation(self, user_input, conversation_history=None):
        """Process user input and return AI response for workout program creation"""
        if conversation_history is None:
            conversation_history = []

        # Check what information we already have to avoid repeating questions
        gathered_info = self._analyze_conversation(conversation_history)

        # Add context about what we already know
        context_info = self._build_context_info(gathered_info)

        # ALWAYS include system prompt - this was the main issue!
        full_prompt = f"{self.SYSTEM_PROMPT}\n\n{context_info}\n\nUser says: {user_input}"

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

                    # Validate the response isn't too overwhelming
                    if self._is_response_too_complex(parsed_response):
                        simplified = self._simplify_response(parsed_response)
                        print(f"[DEBUG] Simplified response: {simplified}")  # Debug logging
                        return simplified

                    return parsed_response
            except json.JSONDecodeError as e:
                print(f"[DEBUG] JSON parse error: {e}")  # Debug logging
                print(f"[DEBUG] Response was: {response[:200]}...")  # Debug logging

            # If not JSON and looks like program request, force JSON format
            if any(keyword in response.lower() for keyword in ['program', 'routine', 'workout plan']):
                return {
                    "type": "error",
                    "message": "I should generate a program in the app, but I gave you text instead. Please try the 'Generate Program Now' button."
                }

            # If not JSON, treat as a regular question but apply validation
            question_response = {
                "type": "question",
                "question": response.strip(),
                "suggestions": []
            }

            # Apply validation to non-JSON responses too
            if self._is_response_too_complex(question_response):
                return self._simplify_response(question_response)

            return question_response

        return {
            "type": "error",
            "message": "Sorry, I'm having trouble connecting to the AI service. Please try again."
        }

    def _analyze_conversation(self, conversation_history):
        """Analyze conversation to determine what information has been gathered"""
        gathered_info = {
            'goal': None,
            'experience': None,
            'training_days': None,
            'preferred_days': None,
            'equipment': None
        }

        # Look for key information in user messages
        for msg in conversation_history:
            if msg.get('role') == 'user':
                content = msg.get('content', '').lower()

                # Check for fitness goals
                if any(word in content for word in ['build muscle', 'muscle', 'strength', 'get stronger', 'lose fat', 'weight loss', 'fitness', 'general']):
                    if 'muscle' in content or 'build' in content:
                        gathered_info['goal'] = 'muscle'
                    elif 'strength' in content or 'stronger' in content:
                        gathered_info['goal'] = 'strength'
                    elif 'fat' in content or 'weight' in content:
                        gathered_info['goal'] = 'weight_loss'
                    else:
                        gathered_info['goal'] = 'general'

                # Check for experience level
                if any(word in content for word in ['new', 'beginner', 'started', 'year', 'years', 'experience']):
                    if 'new' in content or 'beginner' in content:
                        gathered_info['experience'] = 'beginner'
                    elif 'year' in content:
                        gathered_info['experience'] = 'intermediate'
                    else:
                        gathered_info['experience'] = 'intermediate'

                # Check for training days
                if any(word in content for word in ['3 days', '4 days', '5 days', '6 days', 'daily']):
                    if '3 days' in content:
                        gathered_info['training_days'] = 3
                    elif '4 days' in content:
                        gathered_info['training_days'] = 4
                    elif '5 days' in content or '6 days' in content:
                        gathered_info['training_days'] = 5

                # Check for preferred days
                if any(word in content for word in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']):
                    gathered_info['preferred_days'] = content

                # Check for equipment
                if any(word in content for word in ['gym', 'home', 'equipment', 'barbell', 'dumbbell', 'machine']):
                    if 'gym' in content:
                        gathered_info['equipment'] = 'gym'
                    elif 'home' in content:
                        gathered_info['equipment'] = 'home'
                    else:
                        gathered_info['equipment'] = 'basic'

        return gathered_info

    def _build_context_info(self, gathered_info):
        """Build context information for the AI about what we already know"""
        context_parts = []

        if gathered_info['goal']:
            context_parts.append(f"Goal: {gathered_info['goal']}")
        if gathered_info['experience']:
            context_parts.append(f"Experience: {gathered_info['experience']}")
        if gathered_info['training_days']:
            context_parts.append(f"Training days: {gathered_info['training_days']}")
        if gathered_info['preferred_days']:
            context_parts.append(f"Preferred days: {gathered_info['preferred_days']}")
        if gathered_info['equipment']:
            context_parts.append(f"Equipment: {gathered_info['equipment']}")

        if context_parts:
            return f"Information already gathered: {', '.join(context_parts)}. Don't ask about these again."
        else:
            return "No information gathered yet. Start with basic questions."

    def _is_response_too_complex(self, response):
        """Simplified validation - just catch extreme cases"""
        if response.get('type') != 'question':
            return False

        question = response.get('question', '').lower()

        # Only catch really bad cases now that system prompt works
        complexity_indicators = [
            question.count('?') > 2,  # More than 2 question marks
            len(question.split()) > 30,  # More than 30 words (very long)
            question.count('what') > 2,  # Way too many "what" questions
        ]

        return any(complexity_indicators)

    def _simplify_response(self, response):
        """Aggressively simplify complex responses"""
        question = response.get('question', '')

        # Strategy 1: Find the first clear question
        sentences = question.split('?')
        if len(sentences) > 1:
            # Take the first sentence that looks like a question
            first_question = sentences[0].strip()

            # If it's too long, try to extract just the question part
            if len(first_question.split()) > 15:
                # Look for question words and take from there
                question_words = ['what', 'how', 'when', 'where', 'why', 'which', 'do you', 'can you', 'are you']
                for word in question_words:
                    if word in first_question.lower():
                        start_idx = first_question.lower().find(word)
                        first_question = first_question[start_idx:].strip()
                        break

            return {
                "type": "question",
                "question": first_question + '?',
                "suggestions": response.get('suggestions', [])
            }

        # Strategy 2: If no question marks, look for question patterns
        if '?' not in question:
            question_patterns = ['what', 'how', 'when', 'where', 'why', 'which', 'do you', 'can you', 'are you']
            for pattern in question_patterns:
                if pattern in question.lower():
                    start_idx = question.lower().find(pattern)
                    simplified = question[start_idx:].strip()
                    # Take only the first sentence
                    if '.' in simplified:
                        simplified = simplified.split('.')[0]
                    return {
                        "type": "question",
                        "question": simplified + '?',
                        "suggestions": response.get('suggestions', [])
                    }

        # Strategy 3: Fallback - just take first 10 words and add question mark
        words = question.split()
        if len(words) > 10:
            simplified = ' '.join(words[:10])
            return {
    "type": "question",
                "question": simplified + '?',
                "suggestions": response.get('suggestions', [])
            }

        return response

    def force_program_generation(self, conversation_history):
        """Force program generation based on conversation history"""
        # Extract information from conversation history
        user_messages = [msg['content'] for msg in conversation_history if msg['role'] == 'user']

        # Analyze conversation to determine program type
        conversation_text = ' '.join(user_messages).lower()

        # Determine program parameters
        if 'strength' in conversation_text or 'powerlifting' in conversation_text:
            program_type = "strength"
            days = 3
        elif 'muscle' in conversation_text or 'bodybuilding' in conversation_text:
            program_type = "muscle"
            days = 4
        else:
            program_type = "general"
            days = 3

        # Extract training days if mentioned
        for i in range(7, 2, -1):  # Check 7 down to 3
            if f'{i} day' in conversation_text or f'{i}day' in conversation_text:
                days = i
                break

        # Create a focused prompt just for program generation
        program_prompt = f"""Generate a {days}-day {program_type} workout program based on this conversation:

User Messages: {' | '.join(user_messages[-5:])}

Return ONLY this JSON structure with real exercises:
{{"type": "program_generated", "program": {{"name": "{days}-Day {program_type.title()} Program", "description": "Based on user conversation", "scheduling_type": "weekly", "routines": [
{self._get_routine_template(program_type, days)}
]}}}}

IMPORTANT: Include day names in routine names like "Monday: Push", "Tuesday: Pull", etc.

Use real exercise names like: Bench Press, Squat, Deadlift, Pull-ups, Overhead Press, Barbell Row, etc.
Each routine should have 4-6 exercises with 3-4 sets each."""

        response = self.ai_service.generate_content(program_prompt)

        if response:
            try:
                # Look for JSON in the response
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1

                if start_idx != -1 and end_idx != -1:
                    json_str = response[start_idx:end_idx]
                    parsed_response = json.loads(json_str)
                    return parsed_response
            except json.JSONDecodeError as e:
                print(f"[DEBUG] Force generation JSON error: {e}")
                print(f"[DEBUG] Force generation response: {response}")

        # Better fallback - create a proper program based on detected parameters
        return self._create_fallback_program(program_type, days)

    def _get_routine_template(self, program_type, days):
        """Get routine template based on program type"""
        if program_type == "strength" and days >= 3:
            return '''{"name": "Monday: Squat Focus", "description": "Lower body strength", "exercises": [{"exercise_name": "Squat", "order": 1, "sets": [{"reps": 5, "rpe": 8, "notes": "Working set"}]}]}, {"name": "Wednesday: Bench Focus", "description": "Upper body strength", "exercises": [{"exercise_name": "Bench Press", "order": 1, "sets": [{"reps": 5, "rpe": 8, "notes": "Working set"}]}]}, {"name": "Friday: Deadlift Focus", "description": "Posterior chain", "exercises": [{"exercise_name": "Deadlift", "order": 1, "sets": [{"reps": 5, "rpe": 8, "notes": "Working set"}]}]}'''
        elif program_type == "muscle" and days >= 4:
            return '''{"name": "Monday: Push", "description": "Chest, shoulders, triceps", "exercises": [{"exercise_name": "Bench Press", "order": 1, "sets": [{"reps": 8, "rpe": 8, "notes": "Working set"}]}]}, {"name": "Tuesday: Pull", "description": "Back, biceps", "exercises": [{"exercise_name": "Pull-ups", "order": 1, "sets": [{"reps": 8, "rpe": 8, "notes": "Working set"}]}]}, {"name": "Thursday: Legs", "description": "Quads, glutes, hamstrings", "exercises": [{"exercise_name": "Squat", "order": 1, "sets": [{"reps": 10, "rpe": 8, "notes": "Working set"}]}]}, {"name": "Saturday: Push", "description": "Chest, shoulders, triceps", "exercises": [{"exercise_name": "Overhead Press", "order": 1, "sets": [{"reps": 8, "rpe": 8, "notes": "Working set"}]}]}'''
        else:
            return '''{"name": "Monday: Full Body", "description": "Complete workout", "exercises": [{"exercise_name": "Squat", "order": 1, "sets": [{"reps": 10, "rpe": 7, "notes": "Working set"}]}]}'''

    def _create_fallback_program(self, program_type, days):
        """Create a proper fallback program structure"""
        if program_type == "strength":
            routines = [
                {
                    "name": "Monday: Squat Focus",
                    "description": "Lower body strength development",
                    "exercises": [
                        {
                            "exercise_name": "Back Squat",
                            "order": 1,
                            "sets": [
                                {"reps": 5, "rpe": 7, "notes": "Warm up set"},
                                {"reps": 5, "rpe": 8, "notes": "Working set"},
                                {"reps": 5, "rpe": 9, "notes": "Top set"}
                            ]
                        },
                        {
                            "exercise_name": "Romanian Deadlift",
                            "order": 2,
                            "sets": [
                                {"reps": 8, "rpe": 7, "notes": "Working set"},
                                {"reps": 8, "rpe": 8, "notes": "Working set"}
                            ]
                        }
                    ]
                },
                {
                    "name": "Wednesday: Bench Focus",
                    "description": "Upper body pressing strength",
                    "exercises": [
                        {
                            "exercise_name": "Bench Press",
                            "order": 1,
                            "sets": [
                                {"reps": 5, "rpe": 7, "notes": "Warm up set"},
                                {"reps": 5, "rpe": 8, "notes": "Working set"},
                                {"reps": 5, "rpe": 9, "notes": "Top set"}
                            ]
                        },
                        {
                            "exercise_name": "Barbell Row",
                            "order": 2,
                            "sets": [
                                {"reps": 8, "rpe": 7, "notes": "Working set"},
                                {"reps": 8, "rpe": 8, "notes": "Working set"}
                            ]
                        }
                    ]
                },
                {
                    "name": "Friday: Deadlift Focus",
                    "description": "Posterior chain strength",
                    "exercises": [
                        {
                            "exercise_name": "Conventional Deadlift",
                            "order": 1,
                            "sets": [
                                {"reps": 5, "rpe": 7, "notes": "Warm up set"},
                                {"reps": 5, "rpe": 8, "notes": "Working set"},
                                {"reps": 5, "rpe": 9, "notes": "Top set"}
                            ]
                        },
                        {
                            "exercise_name": "Overhead Press",
                            "order": 2,
                            "sets": [
                                {"reps": 8, "rpe": 7, "notes": "Working set"},
                                {"reps": 8, "rpe": 8, "notes": "Working set"}
                            ]
                        }
                    ]
                }
            ]
        elif program_type == "muscle":
            routines = [
            {
                "name": "Monday: Push (Chest, Shoulders, Triceps)",
                "description": "Upper body pushing muscles",
                "exercises": [
                    {
                        "exercise_name": "Bench Press",
                        "order": 1,
                        "sets": [
                                {"reps": 8, "rpe": 7, "notes": "Warm up set"},
                                {"reps": 8, "rpe": 8, "notes": "Working set"},
                            {"reps": 6, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Overhead Press",
                        "order": 2,
                        "sets": [
                                {"reps": 10, "rpe": 8, "notes": "Working set"},
                                {"reps": 10, "rpe": 8, "notes": "Working set"}
                        ]
                    },
                    {
                        "exercise_name": "Dips",
                        "order": 3,
                        "sets": [
                                {"reps": 12, "rpe": 7, "notes": "Working set"},
                                {"reps": 12, "rpe": 8, "notes": "Working set"}
                        ]
                    }
                ]
            },
            {
                "name": "Tuesday: Pull (Back, Biceps)",
                "description": "Upper body pulling muscles",
                "exercises": [
                    {
                        "exercise_name": "Pull-ups",
                        "order": 1,
                        "sets": [
                                {"reps": 6, "rpe": 7, "notes": "Working set"},
                                {"reps": 6, "rpe": 8, "notes": "Working set"},
                            {"reps": 4, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Barbell Row",
                        "order": 2,
                        "sets": [
                                {"reps": 10, "rpe": 8, "notes": "Working set"},
                                {"reps": 10, "rpe": 8, "notes": "Working set"}
                        ]
                    }
                ]
            },
            {
                "name": "Thursday: Legs (Quads, Glutes, Hamstrings)",
                "description": "Lower body muscles",
                "exercises": [
                    {
                            "exercise_name": "Back Squat",
                        "order": 1,
                        "sets": [
                                {"reps": 10, "rpe": 7, "notes": "Warm up set"},
                                {"reps": 10, "rpe": 8, "notes": "Working set"},
                                {"reps": 8, "rpe": 9, "notes": "Top set"}
                        ]
                    },
                    {
                        "exercise_name": "Romanian Deadlift",
                        "order": 2,
                        "sets": [
                                {"reps": 12, "rpe": 8, "notes": "Working set"},
                                {"reps": 12, "rpe": 8, "notes": "Working set"}
                        ]
                    }
                ]
            },
            {
                "name": "Saturday: Push (Chest, Shoulders, Triceps)",
                "description": "Upper body pushing muscles - variation",
                "exercises": [
                    {
                        "exercise_name": "Incline Bench Press",
                        "order": 1,
                        "sets": [
                            {"reps": 8, "rpe": 8, "notes": "Working set"},
                                {"reps": 8, "rpe": 8, "notes": "Working set"}
                            ]
                        }
                    ]
                }
            ]
        else:  # general
            routines = [
                            {
                "name": "Monday: Full Body",
                "description": "Complete body workout",
                    "exercises": [
                        {
                            "exercise_name": "Squat",
                            "order": 1,
                            "sets": [
                                {"reps": 10, "rpe": 7, "notes": "Working set"},
                                {"reps": 10, "rpe": 8, "notes": "Working set"}
                            ]
                        },
                        {
                            "exercise_name": "Push-ups",
                            "order": 2,
                            "sets": [
                                {"reps": 12, "rpe": 7, "notes": "Working set"},
                                {"reps": 12, "rpe": 8, "notes": "Working set"}
                            ]
                        },
                        {
                            "exercise_name": "Pull-ups",
                            "order": 3,
                            "sets": [
                                {"reps": 8, "rpe": 7, "notes": "Working set"},
                                {"reps": 8, "rpe": 8, "notes": "Working set"}
                            ]
                        }
                    ]
                }
            ]

        return {
            "type": "program_generated",
            "program": {
                "name": f"{days}-Day {program_type.title()} Program",
                "description": f"A {program_type} training program based on your conversation",
                "scheduling_type": "weekly",
                "routines": routines[:days]  # Only include the number of days requested
            }
        }


class ConversationManager:
    """Manages AI conversation state using Redis and persistent logging"""

    def __init__(self):
        # Use django_redis which works with SSL configuration
        if get_redis_connection:
            self.redis = get_redis_connection("default")
        else:
            self.redis = None

    def get_conversation_key(self, user_id, session_id):
        return f"ai_conversation:{user_id}:{session_id}"

    def save_conversation(self, user_id, session_id, conversation_history):
        # Save to Redis for active session
        if self.redis:
            key = self.get_conversation_key(user_id, session_id)
            self.redis.set(key, json.dumps(conversation_history), ex=3600)  # 1 hour expiry

        # Also save to database for debugging
        self._log_conversation(user_id, session_id, conversation_history)

    def get_conversation(self, user_id, session_id):
        if self.redis:
            key = self.get_conversation_key(user_id, session_id)
            data = self.redis.get(key)
            if data:
                return json.loads(data.decode('utf-8'))
        return []

    def clear_conversation(self, user_id, session_id):
        if self.redis:
            key = self.get_conversation_key(user_id, session_id)
            self.redis.delete(key)

    def _log_conversation(self, user_id, session_id, conversation_history):
        """Save conversation to database for debugging"""
        try:
            from django.contrib.auth.models import User
            from .models import ConversationLog

            user = User.objects.get(id=user_id)

            # Update or create conversation log
            log, created = ConversationLog.objects.update_or_create(
                user=user,
                session_id=session_id,
                defaults={
                    'conversation_data': conversation_history,
                }
            )
            print(f"[DEBUG] Logged conversation {session_id} with {len(conversation_history)} messages")
        except Exception as e:
            print(f"[DEBUG] Failed to log conversation: {e}")

    def log_outcome(self, user_id, session_id, program_generated=False, program_accepted=False, error_message=""):
        """Log the outcome of a conversation"""
        try:
            from django.contrib.auth.models import User
            from .models import ConversationLog

            log = ConversationLog.objects.filter(
                user_id=user_id,
                session_id=session_id
            ).first()

            if log:
                log.program_generated = program_generated
                log.program_accepted = program_accepted
                log.error_occurred = bool(error_message)
                log.error_message = error_message
                log.save()
                print(f"[DEBUG] Logged outcome for {session_id}: generated={program_generated}, accepted={program_accepted}")
        except Exception as e:
            print(f"[DEBUG] Failed to log outcome: {e}")