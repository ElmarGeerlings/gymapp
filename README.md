# Gainz Workout Tracker

Gainz is a Django-powered workout companion that helps lifters plan structured programs, log detailed sessions, analyze progress, and share milestones with friends. The app combines classic workout logging with AI-assisted program design, rich analytics, and a lightweight social layer.

## Highlights
- **Training pipeline**: Build programs, attach reusable routines, and launch templated workouts with automatic set prefill and progression helpers.
- **AI program builder**: Guided conversation with Google Gemini generates tailored weekly plans that can be accepted straight into your account.
- **Smart logging**: Track exercises, sets, rest timers, performance feedback, and personal records with support for custom exercises and timer preferences.
- **Progress insights**: Summaries for volume, consistency, top exercises, and per-exercise strength trends, ready for future chart visualizations.
- **Social hub**: Follow friends, like and comment on workouts, and control visibility through profile privacy settings.
- **Extensible API**: REST endpoints (via DRF) expose workouts, exercises, timer preferences, and analytics for mobile or third-party integrations.

## Tech Stack
- Python 3.9+ / Django 3.2
- Django REST Framework
- PostgreSQL (via DATABASE_URL) with SQLite fallback for local dev
- Redis for caching conversation state and async queues
- Google Gemini API for AI-assisted program creation
- Bootstrap 5, Font Awesome, and vanilla JS (gainz.js, 	imer.js) on the frontend

## Project Structure
`	ext
.
+-- gainz/
�   +-- ai/                # AI conversation flow, Gemini service, conversation logs
�   +-- exercises/         # Exercise catalog, categories, management commands
�   +-- workouts/          # Programs, routines, workouts, timer prefs, parsing utils
�   +-- social/            # Follow graph, likes, comments, social feed views
�   +-- templates/         # Django templates (workouts, progress, social, AI chat)
�   +-- static/            # Styles, timers, dashboard scripts
+-- config/                # Alternate settings modules (legacy)
+-- requirements.txt       # Python dependencies
+-- render.yaml            # Render deployment definition
+-- build.sh               # Deploy build script (install, migrate, create admin)
+-- manage.py
`

## Key Features in Depth
- **Programs & routines** (gainz/workouts/models.py:1): Organize training by linking routines to weekly schedules, auto-enforcing a single active program per user.
- **Workout logging** (gainz/workouts/models.py:73): Capture per-set data, performance feedback, and visibility controls; includes helpers for 1RM estimation and volume tracking.
- **Timer preferences** (gainz/workouts/models.py:196): User, program, and routine-level overrides plus exercise-specific timers that power the 	imer.js rest timer UI.
- **Progress analytics** (gainz/utils/progress_tracking.py:1): Aggregates workouts, volume, consistency, top exercises, and strength gains for dashboard views.
- **AI conversation** (gainz/ai/services.py:1, gainz/ai/views.py:1): Conversation manager backed by Redis + DB logging, Gemini prompt orchestration, and program finalization.
- **Social layer** (gainz/social/models.py:1, gainz/social/views.py:1): Profiles, follow relationships, likes, comments, and feed/search pages.
- **Import helpers** (gainz/workouts/utils.py:120): Parse text workout logs, map exercises (with alternative names), and prefill targets when launching workouts from routines.

## REST API Surface
Core endpoints are under /api/ and secured with session authentication.
- GET /api/exercises/ � List shared and user-created exercises.
- POST /api/exercises/ � Create custom exercises.
- GET /api/workouts/ � Retrieve workouts with nested exercises/sets.
- POST /api/workouts/{id}/reorder-exercises/ � Update exercise ordering.
- POST /api/workouts/exercises/{id}/sets/ � Append a logged set.
- GET /api/timer-preferences/ plus related program/routine and per-exercise timer endpoints.
- GET /api/progress/exercise/{id}/chart-data/ � Data feed for future charting.
- POST /ai/conversation/ and POST /ai/finalize/ � AI chat loop and program creation (AJAX driven).

Refer to gainz/urls.py:12 for the full route map, including social endpoints under /social/ and development helpers.

## Frontend Notes
- Responsive layout in gainz/templates/base.html with Bootstrap navigation and mobile detection switching to workout_detail_mobile.html.
- gainz/static/gainz.js centralizes AJAX helpers, toasts, workout interactions, and profile preferences.
- gainz/static/timer.js provides a localStorage-backed rest timer with auto-start hooks tied to workout logging events.
- Progress dash templates (gainz/templates/progress/*.html) already surface metrics; chart placeholders will use progress_charts.js once wired to a charting lib.