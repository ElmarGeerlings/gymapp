console.log('gainz.js script started execution.'); // Log at the very top

// ======================================
//          CORE FRAMEWORK
// ======================================

// WebSocket Setup (from stolen_js.js example)
// const port = window.location.port ? `:${window.location.port}` : '';
// const wsProtocol = location.protocol === 'https:' ? 'wss' : 'ws';
// const wsUrl = `${wsProtocol}://${window.location.hostname}${port}/ws/gainz/`; // Adjusted path

// let ws = null;
// const requestMap = new Map();
// let reconnectAttempts = 0;
// const maxReconnectAttempts = 10;
// const reconnectInterval = 3000; // 3 seconds

// function connectWebSocket() { // REMOVED
    // ... WebSocket connection logic ...
// }

// Initialize WebSocket connection
// connectWebSocket(); // REMOVED


// Loading Indicator (can be kept if used by httpRequestHelper or other AJAX calls, or removed if only for WebSockets)
// let intervalId; // REMOVED if show/hideLoading are removed
// function showLoading() { // REMOVED or adapted for general AJAX
    // ... loading logic ...
// }

// function hideLoading() { // REMOVED or adapted for general AJAX
    // ... loading logic ...
// }

// sendWsRequest (from stolen_js.js example, adapted)
// function sendWsRequest(endpoint, element) { // REMOVED
    // ... WebSocket send logic ...
// }

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

        // Debugging log for the specific button
        if (element.id === 'add-exercise-btn' && eventName === 'click' && targetName === 'showAddExerciseToRoutineModal') {
            console.log('Attempting to bind click->showAddExerciseToRoutineModal to #add-exercise-btn');
        }

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
    // Use the specific error div ID for workouts modal, or fallback to generic
    const generalErrorDivId = formId === 'add-workout-form' ? 'form-errors-workout' : 'form-errors';
    const generalErrorDiv = form.querySelector(`#${generalErrorDivId}`);
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

// UI update function using httpRequestHelper
window.handle_and_morph = async function(event) { // Made async to use await with httpRequestHelper
    if (event.type === 'keydown' && event.key !== 'Enter') {
        return;
    }
    event.preventDefault();

    const element = event.currentTarget;
    let endpoint = element.getAttribute('data-routing');
    const targetSelector = element.getAttribute('data-target');

    if (!endpoint) {
        console.error('handle_and_morph: data-routing attribute is missing on element:', element);
        send_toast('Configuration error: Missing routing.', 'danger', 'Error');
        return;
    }

    // Construct URL with query parameters from data-* attributes
    const params = new URLSearchParams();
    for (const dataAttr in element.dataset) {
        // data-routing and data-target are for control, others are params
        // data-function is also for control
        if (dataAttr !== 'routing' && dataAttr !== 'target' && dataAttr !== 'function') {
            params.append(dataAttr, element.dataset[dataAttr]);
        }
    }
    if (params.toString()) {
        endpoint += (endpoint.includes('?') ? '&' : '?') + params.toString();
    }

    console.log(`handle_and_morph: HTTP GET to "${endpoint}" for target "${targetSelector || 'none'}"`);

    try {
        // showLoading(); // Optional: if you have a generic AJAX loading indicator
        const response = await httpRequestHelper(endpoint, 'GET');
        // hideLoading(); // Optional
        console.log('handle_and_morph received HTTP response:', response);

        if (!response.ok) {
            const errorDetail = response.data?.detail || response.data?.error || response.statusText || 'An error occurred.';
            console.error('Error from backend in handle_and_morph:', errorDetail, response);
            send_toast(errorDetail, 'danger', 'Server Error');
            // If the server provides HTML in the error response for the target, display it
            if (targetSelector && response.data?.html) {
                 const targetElement = document.querySelector(targetSelector);
                 if (targetElement) targetElement.innerHTML = response.data.html;
            }
            return;
        }

        if (targetSelector && response.data && response.data.html !== undefined) {
            const targetElement = document.querySelector(targetSelector);
            if (targetElement) {
                targetElement.innerHTML = response.data.html;
            } else {
                console.warn(`handle_and_morph: Target element "${targetSelector}" not found.`);
                send_toast(`UI update error: Target '${targetSelector}' not found.`, 'warning', 'Client Error');
            }
        } else if (targetSelector && (!response.data || response.data.html === undefined)) {
            console.warn(`handle_and_morph: No HTML content provided in response for target "${targetSelector}". Response:`, response);
        }

        // Handle toast messages from response.data if structured accordingly
        if (response.data && response.data.toast) {
            const toast = response.data.toast;
            send_toast(toast.body, toast.status || 'info', toast.title || '');
        }

    } catch (error) {
        // hideLoading(); // Optional: ensure loading is hidden on error
        // This catch handles errors from httpRequestHelper itself (e.g., network errors)
        console.error('Error in httpRequestHelper call for handle_and_morph:', error);
        const message = error.data?.detail || error.message || 'Error processing action.';
        send_toast(message, 'danger', 'Request Failed');
    }
};

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

