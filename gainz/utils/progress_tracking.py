"""
Progress Tracking Utilities

This module provides utilities for tracking workout and exercise progress,
calculating statistics, and managing personal records.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from decimal import Decimal
from django.db.models import QuerySet, Q, Max, Min, Avg
from django.utils import timezone

from ..workouts.models import Workout, WorkoutExercise, PersonalRecord, ExerciseSet
from ..exercises.models import Exercise


@dataclass
class ProgressMetrics:
    """Data class for storing progress metrics"""
    total_workouts: int
    total_exercises: int
    total_volume: Decimal
    average_duration: timedelta
    strength_gains: Dict[str, Decimal]
    consistency_score: float
    personal_records: int


@dataclass
class ExerciseProgress:
    """Data class for exercise-specific progress tracking"""
    exercise_name: str
    current_max: Optional[Decimal]
    previous_max: Optional[Decimal]
    improvement: Optional[Decimal]
    improvement_percentage: Optional[float]
    sessions_count: int
    last_performed: Optional[datetime]
    trend: str  # 'improving', 'declining', 'stable'
    best_1rm: Optional[Decimal] = None
    total_volume: Decimal = Decimal('0')
    workout_count: int = 0


@dataclass
class StrengthTrend:
    """Data class for strength trend analysis"""
    period: str
    volume_change: Decimal
    strength_change: Decimal
    consistency: float
    top_exercises: List[str]


def calculate_workout_volume(workout: Workout) -> Decimal:
    """
    Calculate total volume (weight × reps × sets) for a workout session.
    
    Args:
        workout: Workout instance
        
    Returns:
        Total volume as Decimal
    """
    total_volume = Decimal('0')
    
    for exercise in workout.exercises.all():
        for exercise_set in exercise.sets.all():
            if exercise_set.weight and exercise_set.reps:
                set_volume = exercise_set.weight * exercise_set.reps
                total_volume += set_volume
    
    return total_volume


def get_progress_metrics(user, period_days: int = 30) -> ProgressMetrics:
    """
    Calculate comprehensive progress metrics for a user over a specified period.
    
    Args:
        user: User instance
        period_days: Number of days to look back (default: 30)
        
    Returns:
        ProgressMetrics instance with calculated metrics
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Get workout sessions in the period
    sessions = Workout.objects.filter(
        user=user,
        date__range=[start_date, end_date]
    )
    
    total_workouts = sessions.count()
    
    # Calculate total exercises
    total_exercises = WorkoutExercise.objects.filter(
        workout__in=sessions
    ).count()
    
    # Calculate total volume
    total_volume = Decimal('0')
    total_duration = timedelta()
    
    for session in sessions:
        total_volume += calculate_workout_volume(session)
        if session.duration:
            total_duration += session.duration
    
    # Calculate average duration
    average_duration = total_duration / total_workouts if total_workouts > 0 else timedelta()
    
    # Calculate strength gains by exercise
    strength_gains = calculate_strength_gains(user, period_days)
    
    # Calculate consistency score (workouts per week)
    weeks = period_days / 7
    consistency_score = (total_workouts / weeks) if weeks > 0 else 0
    
    # Count personal records in period
    personal_records = PersonalRecord.objects.filter(
        user=user,
        date_achieved__range=[start_date, end_date]
    ).count()
    
    return ProgressMetrics(
        total_workouts=total_workouts,
        total_exercises=total_exercises,
        total_volume=total_volume,
        average_duration=average_duration,
        strength_gains=strength_gains,
        consistency_score=consistency_score,
        personal_records=personal_records
    )


