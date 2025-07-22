# AI Integration Setup Instructions

## 1. Get Your Free Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click "Create API Key"
4. Copy the generated API key

## 2. Set Environment Variable

### Windows (Command Prompt):
```bash
set GEMINI_API_KEY=AIzaSyD2m3VdvGxI0XPkxzLnCAb2AdvILZkBnUo
```

### Windows (PowerShell):
```bash
$env:GEMINI_API_KEY="AIzaSyD2m3VdvGxI0XPkxzLnCAb2AdvILZkBnUo"
```

### Alternative: Add to your batch file
Add this line to your `start_gainz.bat`:
```bash
set GEMINI_API_KEY=AIzaSyD2m3VdvGxI0XPkxzLnCAb2AdvILZkBnUo
```

## 3. Install Required Dependency

The AI integration uses the `requests` library, which should already be installed. If not:
```bash
pip install requests
```

## 4. Test the Integration

1. Start your Django server
2. Navigate to `/programs/`
3. Click the "Create with AI" button
4. Try the conversation interface

## 5. How It Works

### User Flow:
1. **Start Conversation**: User clicks "Create with AI"
2. **Smart Questions**: AI asks adaptive questions based on responses
3. **Program Generation**: When ready, AI generates a structured workout program
4. **Review & Accept**: User can review, modify, or accept the program
5. **Database Creation**: Accepted programs are saved to your database

### Technical Flow:
- **AI Service**: Uses Google Gemini 1.5 Flash (free tier)
- **Conversation Management**: Uses Redis to store chat history
- **Program Creation**: Converts AI JSON responses to Django models
- **Real-time Chat**: AJAX-based conversation interface

## 6. Customization Options

### Modify AI Behavior:
Edit the `SYSTEM_PROMPT` in `gainz/ai/services.py` to change how the AI asks questions or structures programs.

### Add More Exercises:
The AI will automatically create new exercises if they don't exist in your database, or you can pre-populate your exercise database.

### Adjust Program Structure:
Modify the `AIProgramCreator` class to change how AI responses are converted to database objects.

## 7. Usage Limits

- **Gemini Free Tier**: 15 requests per minute, 1500 requests per day
- **Perfect for personal use**: Should handle multiple program creations easily
- **Conversation Storage**: 1 hour expiry in Redis (adjustable)

## 8. Troubleshooting

### "GEMINI_API_KEY not found" error:
- Make sure you've set the environment variable
- Restart your Django server after setting the variable
- Check that the variable is available: `echo %GEMINI_API_KEY%` (Windows)

### AI not responding:
- Check your internet connection
- Verify your API key is valid
- Check Django logs for detailed error messages

### Program creation failed:
- Make sure you have exercises in your database
- Check that the AI response format is valid JSON
- Review the conversation history in Redis if needed