// This function was modified to correctly handle new card structure and add a default set.
function appendExerciseCardToRoutine(exerciseId, exerciseName) {
    const template = document.getElementById('routine-exercise-template');
    if (!template) {
        console.error('#routine-exercise-template not found!');
        return null; // Return null or throw error
    }

    const container = document.getElementById('routine-exercises-container');
    if (!container) {
        console.error('#routine-exercises-container not found!');
        return null;
    }

    const nextIndex = getNextRoutineExerciseIndex(); // Ensure this gives a unique index
    const defaultOrder = nextIndex + 1; // Order is 1-based

    let content = template.innerHTML;
    content = content.replace(/__INDEX__/g, nextIndex)
                     .replace(/__ORDER__/g, defaultOrder)
                     .replace(/__EXERCISE_NAME__/g, exerciseName || 'Select Exercise');

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = content;
    const newCard = tempDiv.firstElementChild;

    if (!newCard) {
        console.error("Could not create new exercise card from template content.");
        return null;
    }
    newCard.dataset.index = nextIndex; // Set the data-index attribute

    // Set the selected exercise in the dropdown
    const exerciseSelect = newCard.querySelector('.exercise-select');
    if (exerciseSelect && exerciseId) {
        exerciseSelect.value = exerciseId;
        // Trigger update for name and default type display after setting value
        updateExerciseCardName({ target: exerciseSelect });
    } else if (exerciseSelect) {
        // If no exerciseId, ensure default type display is generic
        const specificTypeSelect = newCard.querySelector('select[name*="routine_specific_exercise_type"]');
        if (specificTypeSelect && specificTypeSelect.options.length > 0 && specificTypeSelect.options[0].value === '') {
            specificTypeSelect.options[0].textContent = 'Default (Select Exercise First)';
        }
    }

    container.appendChild(newCard);
    setupDragAndDropListeners(newCard); // Add D&D listeners
    updateRoutineExerciseOrderNumbers(); // Update order numbers for all cards

    // Automatically add one default set to the new exercise card
    window.addSetToExerciseCard(newCard); // Pass the new card element directly
    return newCard; // Return the created card element
}

