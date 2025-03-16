// CSRF token for AJAX requests
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Add a new set to an exercise
async function addSet(workoutExerciseId) {
    const weightInput = document.getElementById(`weight-${workoutExerciseId}`);
    const repsInput = document.getElementById(`reps-${workoutExerciseId}`);
    const warmupInput = document.getElementById(`warmup-${workoutExerciseId}`);
    
    const weight = parseFloat(weightInput.value);
    const reps = parseInt(repsInput.value);
    const isWarmup = warmupInput.checked;
    
    if (!weight || !reps) {
        alert('Please enter both weight and reps');
        return;
    }
    
    try {
        const response = await fetch(`/api/workouts/exercises/${workoutExerciseId}/sets/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                weight: weight,
                reps: reps,
                is_warmup: isWarmup
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            // Update the UI
            const setsTable = document.getElementById(`sets-${workoutExerciseId}`);
            const newRow = document.createElement('tr');
            newRow.innerHTML = `
                <td>${data.set_number}</td>
                <td>${data.weight} kg</td>
                <td>${data.reps}</td>
                <td>${data.is_warmup ? 'Warmup' : 'Working'}</td>
                <td>
                    <button class="edit-set-btn" data-set-id="${data.id}">Edit</button>
                    <button class="delete-set-btn" data-set-id="${data.id}">Delete</button>
                </td>
            `;
            setsTable.appendChild(newRow);
            
            // Clear inputs
            weightInput.value = '';
            repsInput.value = '';
            warmupInput.checked = false;
        } else {
            alert('Error adding set');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error adding set');
    }
}

// Add a new exercise to the workout
async function addExercise(workoutId) {
    const exerciseId = document.getElementById('exercise-select').value;
    const exerciseType = document.getElementById('exercise-type').value;
    
    if (!exerciseId) {
        alert('Please select an exercise');
        return;
    }
    
    try {
        const response = await fetch(`/api/workouts/${workoutId}/add_exercise/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                exercise: exerciseId,
                exercise_type: exerciseType
            })
        });
        
        if (response.ok) {
            // Reload the page to show the new exercise
            location.reload();
        } else {
            alert('Error adding exercise');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error adding exercise');
    }
}

// Delete a set
document.addEventListener('click', async function(e) {
    if (e.target.classList.contains('delete-set-btn')) {
        if (confirm('Are you sure you want to delete this set?')) {
            const setId = e.target.dataset.setId;
            
            try {
                const response = await fetch(`/api/workouts/sets/${setId}/`, {
                    method: 'DELETE',
                    headers: {
                        'X-CSRFToken': getCsrfToken()
                    }
                });
                
                if (response.ok) {
                    // Remove the row from the table
                    e.target.closest('tr').remove();
                } else {
                    alert('Error deleting set');
                }
            } catch (error) {
                console.error('Error:', error);
                alert('Error deleting set');
            }
        }
    }
}); 