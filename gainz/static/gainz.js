// ======================================
//          CORE FRAMEWORK
// ======================================

const observer = new MutationObserver(process_mutations);

function process_mutations(mutations) {
    mutations.forEach(mutation => {
        if (mutation.type === "attributes") {
            const attrName = mutation.attributeName;
            // Only watch data-function if data-endpoint is truly removed
            if (attrName === 'data-function') {
                handle_attribute(mutation.target, mutation.target.getAttributeNode(attrName));
            }
        } else if (mutation.type === "childList") {
            mutation.addedNodes.forEach(node => {
                if (node.nodeType === Node.ELEMENT_NODE) {
                    // Check the added node itself
                    if (node.matches('[data-function]')) {
                         handle_attribute(node, node.getAttributeNode('data-function'));
                    }
                    // Check descendants
                    node.querySelectorAll('[data-function]').forEach(element => {
                        handle_attribute(element, element.getAttributeNode('data-function'));
                    });
                }
            });
        }
    });
}

function handle_attribute(element, attr) {
    if (!attr || !attr.value) return;
    const attr_values = attr.value.trim().split(' ');
    const attrName = attr.name;

    attr_values.forEach(value => {
        const parts = value.split('->');
        if (parts.length !== 2) {
            console.warn(`Invalid ${attrName} format: ${value}. Expected eventName->targetName.`);
            return;
        }
        const [eventName, targetName] = parts;

        const listenerKey = `_${attrName}_${eventName}_${targetName}_listener`;
        if (element[listenerKey]) {
             element.removeEventListener(eventName, element[listenerKey]);
        }

        let listener;
        if (attrName === 'data-function') {
            if (typeof window[targetName] === 'function') {
                listener = (event) => window[targetName](event);
            } else {
                console.warn(`Global function ${targetName} not found.`);
                return;
            }
        }
        // Removed data-endpoint handling based on user comment
        /* else if (attrName === 'data-endpoint') {
            listener = (event) => http_request(event, targetName);
        } */

        if (listener) {
            element.addEventListener(eventName, listener);
            element[listenerKey] = listener;
        }
    });
}

// ======================================
//      HTTP REQUEST HELPER (Optional)
// ======================================
// This can be called by functions triggered via data-function if they need to make API calls.
async function httpRequestHelper(url, method = 'GET', bodyData = null, headers = {}) {
    const csrfToken = getCsrfToken();
    const defaultHeaders = {
        'X-CSRFToken': csrfToken,
        'Accept': 'application/json',
    };
    let body = null;

    if (bodyData && method.toUpperCase() !== 'GET') {
        defaultHeaders['Content-Type'] = 'application/json';
        body = JSON.stringify(bodyData);
    }

    const finalHeaders = { ...defaultHeaders, ...headers };

    try {
        const res = await fetch(url, {
            method: method.toUpperCase(),
            headers: finalHeaders,
            body
        });

        // Attempt to parse JSON, fall back to text if needed or if no content
        let responseData = null;
        const contentType = res.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
             try {
                responseData = await res.json();
             } catch (e) { /* ignore json parsing error if body is empty */ }
        } else {
             try {
                responseData = await res.text();
             } catch(e) { /* ignore text parsing error */ }
        }

        return {
            ok: res.ok,
            status: res.status,
            statusText: res.statusText,
            data: responseData,
            headers: res.headers
        };

    } catch (error) {
        console.error('Fetch error:', error);
        return {
            ok: false,
            status: 0, // Indicate network error
            statusText: 'Network Error',
            data: { detail: 'Network error. Please check your connection.' },
            error: error
        };
    }
}


// ======================================
//          MODAL FUNCTIONS
// ======================================

function show_modal(event) {
    const modalname = event.target.getAttribute('data-modal-name');
    const modal = document.getElementById(modalname);
    if (modal) {
        const form = modal.querySelector('form');
        if(form && form.id) clearFormErrors(form.id);
        modal.style.display = 'flex';
    }
    const focus = event.target.getAttribute('data-focus');
    if (focus) {
        setTimeout(() => {
            const elementToFocus = document.getElementById(focus);
             if (elementToFocus) elementToFocus.focus();
        }, 100);
    }
}