// Restore window.selectAndAddExerciseToRoutine
window.selectAndAddExerciseToRoutine = function(event) {
    const selectElement = event.target;
    const exerciseId = selectElement.value;

    if (!exerciseId) { // User selected the placeholder "Choose an exercise..."
        return;
    }

    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const exerciseName = selectedOption.dataset.name || selectedOption.text;

    // Call the corrected appendExerciseCardToRoutine
    const newCard = appendExerciseCardToRoutine(exerciseId, exerciseName);

    if (newCard) {
        // Optional: Scroll to the new card or highlight it
    }

    // Close the modal
    const modal = document.getElementById('add-exercise-to-routine-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    // Reset the select for next time (already done in showAddExerciseToRoutineModal, but good practice)
    selectElement.value = '';
}

function initializeRoutineForm() {
    const routineExercisesContainer = document.getElementById('routine-exercises-container');
    if (routineExercisesContainer) {
        // Initial setup for existing cards from server
        routineExercisesContainer.querySelectorAll('.exercise-routine-card').forEach(card => {
            setupDragAndDropListeners(card);
            const exerciseSelect = card.querySelector('.exercise-select');
            if (exerciseSelect && exerciseSelect.value) {
                updateExerciseCardName({target: exerciseSelect});
            }
        });
        routineExercisesContainer.addEventListener('dragover', handleDragOver);
        routineExercisesContainer.addEventListener('drop', handleDrop);
    }

    updateRoutineExerciseOrderNumbers();

    // Load and apply checkbox states from Redis
    const rpeToggle = document.getElementById('toggle-rpe-visibility');
    const restToggle = document.getElementById('toggle-rest-time-visibility');
    const notesToggle = document.getElementById('toggle-notes-visibility');

    if(rpeToggle) rpeToggle.checked = localStorage.getItem('gainz.routineForm.showRPE') === 'true';
    if(restToggle) restToggle.checked = localStorage.getItem('gainz.routineForm.showRestTime') === 'true';
    if(notesToggle) notesToggle.checked = localStorage.getItem('gainz.routineForm.showNotes') === 'true';
    // localStorage logic removed, states are now set by Django template from Redis

    window.updateSetRowFieldVisibility(); // Initial call based on server-provided states
}

// Initialization on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired from gainz.js');

    // Explicitly scan for and handle data-function attributes on existing elements
    console.log('Scanning for initial data-function attributes...');
    document.querySelectorAll('[data-function]').forEach(element => {
        console.log('Initial scan processing element:', element); // Log the element itself
        const attrNode = element.getAttributeNode('data-function');
        if (attrNode) { // Ensure the attribute node exists
            handle_attribute(element, attrNode);
        } else {
            console.warn('Element found by querySelectorAll but getAttributeNode("data-function") is null for:', element);
        }
    });

    if (document.getElementById('routineForm')) {
        initializeRoutineForm();
    }

    // Start observing the body for dynamically added/changed elements
    console.log('Starting MutationObserver for data-function attributes...');
    observer.observe(document.body, {
        childList: true,
        subtree: true,
        attributes: true,
        attributeFilter: ['data-function']
    });
});

// Make updateSetRowFieldVisibility explicitly global if not already, for data-function
window.updateSetRowFieldVisibility = updateSetRowFieldVisibility;

// Helper function to update visibility of optional set fields based on checkboxes
async function updateSetRowFieldVisibility(event) { // Made async
    const rpeToggle = document.getElementById('toggle-rpe-visibility');
    const restToggle = document.getElementById('toggle-rest-time-visibility');
    const notesToggle = document.getElementById('toggle-notes-visibility');

    const showRPE = rpeToggle?.checked;
    const showRestTime = restToggle?.checked;
    const showNotes = notesToggle?.checked;

    // Save states to Redis via backend API call
    // const preferencesToSave = []; // Not needed, send one by one or identify caller

    if (event && event.target) { // Check if called by an event on a specific toggle
        const checkbox = event.target;
        const preferenceKeySuffix = checkbox.id.replace('toggle-', '').replace('-visibility', '');
        const preferenceKey = `routineForm.${preferenceKeySuffix}`;
        const preferenceValue = checkbox.checked;
        console.log(`[gainz.js] Attempting to save preference: Key='${preferenceKey}', Value=${preferenceValue}`);
        await httpRequestHelper('/ajax/update_user_preferences/', 'POST', {
            preference_key: preferenceKey,
            preference_value: preferenceValue
        }).then(response => {
            console.log('[gainz.js] Save preference response:', response);
        }).catch(error => {
            console.error('[gainz.js] Save preference error:', error);
        });
    }
    // Removed localStorage saving logic
    // if(rpeToggle) localStorage.setItem('gainz.routineForm.showRPE', showRPE);
    // if(restToggle) localStorage.setItem('gainz.routineForm.showRestTime', showRestTime);
    // if(notesToggle) localStorage.setItem('gainz.routineForm.showNotes', showNotes);

    document.querySelectorAll('.set-row').forEach(setRow => {
        const rpeField = setRow.querySelector('.rpe-field');
        const restTimeField = setRow.querySelector('.rest-time-field');
        const notesField = setRow.querySelector('.notes-field');

        if (rpeField) rpeField.style.display = showRPE ? 'block' : 'none';
        if (restTimeField) restTimeField.style.display = showRestTime ? 'block' : 'none';
        if (notesField) notesField.style.display = showNotes ? 'block' : 'none';
    });
}

