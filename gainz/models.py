# Convenience imports for all Django models
# Import all models at once: from gainz.models import *

# Exercises app models
from gainz.exercises.models import (
    ExerciseCategory,
    Exercise,
    ExerciseAlternativeName,
)

# Workouts app models
from gainz.workouts.models import (
    Program,
    ProgramRoutine,
    Routine,
    RoutineExercise,
    RoutineExerciseSet,
    Workout,
    WorkoutExercise,
    ExerciseSet,
    UserTimerPreference,
    ExerciseTimerOverride,
    PersonalRecord,
    ProgramTimerPreference,
    RoutineTimerPreference,
)

# Social app models
from gainz.social.models import (
    UserProfile,
    UserFollow,
    WorkoutLike,
    WorkoutComment,
)

# AI app models
from gainz.ai.models import (
    ConversationLog,
)

# Export all models for easy importing
__all__ = [
    # Exercises
    'ExerciseCategory',
    'Exercise',
    'ExerciseAlternativeName',

    # Workouts
    'Program',
    'ProgramRoutine',
    'Routine',
    'RoutineExercise',
    'RoutineExerciseSet',
    'Workout',
    'WorkoutExercise',
    'ExerciseSet',
    'UserTimerPreference',
    'ExerciseTimerOverride',
    'PersonalRecord',
    'ProgramTimerPreference',
    'RoutineTimerPreference',

    # Social
    'UserProfile',
    'UserFollow',
    'WorkoutLike',
    'WorkoutComment',

    # AI
    'ConversationLog',
]