def calculate_strength_gains(user, period_days: int = 30) -> Dict[str, Decimal]:
    """
    Calculate strength gains by exercise over a specified period.
    
    Args:
        user: User instance
        period_days: Number of days to look back
        
    Returns:
        Dictionary mapping exercise names to strength gain percentages
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    strength_gains = {}
    
    # Get all exercises the user has performed
    exercises = Exercise.objects.filter(
        workoutexercise__workout__user=user
    ).distinct()
    
    for exercise in exercises:
        # Get exercise sets from first and last workout with this exercise in the period
        
        exercise_sets = ExerciseSet.objects.filter(
            workout_exercise__workout__user=user,
            workout_exercise__exercise=exercise,
            workout_exercise__workout__date__range=[start_date, end_date],
            weight__isnull=False
        ).order_by('workout_exercise__workout__date')
        
        if exercise_sets.count() < 2:
            continue
            
        # Get max weight from first and last periods
        first_period_sets = exercise_sets.filter(
            workout_exercise__workout__date__lte=start_date + timedelta(days=period_days//2)
        )
        last_period_sets = exercise_sets.filter(
            workout_exercise__workout__date__gte=start_date + timedelta(days=period_days//2)
        )
        
        if first_period_sets.exists() and last_period_sets.exists():
            initial_strength = first_period_sets.aggregate(Max('weight'))['weight__max']
            current_strength = last_period_sets.aggregate(Max('weight'))['weight__max']
            
            if initial_strength and current_strength and initial_strength > 0:
                gain_percentage = ((current_strength - initial_strength) / initial_strength) * 100
                strength_gains[exercise.name] = gain_percentage
    
    return strength_gains


def get_exercise_progress(user, exercise: Exercise, period_days: int = 90) -> ExerciseProgress:
    """
    Get detailed progress information for a specific exercise.
    
    Args:
        user: User instance
        exercise: Exercise instance
        period_days: Number of days to analyze
        
    Returns:
        ExerciseProgress instance with detailed progress data
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Get all workout exercises for this exercise
    
    workout_exercises = WorkoutExercise.objects.filter(
        workout__user=user,
        exercise=exercise,
        workout__date__range=[start_date, end_date]
    ).order_by('workout__date')
    
    sessions_count = workout_exercises.count()
    
    if sessions_count == 0:
        return ExerciseProgress(
            exercise_name=exercise.name,
            current_max=None,
            previous_max=None,
            improvement=None,
            improvement_percentage=None,
            sessions_count=0,
            last_performed=None,
            trend='stable'
        )
    
    # Calculate current max from exercise sets
    current_exercise_sets = ExerciseSet.objects.filter(
        workout_exercise__workout__user=user,
        workout_exercise__exercise=exercise,
        workout_exercise__workout__date__range=[start_date, end_date],
        weight__isnull=False
    ).select_related('workout_exercise__workout', 'workout_exercise__exercise')

    current_max = current_exercise_sets.aggregate(Max('weight'))['weight__max'] if current_exercise_sets.exists() else None
    last_performed = workout_exercises.last().workout.date

    total_volume = Decimal('0')
    best_1rm = None
    for exercise_set in current_exercise_sets:
        if not exercise_set.is_warmup:
            total_volume += exercise_set.get_volume()
        if exercise_set.is_valid_for_1rm():
            estimate = exercise_set.get_best_1rm_estimate()
            if estimate is not None:
                if best_1rm is None or estimate > best_1rm:
                    best_1rm = estimate
    
    # Calculate previous max (from earlier period)
    previous_period_start = start_date - timedelta(days=period_days)
    previous_exercise_sets = ExerciseSet.objects.filter(
        workout_exercise__workout__user=user,
        workout_exercise__exercise=exercise,
        workout_exercise__workout__date__range=[previous_period_start, start_date],
        weight__isnull=False
    )
    
    previous_max = previous_exercise_sets.aggregate(Max('weight'))['weight__max'] if previous_exercise_sets.exists() else None
    
    # Calculate improvement
    improvement = None
    improvement_percentage = None
    trend = 'stable'
    
    if current_max and previous_max:
        improvement = current_max - previous_max
        improvement_percentage = float((improvement / previous_max) * 100)
        
        if improvement_percentage > 5:
            trend = 'improving'
        elif improvement_percentage < -5:
            trend = 'declining'
    
    workout_count = workout_exercises.values('workout_id').distinct().count()

    return ExerciseProgress(
        exercise_name=exercise.name,
        current_max=current_max,
        previous_max=previous_max,
        improvement=improvement,
        improvement_percentage=improvement_percentage,
        sessions_count=sessions_count,
        last_performed=last_performed,
        trend=trend,
        best_1rm=best_1rm,
        total_volume=total_volume,
        workout_count=workout_count
    )


def analyze_strength_trends(user, periods: List[int] = [7, 30, 90]) -> List[StrengthTrend]:
    """
    Analyze strength trends over multiple time periods.
    
    Args:
        user: User instance
        periods: List of periods in days to analyze
        
    Returns:
        List of StrengthTrend instances
    """
    trends = []
    
    for period_days in periods:
        # Get metrics for this period
        metrics = get_progress_metrics(user, period_days)
        
        # Get metrics for previous period for comparison
        previous_metrics = get_progress_metrics(user, period_days * 2)
        
        # Calculate changes
        volume_change = metrics.total_volume - (previous_metrics.total_volume - metrics.total_volume)
        
        # Calculate average strength change
        strength_changes = []
        for exercise, gain in metrics.strength_gains.items():
            strength_changes.append(float(gain))
        
        avg_strength_change = sum(strength_changes) / len(strength_changes) if strength_changes else 0
        
        # Get top exercises by volume
        top_exercises = get_top_exercises_by_volume(user, period_days, limit=3)
        
        period_name = f"{period_days} days"
        if period_days == 7:
            period_name = "1 week"
        elif period_days == 30:
            period_name = "1 month"
        elif period_days == 90:
            period_name = "3 months"
        
        trends.append(StrengthTrend(
            period=period_name,
            volume_change=volume_change,
            strength_change=Decimal(str(avg_strength_change)),
            consistency=metrics.consistency_score,
            top_exercises=top_exercises
        ))
    
    return trends