// Helper function to update set numbers and input names within an exercise card
function updateSetNumbers(exerciseCardElement) {
    const exerciseIndex = exerciseCardElement.dataset.index;
    const setRows = exerciseCardElement.querySelectorAll('.sets-container .set-row');
    setRows.forEach((setRow, newSetIndex) => {
        setRow.dataset.setIndex = newSetIndex;

        const setNumberDisplay = setRow.querySelector('.set-number-display');
        if (setNumberDisplay) setNumberDisplay.textContent = `Set ${newSetIndex + 1}`;

        const setNumberInput = setRow.querySelector('.set-number-input');
        if (setNumberInput) setNumberInput.value = newSetIndex + 1;

        // Update name attributes for all inputs in the set row
        setRow.querySelectorAll('input[name*="planned_sets"], select[name*="planned_sets"], textarea[name*="planned_sets"]').forEach(input => {
            const oldName = input.getAttribute('name');
            const newName = oldName.replace(/planned_sets\[\d+\]/, `planned_sets[${newSetIndex}]`);
            // Also, ensure the exercise index part is correct if it was a placeholder
            // This is more for newly added cards from template than for re-ordering existing ones
            const routineExerciseIdInput = exerciseCardElement.querySelector('input[name^="routine_exercise_id_"]');
            if (routineExerciseIdInput && !routineExerciseIdInput.value) {
                newName = newName.replace(/routine_exercise\[\d+\]/, `routine_exercise[${exerciseIndex}]`);
            }
            input.setAttribute('name', newName);

            // Update IDs if they follow a similar pattern (important for labels)
            if (input.id) {
                const oldId = input.id;
                const newId = oldId.replace(/planned_sets_\d+_/g, `planned_sets_${newSetIndex}_`).replace(/__EXERCISE_INDEX__/g, exerciseIndex);
                input.setAttribute('id', newId);
                const label = document.querySelector(`label[for='${oldId}']`);
                if (label) label.setAttribute('for', newId);
            }
        });
    });
}

window.updateExerciseCardName = function(event) {
    const selectElement = event.target;
    const exerciseCard = selectElement.closest('.exercise-routine-card');
    if (!exerciseCard) return;

    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const exerciseName = selectedOption.dataset.name || 'Exercise';

    const nameDisplay = exerciseCard.querySelector('.exercise-name-display');
    if (nameDisplay) nameDisplay.textContent = exerciseName;

    // Update the default exercise type in the specific type dropdown
    const specificTypeSelect = exerciseCard.querySelector('select[name*="routine_specific_exercise_type"]');
    if (specificTypeSelect && specificTypeSelect.options.length > 0) {
        const defaultOption = specificTypeSelect.options[0];
        // Assumption: all_exercises_details (JS object) is available globally or passed appropriately
        // It should map exercise PK to its details including default type display
        // For now, we'll just clear it if we don't have the data readily.
        // This part needs the exercise_type_choices passed to the template AND the actual default type of the selected ex.
        const exercisePk = selectedOption.value;
        // Placeholder: In a real scenario, you'd fetch this from a data structure if not on the option itself.
        // For now, if ex.default_type_display was a data attribute on the option:
        const defaultTypeDisplay = selectedOption.dataset.defaultTypeDisplay || 'Type';
        if (defaultOption.value === '') { // Ensure it's the "Default" option
            defaultOption.textContent = `Default (${defaultTypeDisplay})`;
        }
    }
}

