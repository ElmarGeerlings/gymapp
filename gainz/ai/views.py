import json
import uuid
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages

from gainz.ai.services import WorkoutProgramAI, ConversationManager
from gainz.ai.program_creator import AIProgramCreator


@login_required
def ai_program_create(request):
    """Start AI-powered program creation conversation"""
    session_id = str(uuid.uuid4())
    return render(request, 'ai_program_chat.html', {
        'title': 'Create Program with AI',
        'session_id': session_id
    })


@csrf_exempt
@login_required
def ai_conversation(request):
    """Handle AI conversation via AJAX/WebSocket"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    user_input = data.get('message', '')
    session_id = data.get('session_id', '')

    if not user_input or not session_id:
        return JsonResponse({'error': 'Message and session_id required'}, status=400)

    # Initialize services
    ai_service = WorkoutProgramAI()
    conversation_manager = ConversationManager()

    # Get conversation history
    conversation_history = conversation_manager.get_conversation(request.user.id, session_id)

    # Add user message to history
    conversation_history.append({
        'role': 'user',
        'content': user_input
    })

        # Check if this is a program generation request
    if user_input.lower() in ['generate now', 'please generate a workout program with the information we have so far', 'generate program now', 'create program']:
        # Use the specialized force generation method
        ai_response = ai_service.force_program_generation(conversation_history)
        print(f"[DEBUG] Force Generate Response: {ai_response}")  # Debug logging

        # Log program generation attempt
        if ai_response.get('type') == 'program_generated':
            conversation_manager.log_outcome(request.user.id, session_id, program_generated=True)
    elif user_input.lower() in ['accept this program', 'accept program']:
        # User wants to accept the program - trigger the finalize flow
        ai_response = {
            "type": "accept_program",
            "message": "Perfect! Let me create this program for you in the app."
        }
    else:
        # Normal conversation
        ai_response = ai_service.process_conversation(user_input, conversation_history)

    # Add AI response to history
    conversation_history.append({
        'role': 'assistant',
        'content': json.dumps(ai_response) if isinstance(ai_response, dict) else ai_response
    })

    # Save updated conversation
    conversation_manager.save_conversation(request.user.id, session_id, conversation_history)

    return JsonResponse(ai_response)


@login_required
def ai_program_finalize(request):
    """Finalize and create the AI-generated program"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    program_data = data.get('program_data')
    session_id = data.get('session_id')

    if not program_data:
        return JsonResponse({'error': 'Program data required'}, status=400)

    # Create the program using the AI data
    creator = AIProgramCreator()
    program = creator.create_program_from_ai_data(request.user, program_data)

    if program:
        # Log successful program acceptance
        conversation_manager = ConversationManager()
        conversation_manager.log_outcome(request.user.id, session_id, program_accepted=True)
        conversation_manager.clear_conversation(request.user.id, session_id)

        messages.success(request, f'AI-generated program "{program.name}" created successfully!')
        return JsonResponse({
            'success': True,
            'redirect_url': f'/programs/'
        })
    else:
        # Log program creation failure
        conversation_manager = ConversationManager()
        conversation_manager.log_outcome(request.user.id, session_id, error_message="Failed to create program from AI data")
        return JsonResponse({
            'error': 'Failed to create program. Please try again.'
        }, status=500)