def get_top_exercises_by_volume(
    user,
    period_days: int = 30,
    limit: int = 5,
    *,
    with_volume: bool = False,
) -> List[Any]:
    """
    Get the top exercises by total volume over a period.
    
    Args:
        user: User instance
        period_days: Number of days to analyze
        limit: Maximum number of exercises to return
        
    Returns:
        List of exercise names ordered by volume
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    # Calculate volume by exercise
    exercise_stats: Dict[int, Dict[str, Any]] = {}

    exercise_sets = ExerciseSet.objects.filter(
        workout_exercise__workout__user=user,
        workout_exercise__workout__date__range=[start_date, end_date],
        weight__isnull=False,
        reps__isnull=False
    ).select_related('workout_exercise__exercise')

    for exercise_set in exercise_sets:
        exercise_obj = exercise_set.workout_exercise.exercise
        if exercise_obj is None:
            continue

        if exercise_set.is_warmup:
            continue

        exercise_id = exercise_obj.id
        if exercise_id not in exercise_stats:
            exercise_stats[exercise_id] = {
                'exercise': exercise_obj,
                'volume': Decimal('0'),
                'set_count': 0,
            }

        exercise_stats[exercise_id]['volume'] += exercise_set.get_volume()
        exercise_stats[exercise_id]['set_count'] += 1

    sorted_exercises = sorted(
        exercise_stats.values(),
        key=lambda x: x['volume'],
        reverse=True
    )[:limit]

    if with_volume:
        return [
            {
                'id': data['exercise'].id,
                'name': data['exercise'].name,
                'volume': data['volume'],
                'set_count': data['set_count'],
            }
            for data in sorted_exercises
        ]

    return [data['exercise'].name for data in sorted_exercises]


def calculate_consistency_score(user, period_days: int = 30) -> float:
    """
    Calculate a consistency score based on workout frequency.
    
    Args:
        user: User instance
        period_days: Number of days to analyze
        
    Returns:
        Consistency score (0-100)
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    total_days = period_days
    workout_days = Workout.objects.filter(
        user=user,
        date__range=[start_date, end_date]
    ).dates('date', 'day').count()
    
    # Calculate consistency as percentage of days with workouts
    consistency = (workout_days / total_days) * 100 if total_days > 0 else 0
    
    # Cap at 100 and adjust for realistic expectations
    # 3-4 workouts per week is considered excellent (42-57% of days)
    adjusted_consistency = min(consistency * 1.75, 100)
    
    return round(adjusted_consistency, 2)


def get_personal_records_summary(user, period_days: int = 90) -> Dict[str, Any]:
    """
    Get a summary of personal records achieved in a period.
    
    Args:
        user: User instance
        period_days: Number of days to look back
        
    Returns:
        Dictionary containing PR summary data
    """
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)
    
    records = PersonalRecord.objects.filter(
        user=user,
        date_achieved__range=[start_date, end_date]
    ).order_by('-date_achieved')
    
    summary = {
        'total_records': records.count(),
        'records_by_type': {},
        'recent_records': [],
        'top_exercises': []
    }
    
    # Group by record type
    for record in records:
        record_type = record.record_type
        if record_type in summary['records_by_type']:
            summary['records_by_type'][record_type] += 1
        else:
            summary['records_by_type'][record_type] = 1
    
    # Get recent records (last 5)
    for record in records[:5]:
        summary['recent_records'].append({
            'exercise': record.exercise.name,
            'type': record.record_type,
            'value': record.value,
            'date': record.date_achieved
        })
    
    # Get exercises with most PRs
    exercise_pr_counts = {}
    for record in records:
        exercise_name = record.exercise.name
        if exercise_name in exercise_pr_counts:
            exercise_pr_counts[exercise_name] += 1
        else:
            exercise_pr_counts[exercise_name] = 1
    
    summary['top_exercises'] = sorted(
        exercise_pr_counts.items(),
        key=lambda x: x[1],
        reverse=True
    )[:3]

    return summary


def get_personal_records(user, period_days: int = 365, exercise: Optional[Exercise] = None) -> List[PersonalRecord]:
    """Return personal records within the given period, optionally filtered by exercise."""
    end_date = timezone.now()
    start_date = end_date - timedelta(days=period_days)

    records = PersonalRecord.objects.filter(
        user=user,
        date_achieved__range=[start_date, end_date]
    ).select_related('exercise').order_by('-date_achieved')

    if exercise is not None:
        records = records.filter(exercise=exercise)

    return list(records)