function close_modal(event) {
    // Logic to close modal by clicking background or close button
     if (event.target.classList.contains('siu-modal') || event.target.closest('.siu-modal-close')) {
        const modal = event.target.closest('.siu-modal');
        // Ensure we didn't click inside content unless it IS the close button
        if (modal && (!event.target.closest('.siu-modal-content') || event.target.closest('.siu-modal-close'))) {
             modal.style.display = 'none';
        }
    }
}

// --- Close modal with Escape key ---
document.addEventListener('keydown', (event) => {
    if (event.key === "Escape") {
        document.querySelectorAll('.siu-modal[style*="display: flex"]').forEach(modal => {
            modal.style.display = 'none';
        });
    }
});

// ======================================
//          UI UTILITIES
// ======================================

function getCsrfToken() {
    let token = document.querySelector('meta[name="csrf-token"]');
    if (token) return token.content;
    token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (token) return token.value;
    console.error('CSRF token not found');
    return null;
}

function send_toast(body, status = 'default', title = '', delete_time = 3000) {
    const alertConfigs = {
        success: { icon: 'fas fa-check-circle', alertClass: 'alert-success' },
        danger: { icon: 'fas fa-exclamation-triangle', alertClass: 'alert-danger' },
        warning: { icon: 'fas fa-exclamation-triangle', alertClass: 'alert-warning' },
        info: { icon: 'fas fa-info-circle', alertClass: 'alert-info' },
        default: { icon: 'fas fa-info-circle', alertClass: 'alert-primary' },
    };
    const { icon, alertClass } = alertConfigs[status] || alertConfigs.default;
    let toast_container = document.querySelector(".toast-container");
    if (!toast_container) {
        console.warn("Toast container not found. Creating one.");
        toast_container = document.createElement('div');
        toast_container.className = 'toast-container position-fixed top-0 end-0 p-3';
        toast_container.style.zIndex = '1100';
        document.body.appendChild(toast_container);
    }
    let toast = document.createElement('div');
    toast.className = `toast align-items-center ${alertClass} border-0 show`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');
    toast.style.pointerEvents = 'auto';
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${title ? `<strong class="me-auto"><i class="${icon}"></i> ${title}</strong><p class="mb-0">${body}</p>` : `<i class="${icon}"></i> ${body}`}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close" onclick="this.closest('.toast').remove()"></button>
        </div>
    `;
    toast_container.appendChild(toast);
    setTimeout(() => {
        const bsToast = bootstrap?.Toast?.getInstance(toast);
        if (bsToast) {
            bsToast.hide();
             toast.addEventListener('hidden.bs.toast', () => toast.remove());
        } else {
            toast.remove();
        }
    }, delete_time);
}

function displayFormErrors(formId, errors) {
    const form = document.getElementById(formId);
    if (!form) return;
    const generalErrorDiv = form.querySelector('#form-errors');
    let firstFieldWithError = null;
    if (generalErrorDiv) {
        generalErrorDiv.innerHTML = '';
        generalErrorDiv.style.display = 'none';
    }
    const nonFieldDetail = errors.non_field_errors || (errors.detail ? [errors.detail] : []);
     if (nonFieldDetail.length > 0 && generalErrorDiv) {
        generalErrorDiv.innerHTML = nonFieldDetail.join('<br>');
        generalErrorDiv.style.display = 'block';
    }
    for (const field in errors) {
        if (field !== 'non_field_errors' && field !== 'detail') {
            const errorDiv = form.querySelector(`#error-${field}`);
            const inputField = form.querySelector(`[name=${field}]`);
            if (errorDiv) {
                errorDiv.textContent = Array.isArray(errors[field]) ? errors[field].join(' ') : errors[field];
                errorDiv.style.display = 'block';
                if (!firstFieldWithError) firstFieldWithError = inputField;
            }
            if (inputField) {
                inputField.classList.add('is-invalid');
                 if (errorDiv && errorDiv.id) {
                    inputField.setAttribute('aria-describedby', errorDiv.id);
                 }
            }
        }
    }
     if (firstFieldWithError) {
         firstFieldWithError.focus();
     }
}

