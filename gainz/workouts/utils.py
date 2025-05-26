import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

from gainz.workouts.models import Workout, ExerciseSet, RoutineExerciseSet, RoutineExercise, Routine
from gainz.exercises.models import Exercise


# Helper to resolve target_reps string to an integer
def _resolve_target_reps_to_integer(target_reps_str, default_amrap_reps=10):
    if not target_reps_str:
        return None
    target_reps_str = str(target_reps_str).lower()
    if "amrap" in target_reps_str:
        return default_amrap_reps
    
    # Check for a range like "8-12" and take the lower bound.
    match = re.match(r"(\d+)\s*-\s*(\d+)", target_reps_str)
    if match:
        return int(match.group(1))
    
    # Check for a specific number.
    match = re.match(r"(\d+)", target_reps_str)
    if match:
        return int(match.group(1))
    
    return None # Or raise an error, or a default

# Epley formula for 1RM estimation
def _calculate_epley_1rm(weight, reps):
    if reps == 0 or weight == 0: # Avoid division by zero or nonsensical 1RM
        return Decimal('0.0')
    if reps == 1:
        return Decimal(weight)
    # 1RM = weight * (1 + 0.0333 * reps)
    return Decimal(weight) * (Decimal('1') + (Decimal('0.0333') * Decimal(reps)))

# Reps to %1RM mapping (simplified - can be expanded and made more granular)
REPS_TO_PERCENT_1RM = {
    1: Decimal('1.00'),
    2: Decimal('0.95'),
    3: Decimal('0.93'),
    4: Decimal('0.90'),
    5: Decimal('0.87'),
    6: Decimal('0.85'),
    7: Decimal('0.83'),
    8: Decimal('0.80'),
    9: Decimal('0.77'),
    10: Decimal('0.75'),
    11: Decimal('0.73'), # Approximated
    12: Decimal('0.70'), # Approximated
    13: Decimal('0.68'), # Approximated
    14: Decimal('0.67'), # Approximated
    15: Decimal('0.65'), # Approximated
}

def _get_weight_from_1rm_for_reps(one_rm_estimate, target_reps):
    if not one_rm_estimate or one_rm_estimate <= 0 or not target_reps or target_reps <= 0:
        return None

    # Find closest percentage for target_reps
    # If target_reps is in the map, use it directly
    if target_reps in REPS_TO_PERCENT_1RM:
        percentage = REPS_TO_PERCENT_1RM[target_reps]
    else:
        # Interpolate or find closest if not directly in map
        # For simplicity, if reps > 15 (max in our current map), we might not be able to estimate well
        # or we take the percentage for 15 reps. Let's cap it for now.
        if target_reps > 15:
             percentage = REPS_TO_PERCENT_1RM.get(15, Decimal('0.65')) # Default to 15 rep percentage
        else: # Try to find the closest lower rep count
            closest_reps = max(r for r in REPS_TO_PERCENT_1RM if r <= target_reps)
            percentage = REPS_TO_PERCENT_1RM[closest_reps]
            
    if percentage is None:
        return None
        
    # Estimated weight = 1RM * percentage
    # Quantize to typical weight increments (e.g., 2.5 lbs or 1 kg)
    # For simplicity here, just rounding to 2 decimal places, as model weights are.
    estimated_weight = (one_rm_estimate * percentage).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return estimated_weight