window.addSetToExerciseCard = function(eventOrCardElement) {
    let exerciseCard;
    if (eventOrCardElement instanceof HTMLElement) {
        exerciseCard = eventOrCardElement;
    } else { // It's an event
        exerciseCard = eventOrCardElement.target.closest('.exercise-routine-card');
    }

    if (!exerciseCard) return;

    const exerciseIndex = exerciseCard.dataset.index;
    const setsContainer = exerciseCard.querySelector('.sets-container');
    if (!setsContainer) return;

    const setTemplate = document.getElementById('set-row-template');
    if (!setTemplate) {
        console.error('#set-row-template not found!');
        return;
    }

    const nextSetIndex = setsContainer.querySelectorAll('.set-row').length;
    const newSetNumber = nextSetIndex + 1;

    const clone = setTemplate.content.cloneNode(true);
    const newSetRow = clone.querySelector('.set-row');
    newSetRow.dataset.setIndex = nextSetIndex;

    const setNumberDisplay = newSetRow.querySelector('.set-number-display');
    if (setNumberDisplay) setNumberDisplay.textContent = `Set ${newSetNumber}`;

    const setNumberInput = newSetRow.querySelector('.set-number-input');
    if (setNumberInput) setNumberInput.value = newSetNumber;

    // Update name attributes and IDs
    newSetRow.querySelectorAll('input, select, textarea').forEach(input => {
        let name = input.getAttribute('name');
        if (name) {
            name = name.replace(/__EXERCISE_INDEX__/g, exerciseIndex)
                       .replace(/__SET_INDEX__/g, nextSetIndex)
                       .replace(/__SET_NUMBER__/g, newSetNumber); // Though set number is mostly for display
            input.setAttribute('name', name);
        }
        let id = input.getAttribute('id');
        if (id) {
            id = id.replace(/__EXERCISE_INDEX__/g, exerciseIndex)
                   .replace(/__SET_INDEX__/g, nextSetIndex)
                   .replace(/__SET_NUMBER__/g, newSetNumber);
            input.setAttribute('id', id);
            const label = clone.querySelector(`label[for='${id.replace(nextSetIndex, '__SET_INDEX__').replace(exerciseIndex, '__EXERCISE_INDEX__')}']`);
            if (label) label.setAttribute('for', id);
        }
    });

    setsContainer.appendChild(newSetRow);
    updateSetRowFieldVisibility(); // Apply current visibility settings
    // Event listeners for new buttons will be handled by the global mutation observer for data-function
}

window.removeSetFromExerciseCard = function(event) {
    const setRow = event.target.closest('.set-row');
    if (!setRow) return;

    const exerciseCard = setRow.closest('.exercise-routine-card');
    setRow.remove();

    if (exerciseCard) {
        updateSetNumbers(exerciseCard);
    }
}

window.duplicateSetRow = function(event) {
    const sourceSetRow = event.target.closest('.set-row');
    if (!sourceSetRow) return;

    const exerciseCard = sourceSetRow.closest('.exercise-routine-card');
    if (!exerciseCard) return;

    const setsContainer = exerciseCard.querySelector('.sets-container');
    if (!setsContainer) return;

    const exerciseIndex = exerciseCard.dataset.index;
    const newSetIndex = setsContainer.querySelectorAll('.set-row').length; // Index for the new row
    const newSetNumber = newSetIndex + 1;

    const clone = sourceSetRow.cloneNode(true);
    clone.dataset.setIndex = newSetIndex;

    // Clear the ID field for the new set (so backend treats it as new)
    const idInput = clone.querySelector('input[name*="_id"]');
    if (idInput) idInput.value = '';

    const setNumberDisplay = clone.querySelector('.set-number-display');
    if (setNumberDisplay) setNumberDisplay.textContent = `Set ${newSetNumber}`;

    const setNumberInput = clone.querySelector('.set-number-input');
    if (setNumberInput) setNumberInput.value = newSetNumber;

    // Update name attributes and IDs for the cloned row
    clone.querySelectorAll('input, select, textarea').forEach(input => {
        let name = input.getAttribute('name');
        if (name) {
            name = name.replace(/planned_sets\[\d+\]/, `planned_sets[${newSetIndex}]`);
            // Ensure exercise index is correct (especially if source was also from template)
            name = name.replace(/routine_exercise\[(?:\|__EXERCISE_INDEX__\|)\]/g, `routine_exercise[${exerciseIndex}]`);
            input.setAttribute('name', name);
        }
        let id = input.getAttribute('id');
        if (id) {
            const oldSetIndexPattern = /planned_sets_\d+_/; // Matches planned_sets_0_, planned_sets_1_, etc.
            id = id.replace(oldSetIndexPattern, `planned_sets_${newSetIndex}_`)
                   .replace(/__EXERCISE_INDEX__/g, exerciseIndex) // if coming from a template placeholder
                   .replace(/routine_exercise_\d+_/, `routine_exercise_${exerciseIndex}_`); // if coming from an existing item
            input.setAttribute('id', id);
            const label = clone.querySelector(`label[for='${input.getAttribute('data-original-id-for-label') || id}']`); // A bit hacky, assumes original ID for label if complex IDs
            if (label) label.setAttribute('for', id);
        }
    });

    // Insert after the source row
    sourceSetRow.parentNode.insertBefore(clone, sourceSetRow.nextSibling);

    // Update numbers for all subsequent sets (including the one just added if it wasn't last)
    updateSetNumbers(exerciseCard);
    updateSetRowFieldVisibility(); // Apply visibility to the new row
}