function clearFormErrors(formId) {
    const form = document.getElementById(formId);
    if (!form) return;

    // Clear general errors
    const generalErrorDiv = form.querySelector('#form-errors');
    if (generalErrorDiv) {
        generalErrorDiv.innerHTML = '';
        generalErrorDiv.style.display = 'none';
    }

    // Clear field-specific errors and remove invalid classes
    const errorMessages = form.querySelectorAll('.invalid-feedback');
    errorMessages.forEach(errorDiv => {
        errorDiv.textContent = '';
        errorDiv.style.display = 'none';
    });

    const invalidInputs = form.querySelectorAll('.is-invalid');
    invalidInputs.forEach(input => {
        input.classList.remove('is-invalid');
    });
}

// ======================================
//      APPLICATION-SPECIFIC FUNCTIONS
// ======================================

// --- Add Exercise Modal Submission ---
// This function will be triggered by data-function="click->saveExercise"
async function saveExercise(event) {
    const form = event.target.closest('form');
    if (!form) return;
    const formId = form.id;
    clearFormErrors(formId);

    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => {
        const inputElement = form.querySelector(`[name="${key}"]`);
        if (inputElement && inputElement.tagName === 'SELECT' && inputElement.multiple) {
            // Always get all for multi-select
            if (!data[key]) data[key] = []; // Initialize if not exists
            data[key] = formData.getAll(key);
        } else if (data.hasOwnProperty(key)) {
            // Handle multiple non-multi-select (e.g., checkboxes)
            if (!Array.isArray(data[key])) data[key] = [data[key]];
            data[key].push(value);
        } else {
            data[key] = value;
        }
    });
    data.is_custom = true; // Always set for this form

    // Use the helper for the actual request
    const response = await httpRequestHelper(form.action, 'POST', data);

    if (response.ok) {
        send_toast('Exercise added successfully!', 'success');
        const modal = form.closest('.siu-modal');
        if (modal) modal.style.display = 'none';
        form.reset();
        // Instead of full reload, maybe update list dynamically later?
        // For now, reload is simplest
        window.location.reload();
    } else {
        displayFormErrors(formId, response.data || { detail: response.statusText });
        send_toast(response.data?.detail || 'Error saving exercise.', 'danger');
    }
}

// --- Save Workout Modal Submission ---
// This function will be triggered by data-function="click->saveWorkout"
async function saveWorkout(event) {
    const form = event.target.closest('form');
    if (!form) return;
    const formId = form.id;
    clearFormErrors(formId);

    const formData = new FormData(form);
    const data = {};
    formData.forEach((value, key) => {
        data[key] = value;
    });

    // Handle duration: API expects HH:MM:SS or null
    // Basic parsing for "Xh Ym Zs" or HH:MM:SS - can be improved
    if (data.duration) {
        let durationStr = data.duration;
        let hours = 0, minutes = 0, seconds = 0;
        const timeParts = durationStr.match(/(\d+)\s*h|(\d+)\s*m|(\d+)\s*s|(\d{1,2}:\d{2}(:\d{2})?)/gi);

        if (timeParts) {
            if (durationStr.includes(':')) { // HH:MM:SS format
                const parts = durationStr.split(':');
                hours = parseInt(parts[0]) || 0;
                minutes = parseInt(parts[1]) || 0;
                seconds = parts[2] ? parseInt(parts[2]) : 0;
            } else { // Xh Ym Zs format
                timeParts.forEach(part => {
                    if (part.toLowerCase().includes('h')) hours = parseInt(part) || 0;
                    else if (part.toLowerCase().includes('m')) minutes = parseInt(part) || 0;
                    else if (part.toLowerCase().includes('s')) seconds = parseInt(part) || 0;
                });
            }
            data.duration = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        } else if (durationStr.trim() === '') {
            data.duration = null; // Send null if empty string
        } else {
            // If parsing fails and it's not empty, keep original for server-side validation to catch
            // Or display a client-side error immediately
            displayFormErrors(formId, { duration: ['Invalid duration format. Use HH:MM:SS or like 1h 30m.'] });
            send_toast('Invalid duration format.', 'warning');
            return;
        }
    } else {
        data.duration = null; // Send null if field is not present or empty
    }

    const response = await httpRequestHelper(form.action, 'POST', data);

    if (response.ok) {
        send_toast('Workout added successfully!', 'success');
        const modal = form.closest('.siu-modal');
        if (modal) modal.style.display = 'none';
        form.reset();
        window.location.reload(); // Reload to see the new workout in the list
    } else {
        displayFormErrors(formId, response.data || { detail: response.statusText });
        send_toast(response.data?.detail || 'Error saving workout.', 'danger');
    }
}