def get_prefill_data(user, routine_exercise_set_template: RoutineExerciseSet, current_date: date):
    suggested_reps = None
    suggested_weight = None
    
    routine_exercise = routine_exercise_set_template.routine_exercise
    base_exercise = routine_exercise.exercise

    # --- 1. Last Logged Performance (Same Routine, Same Set Number) ---
    # Find the most recent Workout by user linked to routine_exercise_set_template.routine_exercise.
    # From that workout, get the actual reps and weight logged for the ExerciseSet
    # corresponding to routine_exercise_set_template.set_number.
    last_workout_with_routine_exercise = Workout.objects.filter(
        user=user,
        routine_source=routine_exercise.routine, # Ensure workout is from the same routine
        exercises__routine_exercise_source=routine_exercise # Link WorkoutExercise back to the RoutineExercise
    ).order_by('-date').first()

    if last_workout_with_routine_exercise:
        workout_exercise_instance = last_workout_with_routine_exercise.exercises.filter(
            routine_exercise_source=routine_exercise
        ).first()
        if workout_exercise_instance:
            logged_set = ExerciseSet.objects.filter(
                workout_exercise=workout_exercise_instance,
                set_number=routine_exercise_set_template.set_number
            ).first()
            if logged_set:
                suggested_reps = logged_set.reps
                suggested_weight = logged_set.weight
                return {'reps': suggested_reps, 'weight': suggested_weight}

    # --- 2. First Time with Routine - Use Template Values ---
    template_target_reps_int = _resolve_target_reps_to_integer(routine_exercise_set_template.target_reps)
    template_target_weight = routine_exercise_set_template.target_weight

    if template_target_reps_int is not None: # If target_reps is something, use it
        suggested_reps = template_target_reps_int
        if template_target_weight is not None:
            suggested_weight = template_target_weight
            # If both reps and weight are from template, we can return.
            # If weight is null, we will proceed to try and find a weight.
            return {'reps': suggested_reps, 'weight': suggested_weight} 
            # This rule only pre-fills both if both template values are present.
            # If only target_reps is present, we will use it but then try to find a weight in step 3 or 4.
    
    # If we are here, either the template didn't have weight, or didn't have reps.
    # We need a rep count for the next steps.
    if suggested_reps is None and template_target_reps_int:
        suggested_reps = template_target_reps_int
    elif suggested_reps is None: # Still no reps, try to get a default (e.g. 10 if not specified at all)
        suggested_reps = _resolve_target_reps_to_integer(None) # Will use default_amrap_reps=10

    # If template_target_weight was None, we proceed to find a weight using suggested_reps (which is now set)

    # --- 3. Match Reps in Most Recent Workout (Any Routine, Same Base Exercise) ---
    if suggested_reps is not None: # We need a rep target for this logic
        last_workout_with_base_exercise = Workout.objects.filter(
            user=user,
            exercises__exercise=base_exercise
        ).order_by('-date').first()

        if last_workout_with_base_exercise:
            # Find WorkoutExercise instances for the base exercise in that last workout
            workout_exercises_for_base = last_workout_with_base_exercise.exercises.filter(exercise=base_exercise)
            
            matching_sets = ExerciseSet.objects.filter(
                workout_exercise__in=workout_exercises_for_base,
                reps=suggested_reps
            ).order_by('-weight') # Heaviest weight first
            
            best_matching_set = matching_sets.first()
            if best_matching_set:
                suggested_weight = best_matching_set.weight
                return {'reps': suggested_reps, 'weight': suggested_weight}

    # --- 4. Estimate via 1RM (from best set in last session, detraining adjustment) ---
    if suggested_reps is not None: # We still need a rep target
        template_target_reps_for_estimation = suggested_reps # Use the already resolved/defaulted rep count

        if template_target_reps_for_estimation <= 15: # Rep Limit Check (Input)
            last_workout_for_1rm = Workout.objects.filter(
                user=user,
                exercises__exercise=base_exercise
            ).order_by('-date').first()

            if last_workout_for_1rm:
                workout_exercises_for_1rm = last_workout_for_1rm.exercises.filter(exercise=base_exercise)
                
                highest_1rm_estimate = Decimal('0.0')
                workout_date_for_highest_1rm = None

                sets_for_1rm_calc = ExerciseSet.objects.filter(workout_exercise__in=workout_exercises_for_1rm)

                for s_set in sets_for_1rm_calc:
                    if s_set.reps <= 15 and s_set.reps > 0 and s_set.weight > 0: # Rep Limit Check (Historical Set) and valid data
                        current_set_1rm = _calculate_epley_1rm(s_set.weight, s_set.reps)
                        if current_set_1rm > highest_1rm_estimate:
                            highest_1rm_estimate = current_set_1rm
                            workout_date_for_highest_1rm = last_workout_for_1rm.date.date() # Store date part only
                
                if highest_1rm_estimate > Decimal('0.0'):
                    estimated_weight_for_reps = _get_weight_from_1rm_for_reps(highest_1rm_estimate, template_target_reps_for_estimation)
                    
                    if estimated_weight_for_reps is not None:
                        # Detraining Adjustment
                        if workout_date_for_highest_1rm and (current_date - workout_date_for_highest_1rm) > timedelta(days=90): # > 3 months
                            estimated_weight_for_reps *= Decimal('0.9') # Reduce by 10%
                            estimated_weight_for_reps = estimated_weight_for_reps.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

                        suggested_weight = estimated_weight_for_reps
                        return {'reps': suggested_reps, 'weight': suggested_weight}
    
    # --- 5. Empty Field ---
    # If suggested_reps has a value (from template or default), but no weight was found, return reps with None weight
    if suggested_reps is not None and suggested_weight is None:
        return {'reps': suggested_reps, 'weight': None}
        
    # If all else fails, return no pre-fill
    return {'reps': None, 'weight': None} 