// --- Add Set to Workout Exercise ---
// Triggered by data-function="click->addSet"
// Needs data-workout-exercise-id="{{ workout_exercise.id }}" on the button
async function addSet(event) {
    const button = event.target;
    const workoutExerciseId = button.dataset.workoutExerciseId;
    if (!workoutExerciseId) {
        console.error('Missing data-workout-exercise-id on add set button');
        return;
    }

    // Find inputs relative to the button/exercise container
    const container = button.closest('.workout-exercise-controls'); // Adjust selector if needed
    if (!container) {
         console.error('Cannot find container for inputs relative to button');
         return;
    }
    const weightInput = container.querySelector(`.weight-input`); // Use classes for inputs
    const repsInput = container.querySelector(`.reps-input`);
    const warmupInput = container.querySelector(`.warmup-input`);

    const weight = parseFloat(weightInput?.value);
    const reps = parseInt(repsInput?.value);
    const isWarmup = warmupInput?.checked || false;

    if (isNaN(weight) || isNaN(reps)) {
        send_toast('Please enter valid weight and reps', 'warning');
        return;
    }

    const url = `/api/workouts/exercises/${workoutExerciseId}/sets/`;
    const data = { weight, reps, is_warmup: isWarmup };

    const response = await httpRequestHelper(url, 'POST', data);

    if (response.ok) {
        send_toast('Set added', 'success');
        // TODO: Update UI dynamically instead of relying on reload?
        // Find table: document.getElementById(`sets-${workoutExerciseId}`)
        // Append row with response.data info
        // Clear inputs
        if(weightInput) weightInput.value = '';
        if(repsInput) repsInput.value = '';
        if(warmupInput) warmupInput.checked = false;
        // TEMP: Reload for simplicity
        location.reload();
    } else {
        displayFormErrors(container.id || 'add-set-form', response.data); // Need a way to target errors
        send_toast(response.data?.detail || 'Error adding set', 'danger');
    }
}

// --- Delete Set ---
// Triggered by data-function="click->deleteSet"
// Needs data-set-id="{{ set.id }}" and data-confirm="Are you sure?" on the button
async function deleteSet(event) {
    const button = event.target;
    const setId = button.dataset.setId;
    const confirmMsg = button.dataset.confirm;

    if (!setId) {
        console.error('Missing data-set-id on delete button');
        return;
    }

    if (confirmMsg && !confirm(confirmMsg)) {
        return;
    }

    const url = `/api/workouts/sets/${setId}/`;
    const response = await httpRequestHelper(url, 'DELETE');

    if (response.ok) {
        send_toast('Set deleted', 'success');
        button.closest('tr')?.remove(); // Remove the table row
    } else {
         send_toast(response.data?.detail || 'Error deleting set', 'danger');
    }
}

// --- Add Existing Exercise to Workout ---
// Triggered by data-function="click->addExerciseToWorkout"
// Needs data-workout-id="{{ workout.id }}" on the button
// Assumes select#exercise-select and select#exercise-type exist nearby
async function addExerciseToWorkout(event) {
    const button = event.target;
    const workoutId = button.dataset.workoutId;
    if (!workoutId) {
        console.error('Missing data-workout-id');
        return;
    }

    // Find controls - assuming they are in a shared parent/container
    const container = button.closest('.add-exercise-controls'); // Adjust selector
    if (!container) {
         console.error('Cannot find container for add exercise controls');
         return;
    }
    const exerciseSelect = container.querySelector('#exercise-select'); // Assuming IDs are stable
    const typeSelect = container.querySelector('#exercise-type');

    const exerciseId = exerciseSelect?.value;
    const exerciseType = typeSelect?.value;

    if (!exerciseId) {
        send_toast('Please select an exercise', 'warning');
        return;
    }

    const url = `/api/workouts/${workoutId}/add_exercise/`;
    const data = { exercise: exerciseId, exercise_type: exerciseType };

    const response = await httpRequestHelper(url, 'POST', data);

    if (response.ok) {
        send_toast('Exercise added to workout', 'success');
        window.location.reload(); // Reload to see the change
    } else {
        send_toast(response.data?.detail || 'Error adding exercise', 'danger');
    }
}

// ======================================
// EXERCISE LIST FILTERING & SEARCH
// ======================================

function debounce(func, delay) {
    let timeoutId;
    return function(...args) {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
}

// Make this function global for data-function
window.fetchAndUpdateExerciseList = async function() {
    const form = document.getElementById('exercise-filter-form');
    if (!form) return;

    const searchInput = document.getElementById('exercise-search');
    const typeFilter = document.getElementById('exercise-type-filter');
    const categoryFilter = document.getElementById('category-filter');
    const listContainer = document.getElementById('exercise-list-container');

    if (!listContainer) return;

    const params = new URLSearchParams();
    if (searchInput && searchInput.value) { // Added null check for searchInput
        params.append('search_query', searchInput.value);
    }
    if (typeFilter && typeFilter.value) { // Added null check for typeFilter
        params.append('exercise_type', typeFilter.value);
    }
    if (categoryFilter && categoryFilter.value) { // Added null check for categoryFilter
        params.append('category', categoryFilter.value);
    }

    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({ path: newUrl }, '', newUrl);

    try {
        const response = await fetch(`${form.action}?${params.toString()}`, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        if (!response.ok) {
            console.error('Error fetching exercise list:', response.statusText);
            listContainer.innerHTML = '<p class="text-danger">Error loading exercises. Please try again.</p>';
            return;
        }
        const html = await response.text();
        listContainer.innerHTML = html;
    } catch (error) {
        console.error('Fetch error:', error);
        listContainer.innerHTML = '<p class="text-danger">Error loading exercises. Please try again.</p>';
    }
}

// Make this debounced function global for data-function
window.debouncedFetchExercises = debounce(window.fetchAndUpdateExerciseList, 300);

// ======================================
//      ROUTINE FORM FUNCTIONS
// ======================================

function getNextRoutineExerciseIndex() {
    const exercisesContainer = document.getElementById('routine-exercises-container');
    if (!exercisesContainer) return 0;
    let maxIndex = -1;
    exercisesContainer.querySelectorAll('.exercise-routine-card').forEach(card => {
        const cardIndex = parseInt(card.dataset.index, 10);
        if (cardIndex > maxIndex) {
            maxIndex = cardIndex;
        }
    });
    return maxIndex + 1;
}

function updateRoutineExerciseOrderNumbers() {
    const exercisesContainer = document.getElementById('routine-exercises-container');
    if (!exercisesContainer) return;
    const cards = exercisesContainer.querySelectorAll('.exercise-routine-card');
    cards.forEach((card, idx) => {
        const orderSpan = card.querySelector('.exercise-order');
        const orderInput = card.querySelector('input[name^="order_"]');
        const newOrder = idx + 1;
        if (orderSpan) {
            orderSpan.textContent = newOrder;
        }
        // Only set the input value for newly added cards (those without an existing ID)
        // or if it still has the placeholder value.
        const routineExerciseIdInput = card.querySelector('input[name^="routine_exercise_id_"]');
        if (orderInput && (!routineExerciseIdInput || !routineExerciseIdInput.value || orderInput.value === '__DEFAULT_ORDER__')) {
            orderInput.value = newOrder;
        }
    });
}

function updateRoutineFormCount() {
    const exercisesContainer = document.getElementById('routine-exercises-container');
    if (!exercisesContainer) return;
    let formCountInput = document.querySelector('input[name="routine_exercise_form_count"]');
    if (!formCountInput) {
        formCountInput = document.createElement('input');
        formCountInput.type = 'hidden';
        formCountInput.name = 'routine_exercise_form_count';
        const routineForm = document.getElementById('routineForm');
        if (routineForm) routineForm.appendChild(formCountInput);
    }
    if(formCountInput) formCountInput.value = exercisesContainer.querySelectorAll('.exercise-routine-card').length;
}

// window.addRoutineExerciseCard = function(event) { // This function is being replaced by the modal workflow
//     const exercisesContainer = document.getElementById('routine-exercises-container');
//     const exerciseTemplateHTML = document.getElementById('routine-exercise-template')?.innerHTML;
//     if (!exercisesContainer || !exerciseTemplateHTML) {
//         console.error('Missing exercises container or template for routine exercises.');
//         return;
//     }
//
//     const newIndex = getNextRoutineExerciseIndex();
//     const defaultOrder = exercisesContainer.querySelectorAll('.exercise-routine-card').length + 1;
//
//     const newExerciseHtml = exerciseTemplateHTML.replace(/__INDEX__/g, newIndex)
//                                               .replace(/__DEFAULT_ORDER__/g, defaultOrder);
//     const tempDiv = document.createElement('div');
//     tempDiv.innerHTML = newExerciseHtml;
//
//     const newCard = tempDiv.firstElementChild;
//     if (newCard) {
//         exercisesContainer.appendChild(newCard);
//         // Explicitly set order for the new card's input and span
//         const orderInputForNewCard = newCard.querySelector(`input[name="order_${newIndex}"]`);
//         if(orderInputForNewCard) orderInputForNewCard.value = defaultOrder;
//         const orderSpanForNewCard = newCard.querySelector('.exercise-order');
//         if(orderSpanForNewCard) orderSpanForNewCard.textContent = defaultOrder;
//     }
//     updateRoutineFormCount();
// }

window.removeRoutineExerciseCard = function(event) {
    const button = event.target;
    const cardToRemove = button.closest('.exercise-routine-card');
    if (cardToRemove) {
        cardToRemove.remove();
        updateRoutineFormCount();
        updateRoutineExerciseOrderNumbers();
    }
}

// --- Routine Form Modal Functions ---
window.showAddExerciseToRoutineModal = function(event) {
    const modal = document.getElementById('add-exercise-to-routine-modal');
    if (modal) {
        // Reset the select input and clear any previous error messages
        const exerciseSelect = modal.querySelector('#modal-exercise-select');
        if (exerciseSelect) {
            exerciseSelect.value = ''; // Reset to the placeholder
            exerciseSelect.classList.remove('is-invalid');
        }
        modal.style.display = 'flex';
    }
}

let draggedItem = null;
let floatingClone = null;
let dragOffsetX = 0;
let dragOffsetY = 0;

function handleDragStart(event) {
    draggedItem = event.target; // The original card
    if (!draggedItem.classList.contains('exercise-routine-card')) return; // Ensure we are dragging the correct item

    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', draggedItem.dataset.index); // Still useful for context

    // Create a transparent 1x1 pixel image to hide the default OS ghost
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    event.dataTransfer.setDragImage(img, 0, 0);

    // Create a visual clone for dragging
    floatingClone = draggedItem.cloneNode(true);
    floatingClone.classList.add('dragging-clone'); // New class for styling the clone

    // Ensure the clone has the same dimensions as the original item
    const rect = draggedItem.getBoundingClientRect();
    floatingClone.style.width = `${rect.width}px`;
    floatingClone.style.height = `${rect.height}px`;
    // Apply all computed styles from the original to the clone to match appearance as closely as possible
    // This is more robust than just width/height but can be performance intensive if abused.
    // For now, let's stick to width/height, if more is needed we can iterate.
    /*
    const originalStyles = window.getComputedStyle(draggedItem);
    for (let i = 0; i < originalStyles.length; i++) {
        const key = originalStyles[i];
        floatingClone.style.setProperty(key, originalStyles.getPropertyValue(key), originalStyles.getPropertyPriority(key));
    }
    */

    document.body.appendChild(floatingClone);

    // Calculate mouse offset relative to the dragged item (using the new rect)
    dragOffsetX = event.clientX - rect.left;
    dragOffsetY = event.clientY - rect.top;

    // Position the clone initially under the mouse
    floatingClone.style.left = `${event.clientX - dragOffsetX}px`;
    floatingClone.style.top = `${event.clientY - dragOffsetY}px`;

    // Hide the original item (it will be moved on drop)
    setTimeout(() => { // Timeout to allow initial setup before hiding
        if(draggedItem) draggedItem.classList.add('drag-source-hidden');
    }, 0);

    document.addEventListener('dragover', handleDragMouseMove); // Use dragover on document for continuous position update
}

function handleDragMouseMove(event) {
    if (floatingClone) {
        // event.preventDefault(); // Important if this listener is on a droppable area, less so on document for just tracking mouse
        floatingClone.style.left = `${event.clientX - dragOffsetX}px`;
        floatingClone.style.top = `${event.clientY - dragOffsetY}px`;
    }
}

function handleDragEnd(event) {
    if (floatingClone) {
        document.body.removeChild(floatingClone);
        floatingClone = null;
    }
    if (draggedItem) {
        draggedItem.classList.remove('drag-source-hidden');
        draggedItem.style.opacity = ''; // Reset any direct opacity manipulations
    }
    draggedItem = null;
    document.removeEventListener('dragover', handleDragMouseMove);
}

// handleDragOver on the container needs to be adjusted
// For now, it will just allow drop and maybe show where draggedItem (original hidden one) would go
function handleDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    // Original reordering logic based on the hidden draggedItem might still work
    // if we consider its placeholder or conceptual position
    const container = event.currentTarget;
    if (!draggedItem) return; // If original item reference is lost

    const afterElement = getDragAfterElement(container, event.clientY, draggedItem);
    if (afterElement === undefined && container.lastChild !== draggedItem && !draggedItem.contains(container.lastChild)) {
        // append to end if no element to insert before, and it's not already there or a child
        // This needs to operate on a placeholder for draggedItem or the draggedItem itself if it's only hidden, not removed
    } else if (afterElement && afterElement !== draggedItem && !draggedItem.contains(afterElement)) {
        // container.insertBefore(draggedItem, afterElement);
    }
     // More complex logic will be needed here to show a placeholder for the hidden draggedItem
     // and reorder other items around this conceptual placeholder.
     // For now, let's focus on the floating clone visual.
}

function getDragAfterElement(container, y, currentDraggedItem) { // Added currentDraggedItem
    const draggableElements = [...container.querySelectorAll('.exercise-routine-card:not(.drag-source-hidden)')];

    return draggableElements.reduce((closest, child) => {
        if (child === currentDraggedItem) return closest; // Don't compare with the item being dragged
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function handleDrop(event) {
    event.preventDefault();
    if (draggedItem) {
        // Logic to place the original draggedItem into the correct spot
        // This will now use the position of the drop event, relative to other items
        const container = document.getElementById('routine-exercises-container');
        const afterElement = getDragAfterElement(container, event.clientY, draggedItem);

        if (afterElement) {
            container.insertBefore(draggedItem, afterElement);
        } else {
            container.appendChild(draggedItem); // Append to end if no element to insert before
        }
        draggedItem.classList.remove('drag-source-hidden'); // Make it visible
    }

    updateRoutineExerciseOrderNumbers();
    // draggedItem is reset in dragend
}

function setupDragAndDropListeners(cardElement) {
    cardElement.addEventListener('dragstart', handleDragStart);
    cardElement.addEventListener('dragend', handleDragEnd);
}

window.initializeRoutineForm = function() {
    const exercisesContainer = document.getElementById('routine-exercises-container');
    if (exercisesContainer) {
        // Add D&D listeners to container
        exercisesContainer.addEventListener('dragover', handleDragOver);
        exercisesContainer.addEventListener('drop', handleDrop);

        // Add D&D listeners to existing cards
        exercisesContainer.querySelectorAll('.exercise-routine-card').forEach(card => {
            setupDragAndDropListeners(card);
        });

        if (exercisesContainer.querySelectorAll('.exercise-routine-card').length > 0) {
            updateRoutineFormCount();
            updateRoutineExerciseOrderNumbers();
        }
    }
}

// Update appendExerciseCardToRoutine to also add D&D listeners to new cards
function appendExerciseCardToRoutine(exerciseId, exerciseName) {
    const exercisesContainer = document.getElementById('routine-exercises-container');
    const exerciseTemplateHTML = document.getElementById('routine-exercise-template')?.innerHTML;

    if (!exercisesContainer || !exerciseTemplateHTML) {
        console.error('Missing exercises container or template.');
        return;
    }

    const newIndex = getNextRoutineExerciseIndex();
    const defaultOrder = exercisesContainer.querySelectorAll('.exercise-routine-card').length + 1;

    let newExerciseHtml = exerciseTemplateHTML.replace(/__INDEX__/g, newIndex)
                                              .replace(/__DEFAULT_ORDER__/g, defaultOrder);

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = newExerciseHtml;
    const newCard = tempDiv.firstElementChild;

    if (newCard) {
        const exerciseSelectInCard = newCard.querySelector(`select[name="exercise_pk_${newIndex}"]`);
        if (exerciseSelectInCard) {
            exerciseSelectInCard.value = exerciseId;
        }
        exercisesContainer.appendChild(newCard);
        setupDragAndDropListeners(newCard); // Add D&D listeners to the newly added card

        const orderInputForNewCard = newCard.querySelector(`input[name="order_${newIndex}"]`);
        if(orderInputForNewCard) orderInputForNewCard.value = defaultOrder;
        const orderSpanForNewCard = newCard.querySelector('.exercise-order');
        if(orderSpanForNewCard) orderSpanForNewCard.textContent = defaultOrder;

        updateRoutineFormCount();
        // Order numbers for existing items are updated by updateRoutineExerciseOrderNumbers if needed,
        // called from handleDrop or if an item is removed.
    } else {
        console.error("Could not create new exercise card from template.");
    }
}

window.selectAndAddExerciseToRoutine = function(event) {
    const selectElement = event.target;
    const exerciseId = selectElement.value;

    if (!exerciseId) { // User selected the placeholder "Choose an exercise..."
        return;
    }

    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const exerciseName = selectedOption.dataset.name || selectedOption.text;

    appendExerciseCardToRoutine(exerciseId, exerciseName);

    // Close the modal
    const modal = document.getElementById('add-exercise-to-routine-modal');
    if (modal) {
        modal.style.display = 'none';
    }

    // It might be good practice to reset the select here too,
    // though showAddExerciseToRoutineModal will do it when modal is next opened.
    // selectElement.value = ''; // Optional: reset immediately
}

// ======================================
//          INITIALIZATION
// ======================================

document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired');

    // Initial scan for elements present on page load
    document.querySelectorAll('[data-function]').forEach(element => {
         console.log('Initial scan found element with data-function:', element);
         handle_attribute(element, element.getAttributeNode('data-function'));
    });

    // Explicitly initialize routine form if its container is present
    if (document.getElementById('routine-exercises-container')) {
        initializeRoutineForm();
    }

    // Start observing the body for dynamically added/changed elements
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['data-function'] // Only observe data-function
    });
});