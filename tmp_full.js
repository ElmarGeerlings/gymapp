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

let mutationObserverStarted = false;

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

const observer = new MutationObserver(process_mutations);

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

// Store the original program state for cancel functionality
let originalProgramState = null;

function saveProgramState() {
    const state = {
        schedulingType: document.getElementById('scheduling-weekly').checked ? 'weekly' : 'sequential',
        weeklyRoutines: {},
        sequentialRoutines: []
    };

    // Save weekly routines with order
    document.querySelectorAll('.day-column').forEach(dayColumn => {
        const dayValue = dayColumn.dataset.dayValue;
        state.weeklyRoutines[dayValue] = [];
        dayColumn.querySelectorAll('.routine-chip').forEach((chip, index) => {
            state.weeklyRoutines[dayValue].push({
                routine_id: chip.dataset.routineId,
                name: chip.dataset.routineName || chip.querySelector('span').textContent,
                order: index + 1
            });
        });
    });

    // Save sequential routines
    document.querySelectorAll('.program-routine-row').forEach(row => {
        const routineIdInput = row.querySelector('input[name*="_routine_id"]');
        const routineNameInput = row.querySelector('input[type="text"][readonly]');
        const orderInput = row.querySelector('input[name*="_order"]');

        if (routineIdInput && routineNameInput) {
            state.sequentialRoutines.push({
                routine_id: routineIdInput.value,
                name: routineNameInput.value,
                order: orderInput ? orderInput.value : state.sequentialRoutines.length + 1
            });
        }
    });

    return state;
}

function restoreProgramState(state) {
    if (!state) return;

    // Restore scheduling type
    if (state.schedulingType === 'weekly') {
        document.getElementById('scheduling-weekly').checked = true;
    } else {
        document.getElementById('scheduling-sequential').checked = true;
    }

    // Clear current routines
    document.querySelectorAll('.routines-for-day-container').forEach(container => {
        container.innerHTML = '';
    });
    document.getElementById('program-routines-container').innerHTML = '';

    // Restore weekly routines
    Object.keys(state.weeklyRoutines).forEach(dayValue => {
        const dayColumn = document.querySelector(`.day-column[data-day-value="${dayValue}"]`);
        if (dayColumn) {
            const container = dayColumn.querySelector('.routines-for-day-container');
            state.weeklyRoutines[dayValue].forEach(routine => {
                const chip = document.createElement('div');
                chip.className = 'routine-chip';
                chip.draggable = true;
                chip.dataset.routineId = routine.routine_id || routine.id;
                chip.dataset.routineName = routine.name;
                chip.innerHTML = `
                    <span class="routine-chip-label">${routine.name}</span>
                    <div class="d-flex align-items-center">
                        <button type="button" class="btn-close btn-close-white btn-sm" data-ignore-double-activate="true" aria-label="Remove"></button>
                    </div>
                    <input type="hidden" name="weekly_day_${dayValue}_routines" value="${routine.routine_id || routine.id}">
                `;
                container.appendChild(chip);
                setupProgramRoutineDragListeners(chip);
            });
        }
    });

    // Restore sequential routines
    const programRoutinesContainer = document.getElementById('program-routines-container');
    const template = document.getElementById('program-routine-template');

    state.sequentialRoutines.forEach((routine, index) => {
        if (template) {
            let newRowHTML = template.innerHTML;
            newRowHTML = newRowHTML.replace(/__INDEX__/g, index)
                                   .replace(/__ROUTINE_ID__/g, routine.routine_id || routine.id)
                                   .replace(/__ROUTINE_NAME__/g, routine.name)
                                   .replace(/__ORDER__/g, routine.order);

            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = newRowHTML;
            const newRow = tempDiv.firstElementChild;

            programRoutinesContainer.appendChild(newRow);
            setupSequentialRoutineActivation(newRow);
        }
    });

    // Update UI visibility
    const weeklyContainer = document.getElementById('weekly-schedule-container');
    const sequentialContainer = document.getElementById('sequential-schedule-container');
    const sequentialAdder = document.getElementById('sequential-routine-adder');

    if (state.schedulingType === 'weekly') {
        weeklyContainer.style.display = 'block';
        sequentialContainer.style.display = 'none';
        sequentialAdder.style.display = 'none';
        initializeProgramRoutinesDragDrop();
    } else {
        weeklyContainer.style.display = 'none';
        sequentialContainer.style.display = 'block';
        sequentialAdder.style.display = 'block';
    }
}

async function restoreProgramStateViaAPI(programId, originalState) {
    try {
        const response = await fetch(`/ajax/program/${programId}/restore-state/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            },
            body: JSON.stringify({
                original_state: originalState
            })
        });

        if (!response.ok) {
            throw new Error('Failed to restore program state');
        }

        const data = await response.json();
        if (data.success) {
            console.log('Program state restored successfully');
            return true;
        } else {
            console.error('Error restoring program state:', data.error);
            return false;
        }
    } catch (error) {
        console.error('Error restoring program state:', error);
        return false;
    }
}

async function toggleScheduleType() {
    const weeklyContainer = document.getElementById('weekly-schedule-container');
    const sequentialContainer = document.getElementById('sequential-schedule-container');
    const sequentialAdder = document.getElementById('sequential-routine-adder');
    const weeklyRadio = document.getElementById('scheduling-weekly');
    const programRoutinesContainer = document.getElementById('program-routines-container');

    if (!weeklyContainer || !sequentialContainer || !sequentialAdder || !weeklyRadio) return;

    // Get program ID first
    const programForm = document.querySelector('form[action*="/programs/"]');
    let programId = null;
    if (programForm) {
        const actionUrl = programForm.getAttribute('action');
        const match = actionUrl.match(/\/programs\/(\d+)\//);
        if (match) {
            programId = match[1];
        }
    }

    // Prepare routine data to send to backend
    let routineData = null;
    const schedulingType = weeklyRadio.checked ? 'weekly' : 'sequential';

    if (weeklyRadio.checked) {
        // Switching TO weekly - collect from sequential view first
        const sequentialRoutines = [];
        programRoutinesContainer?.querySelectorAll('.program-routine-row').forEach((row) => {
            const routineIdInput = row.querySelector('input[name*="_routine_id"]');
            const routineNameInput = row.querySelector('input[type="text"][readonly]');

            if (routineIdInput && routineNameInput && routineIdInput.value) {
                sequentialRoutines.push({
                    routine_id: routineIdInput.value,
                    name: routineNameInput.value
                });
            }
        });

        // Distribute sequential routines to weekly days
        const days = [0, 1, 2, 3, 4, 5, 6];
        routineData = {};
        sequentialRoutines.forEach((routine, index) => {
            const assignedDay = days[index % days.length];
            if (!routineData[assignedDay]) {
                routineData[assignedDay] = [];
            }
            routineData[assignedDay].push(routine);
        });

        // Save to database first if we have a program ID
        if (programId) {
            try {
                const response = await fetch(`/ajax/program/${programId}/update-scheduling/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        scheduling_type: 'weekly',
                        routines: routineData
                    })
                });

                const data = await response.json();
                if (!data.success) {
                    console.error('Error updating scheduling type:', data.error);
                    return;
                }
            } catch (error) {
                console.error('Error updating scheduling type:', error);
                return;
            }
        }

        // Now update the DOM
        // Clear sequential container
        programRoutinesContainer.innerHTML = '';

        // Clear weekly containers first to avoid duplicates
        weeklyContainer.querySelectorAll('.routines-for-day-container').forEach(container => {
            container.innerHTML = '';
        });

        // Add to weekly view
        Object.entries(routineData).forEach(([day, routines]) => {
            const dayColumn = weeklyContainer.querySelector(`.day-column[data-day-value="${day}"]`);
            if (dayColumn) {
                const routinesContainer = dayColumn.querySelector('.routines-for-day-container');

                routines.forEach(routine => {
                    const chip = document.createElement('div');
                    chip.className = 'routine-chip';
                    chip.draggable = true;
                    chip.dataset.routineId = routine.routine_id;
                    chip.dataset.routineName = routine.name;
                    chip.innerHTML = `
                        <span class="routine-chip-label">${routine.name}</span>
                        <div class="d-flex align-items-center">
                            <button type="button" class="btn-close btn-close-white btn-sm" data-ignore-double-activate="true" aria-label="Remove"></button>
                        </div>
                        <input type="hidden" name="weekly_day_${day}_routines" value="${routine.routine_id}">
                    `;

                    routinesContainer.appendChild(chip);
                    setupProgramRoutineDragListeners(chip);
                });
            }
        });

        weeklyContainer.style.display = 'block';
        sequentialContainer.style.display = 'none';
        sequentialAdder.style.display = 'none';
        initializeProgramRoutinesDragDrop();

    } else {
        // Switching TO sequential - collect from weekly view first
        routineData = [];

        for (let day = 0; day < 7; day++) {
            const dayColumn = weeklyContainer.querySelector(`.day-column[data-day-value="${day}"]`);
            if (dayColumn) {
                dayColumn.querySelectorAll('.routine-chip').forEach(chip => {
                    const routineId = chip.dataset.routineId;
                    const routineName = chip.dataset.routineName || chip.querySelector('span').textContent;
                    if (routineId) {
                        routineData.push({
                            routine_id: routineId,
                            name: routineName
                        });
                    }
                });
            }
        }

        // Save to database first if we have a program ID
        if (programId) {
            try {
                const response = await fetch(`/ajax/program/${programId}/update-scheduling/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        scheduling_type: 'sequential',
                        routines: routineData
                    })
                });

                const data = await response.json();
                if (!data.success) {
                    console.error('Error updating scheduling type:', data.error);
                    return;
                }
            } catch (error) {
                console.error('Error updating scheduling type:', error);
                return;
            }
        }

        // Now update the DOM
        // Clear weekly view
        weeklyContainer.querySelectorAll('.routines-for-day-container').forEach(container => {
            container.innerHTML = '';
        });

        // Clear sequential first
        programRoutinesContainer.innerHTML = '';

        // Add to sequential view
        routineData.forEach((routine, index) => {
            const template = document.getElementById('program-routine-template');
            if (template) {
                let newRowHTML = template.innerHTML;
                newRowHTML = newRowHTML.replace(/__INDEX__/g, index)
                                       .replace(/__ROUTINE_ID__/g, routine.routine_id)
                                       .replace(/__ROUTINE_NAME__/g, routine.name)
                                       .replace(/__ORDER__/g, index + 1);

                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = newRowHTML;
                const newRow = tempDiv.firstElementChild;

                programRoutinesContainer.appendChild(newRow);
            }
        });

        weeklyContainer.style.display = 'none';
        sequentialContainer.style.display = 'block';
        sequentialAdder.style.display = 'block';
    }
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

        // Reset the form for add exercise modal
        if (modalname === 'add-exercise-modal') {
            // Reset title
            const modalTitle = document.getElementById('exercise-modal-title');
            if (modalTitle) modalTitle.textContent = 'Add New Exercise';

            // Clear exercise ID
            const exerciseIdField = document.getElementById('exercise-id');
            if (exerciseIdField) exerciseIdField.value = '';

            // Reset form
            if (form) form.reset();

            // Hide delete button
            const deleteBtn = document.getElementById('delete-exercise-btn');
            if (deleteBtn) deleteBtn.style.display = 'none';

            // Reset exercise type to default
            const exerciseTypeField = document.getElementById('id_exercise_type_modal');
            if (exerciseTypeField) exerciseTypeField.value = 'accessory';
        }

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

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function getCsrfToken() {
    let token = document.querySelector('meta[name="csrf-token"]');
    if (token) return token.content;
    token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (token) return token.value;
    // Fallback to cookie
    token = getCookie('csrftoken');
    if (token) return token;
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

// --- Add/Edit Exercise Modal Submission ---
// This function will be triggered by data-function="click->saveExercise"
async function saveExercise(event) {
    const form = event.target.closest('form');
    if (!form) return;
    const formId = form.id;
    clearFormErrors(formId);

    const exerciseId = document.getElementById('exercise-id').value;
    const isEdit = exerciseId !== '';

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

    // Determine URL and method based on whether we're editing or creating
    const url = isEdit ? `/api/exercises/${exerciseId}/` : form.action;
    const method = isEdit ? 'PUT' : 'POST';

    // Use the helper for the actual request
    const response = await httpRequestHelper(url, method, data);

    if (response.ok) {
        const message = isEdit ? 'Exercise updated successfully!' : 'Exercise added successfully!';
        send_toast(message, 'success');
        const modal = form.closest('.siu-modal');
        if (modal) modal.style.display = 'none';
        form.reset();
        document.getElementById('exercise-id').value = '';
        // Instead of full reload, maybe update list dynamically later?
        // For now, reload is simplest
        window.location.reload();
    } else {
        displayFormErrors(formId, response.data || { detail: response.statusText });
        send_toast(response.data?.detail || 'Error saving exercise.', 'danger');
    }
}

// --- Edit Exercise ---
// This function opens the modal with pre-filled data for editing
function editExercise(event) {
    const exerciseCard = event.currentTarget;

    // Get the exercise data from data attributes
    const exerciseId = exerciseCard.dataset.exerciseId;
    const exerciseName = exerciseCard.dataset.exerciseName;
    const exerciseDescription = exerciseCard.dataset.exerciseDescription || '';
    const exerciseType = exerciseCard.dataset.exerciseType;
    const exerciseCategories = exerciseCard.dataset.exerciseCategories ?
        exerciseCard.dataset.exerciseCategories.split(',') : [];

    // Update modal title
    document.getElementById('exercise-modal-title').textContent = 'Edit Exercise';

    // Fill the form fields
    document.getElementById('exercise-id').value = exerciseId;
    document.getElementById('id_name_modal').value = exerciseName;
    document.getElementById('id_description_modal').value = exerciseDescription;
    document.getElementById('id_exercise_type_modal').value = exerciseType;

    // Set selected categories
    const categorySelect = document.getElementById('id_categories_modal');
    Array.from(categorySelect.options).forEach(option => {
        option.selected = exerciseCategories.includes(option.value);
    });

    // Show delete button for editing
    document.getElementById('delete-exercise-btn').style.display = 'inline-block';

    // Open the modal
    document.getElementById('add-exercise-modal').style.display = 'block';

    // Focus on the name field
    document.getElementById('id_name_modal').focus();
}

// --- Delete Exercise ---
// This function deletes a custom exercise
async function deleteExercise(event) {
    const exerciseId = document.getElementById('exercise-id').value;

    if (!exerciseId) {
        send_toast('No exercise selected for deletion.', 'danger');
        return;
    }

    if (!confirm('Are you sure you want to delete this exercise? This cannot be undone.')) {
        return;
    }

    const response = await httpRequestHelper(`/api/exercises/${exerciseId}/`, 'DELETE');

    if (response.ok) {
        send_toast('Exercise deleted successfully!', 'success');
        const modal = document.getElementById('add-exercise-modal');
        if (modal) modal.style.display = 'none';
        document.getElementById('add-exercise-form').reset();
        document.getElementById('exercise-id').value = '';
        window.location.reload();
    } else {
        send_toast(response.data?.detail || 'Error deleting exercise.', 'danger');
    }
}


// --- Update Set ---
// Triggered by data-function="blur->updateSet" or data-function="change->updateSet"
// Needs data-set-id, data-field on the input/select element
async function updateSet(eventOrElement, overrideValue) {
    const element = eventOrElement && eventOrElement.target ? eventOrElement.target : eventOrElement;
    if (!element) {
        return false;
    }

    const setId = element.dataset.setId;
    const field = element.dataset.field;

    if (!setId || !field) {
        console.error('Missing data-set-id or data-field on element');
        return false;
    }

    let value;
    if (overrideValue !== undefined) {
        value = overrideValue;
    } else if (field === 'is_warmup') {
        value = element.checked;
    } else {
        value = element.value;
    }

    const url = '/api/workouts/sets/' + setId + '/';
    const data = { [field]: value };

    const response = await httpRequestHelper(url, 'PATCH', data);

    if (response.ok) {
        if (field === 'reps' || field === 'weight') {
            const row = element.closest('.set-row');
            if (row) {
                row.dataset[field] = value;
            }
        }
        return true;
    }

    send_toast(response.data?.detail || 'Error updating set', 'danger');
    return false;
}

function normalizeWorkoutSetValue(value, field) {
    if (value === null || value === undefined) {
        return '';
    }
    const trimmed = String(value).trim();
    if (!trimmed) {
        return '';
    }
    if (field === 'weight') {
        const numeric = Number(trimmed);
        return Number.isFinite(numeric) ? numeric : trimmed;
    }
    return trimmed;
}

function captureWorkoutSetOriginalValue(event) {
    const element = event?.target;
    if (!element) {
        return;
    }
    const field = element.dataset.field;
    if (field === 'is_warmup') {
        element.dataset.originalValue = element.checked ? 'true' : 'false';
    } else {
        element.dataset.originalValue = element.value ?? '';
    }
}

async function handleWorkoutSetChange(event) {
    const element = event?.target;
    if (!element) {
        return;
    }

    const field = element.dataset.field;
    const originalValueRaw = element.dataset.originalValue ?? (field === 'is_warmup' ? (element.checked ? 'true' : 'false') : element.value ?? '');
    const normalizedOriginal = normalizeWorkoutSetValue(originalValueRaw, field);

    const success = await updateSet(element);
    if (!success) {
        return;
    }

    const newValueRaw = field === 'is_warmup' ? (element.checked ? 'true' : 'false') : element.value ?? '';
    element.dataset.originalValue = newValueRaw;

    if ((field !== 'reps' && field !== 'weight') || normalizeWorkoutSetValue(newValueRaw, field) === normalizedOriginal) {
        return;
    }

    const setsContainer = element.closest('.sets-container');
    if (!setsContainer) {
        return;
    }

    const inputs = setsContainer.querySelectorAll('[data-field="' + field + '"]');
    for (const other of inputs) {
        if (other === element) {
            continue;
        }
        const otherOriginalValue = other.value ?? '';
        if (normalizeWorkoutSetValue(otherOriginalValue, field) !== normalizedOriginal) {
            continue;
        }

        other.value = element.value;
        const updated = await updateSet(other, element.value);
        if (updated) {
            other.dataset.originalValue = newValueRaw;
        } else {
            other.value = otherOriginalValue;
        }
    }
}

// --- Add Set to Exercise ---
// Triggered by data-function="click->addSet"
// Copies values from the last set or uses smart defaults
async function addSet(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const exerciseId = button.dataset.exerciseId;

    if (!exerciseId) {
        console.error('Missing data-exercise-id on add set button');
        return;
    }

    // Find the parent card body and sets container
    const cardBody = button.closest('.card-body');
    const setsContainer = cardBody.querySelector('.sets-container');
    const tbody = setsContainer.querySelector('.sets-tbody');

    // Get default values from last set and calculate set number
    let reps = 0;
    let weight = 0;
    let isWarmup = false;
    let setNumber = 1;

    if (tbody) {
        // Count existing sets to determine next set number
        const existingRows = tbody.querySelectorAll('.set-row');
        setNumber = existingRows.length + 1;

        // Get the last set row
        const lastRow = tbody.querySelector('.set-row:last-child');
        if (lastRow) {
            // Copy values from last set
            reps = parseInt(lastRow.dataset.reps) || parseInt(lastRow.querySelector('.set-reps-input')?.value) || 0;
            weight = parseFloat(lastRow.dataset.weight) || parseFloat(lastRow.querySelector('.set-weight-input')?.value) || 0;
            // Last set is usually not a warmup
            isWarmup = false;
        }
    }

    // If still no values, try to get from previous workout with same exercise
    // This would require an API call to get historical data - for now use defaults
    if (reps === 0) {
        reps = 10; // Default reps
        weight = 0; // Default weight
    }

    // Ensure reps is at least 1 (PositiveIntegerField in Django)
    if (reps < 1) {
        reps = 1;
    }

    const url = `/api/workouts/exercises/${exerciseId}/sets/`;
    const data = {
        set_number: setNumber,
        reps: Math.max(1, reps), // Ensure at least 1
        weight: weight.toFixed(2), // Format as decimal string
        is_warmup: isWarmup
    };

    console.log('Adding set with data:', data, 'to URL:', url);
    const response = await httpRequestHelper(url, 'POST', data);
    console.log('Add set response:', response);

    if (response.ok) {
        send_toast('Set added', 'success');

        // Auto-start timer based on user preferences
        if (window.handleTimerAutoStart) {
            await window.handleTimerAutoStart(button);
        }

        // No inputs to clear since we're using a simple + button

        // Re-find tbody since we may have created the table structure
        let tbody = setsContainer.querySelector('.sets-tbody');

        // If no table exists yet (first set), create the table structure
        if (!tbody) {
            const noSetsMessage = setsContainer.querySelector('.no-sets-message');
            if (noSetsMessage) {
                noSetsMessage.remove();
            }

            const tableHtml = `
                <div class="table-responsive">
                    <table class="table table-sm table-striped">
                        <thead>
                            <tr>
                                <th class="set-header-reps">Reps</th>
                                <th class="set-header-weight">Weight</th>
                                <th class="set-header-warmup">Warmup</th>
                                <th class="set-header-done">Done</th>
                                <th class="set-header-actions"></th>
                            </tr>
                        </thead>
                        <tbody class="sets-tbody"></tbody>
                    </table>
                </div>
            `;

            // Insert the table before the add button (which is in a mt-2 div)
            const addButton = setsContainer.querySelector('button[data-function*="addSet"]');
            if (addButton && addButton.parentElement) {
                addButton.parentElement.insertAdjacentHTML('beforebegin', tableHtml);
            } else {
                // Fallback: add at the end of the container
                setsContainer.insertAdjacentHTML('beforeend', tableHtml);
            }
            tbody = setsContainer.querySelector('.sets-tbody');
        }

        // Add the new row
        const setData = response.data;
        const formattedWeight =
            setData.weight !== null && setData.weight !== undefined && setData.weight !== ''
                ? parseFloat(setData.weight).toFixed(1)
                : '';
        const newRow = `
            <tr class="set-row${setData.is_completed ? ' set-completed' : ''}" data-set-id="${setData.id}" data-reps="${setData.reps}" data-weight="${formattedWeight}" data-is-completed="${setData.is_completed ? 'true' : 'false'}" data-exercise-id="${exerciseId}">
                <td class="set-reps">
                    <input type="number" class="form-control form-control-sm set-reps-input"
                           value="${setData.reps}" min="0" step="1"
                           data-function="blur->updateSet"
                           data-set-id="${setData.id}"
                           data-field="reps">
                </td>
                <td class="set-weight">
                    <input type="number" class="form-control form-control-sm set-weight-input"
                           value="${formattedWeight}" min="0" step="0.5"
                           data-function="blur->updateSet"
                           data-set-id="${setData.id}"
                           data-field="weight">
                </td>
                <td class="set-warmup text-center">
                    <input type="checkbox" class="form-check-input"
                           ${setData.is_warmup ? 'checked' : ''}
                           data-function="change->updateSet"
                           data-set-id="${setData.id}"
                           data-field="is_warmup">
                </td>
                <td class="set-done text-center">
                    <button type="button" class="btn btn-sm btn-outline-success mark-set-btn"
                            data-function="click->toggleSetCompletion"
                            data-set-id="${setData.id}"
                            data-exercise-id="${exerciseId}"
                            data-completed="${setData.is_completed ? 'true' : 'false'}"
                            title="Toggle completion">
                        <i class="fas fa-check"></i>
                    </button>
                </td>
                <td class="set-actions text-center">
                    <a href="#" class="text-danger"
                       data-function="click->deleteSet"
                       data-set-id="${setData.id}"
                       title="Delete set">
                        <i class="fas fa-times"></i>
                    </a>
                </td>
            </tr>
        `;
        tbody.insertAdjacentHTML('beforeend', newRow);

        const insertedRow = tbody.querySelector(`.set-row[data-set-id="${setData.id}"]`);
        if (insertedRow) {
            const index = Array.from(tbody.querySelectorAll('.set-row')).indexOf(insertedRow);
            insertedRow.dataset.setIndex = index;
        }

        if (window.mobileSetController && typeof window.mobileSetController.focusSet === 'function') {
            window.mobileSetController.focusSet(exerciseId, String(setData.id));
        }
    } else {
        console.error('Error adding set:', response);
        const errorMsg = response.data?.detail || response.data?.error || JSON.stringify(response.data) || 'Error adding set';
        send_toast(errorMsg, 'danger');
    }
}

// --- Delete Set ---
// Triggered by data-function="click->deleteSet"
// Needs data-set-id on the delete link/button
async function deleteSet(event) {
    event.preventDefault();
    const element = event.currentTarget;
    const setId = element.dataset.setId;

    if (!setId) {
        console.error('Missing data-set-id on delete element');
        return;
    }

    const url = `/api/workouts/sets/${setId}/`;
    const response = await httpRequestHelper(url, 'DELETE');

    if (response.ok) {
        send_toast('Set deleted', 'success');
        const row = element.closest('tr');
        const tbody = row.closest('tbody');
        const exerciseId = row?.dataset?.exerciseId;
        row.remove();

        // No need to update set numbers since we removed that column

        // Check if any rows are left
        const remainingRows = tbody.querySelectorAll('.set-row');
        if (remainingRows.length === 0) {
            const table = tbody.closest('.table-responsive');
            const setsContainer = table.closest('.sets-container');
            table.remove();
            const addButton = setsContainer.querySelector('.mt-2');
            if (addButton) {
                addButton.insertAdjacentHTML('beforebegin', '<p class="text-muted no-sets-message">No sets recorded for this exercise.</p>');
            }
        }

        if (exerciseId && window.mobileSetController && typeof window.mobileSetController.advanceSetForExercise === 'function') {
            window.mobileSetController.advanceSetForExercise(exerciseId);
        }
    } else {
         send_toast(response.data?.detail || 'Error deleting set', 'danger');
    }
}

// --- Toggle Set Completion ---
// Triggered by data-function="click->toggleSetCompletion"
// Toggles is_completed flag and updates UI state
async function toggleSetCompletion(event) {
    event.preventDefault();
    const button = event.currentTarget;
    const setId = button.dataset.setId;
    const exerciseId = button.dataset.exerciseId;

    if (!setId) {
        console.error('Missing data-set-id on completion toggle button');
        return;
    }

    const isCurrentlyCompleted = button.dataset.completed === 'true';
    const url = `/api/workouts/sets/${setId}/`;
    const response = await httpRequestHelper(url, 'PATCH', { is_completed: !isCurrentlyCompleted });

    if (!response.ok) {
        send_toast(response.data?.detail || 'Error updating set', 'danger');
        return;
    }

    const row = button.closest('.set-row');
    if (row) {
        row.dataset.isCompleted = (!isCurrentlyCompleted).toString();
        row.classList.toggle('set-completed', !isCurrentlyCompleted);
    }

    button.dataset.completed = (!isCurrentlyCompleted).toString();
    if (!isCurrentlyCompleted) {
        button.classList.remove('btn-outline-success');
        button.classList.add('btn-success', 'text-white');
        send_toast('Set marked complete', 'success');
    } else {
        button.classList.remove('btn-success', 'text-white');
        button.classList.add('btn-outline-success');
        send_toast('Set marked incomplete', 'info');
    }

    if (window.mobileSetController && typeof window.mobileSetController.handleSetCompletionChange === 'function') {
        window.mobileSetController.handleSetCompletionChange({
            exerciseId: exerciseId,
            setId: setId,
            isCompleted: !isCurrentlyCompleted
        });
    }
}

// --- Update Exercise Feedback ---
// Triggered by data-function="click->updateExerciseFeedback"
// Needs data-exercise-id and data-feedback on the button
async function updateExerciseFeedback(event) {
    const button = event.currentTarget;
    const exerciseId = button.dataset.exerciseId;
    const feedback = button.dataset.feedback;

    if (!exerciseId || !feedback) {
        console.error('Missing data-exercise-id or data-feedback on button');
        return;
    }

    // Use PATCH to update just the feedback field
    const url = `/api/workouts/exercises/${exerciseId}/`;
    const data = { performance_feedback: feedback };

    const response = await httpRequestHelper(url, 'PATCH', data);

    if (response.ok) {
        // Update button states (robust to both desktop and mobile markup)
        // Scope to the current card if possible
        const scope = button.closest('.exercise-card') || button.closest('.workout-exercise-card') || document;
        const selector = `[data-function*="updateExerciseFeedback"][data-exercise-id="${exerciseId}"]`;
        const allButtons = scope.querySelectorAll(selector);

        allButtons.forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');

        send_toast(`Feedback saved: ${feedback}`, 'success');
    } else {
        console.error('Error updating feedback:', response);
        send_toast(response.data?.detail || 'Error updating feedback', 'danger');
    }
}

// --- Remove Exercise from Workout ---
// Triggered by data-function="click->removeExercise"
// Needs data-exercise-id on the button
async function removeExercise(event) {
    const button = event.currentTarget;
    const exerciseId = button.dataset.exerciseId;

    if (!exerciseId) {
        console.error('Missing data-exercise-id on remove button');
        return;
    }

    if (!confirm('Are you sure you want to remove this exercise and all its sets?')) {
        return;
    }

    const url = `/api/workouts/exercises/${exerciseId}/`;
    const response = await httpRequestHelper(url, 'DELETE');

    if (response.ok) {
        send_toast('Exercise removed', 'success');

        // Stop and clear any timer state for this exercise
        try {
            if (window.timerManager) {
                window.timerManager.stopTimer(exerciseId);
            }
        } catch (e) { /* noop */ }

        // Prefer removing the full mobile wrapper if present
        let wrapper = button.closest('.exercise-card');
        let preferredIndex = null;
        if (wrapper) {
            // Remember index before removal
            preferredIndex = parseInt(wrapper.dataset.exerciseIndex || '0', 10);
            wrapper.remove();
        } else {
            // Desktop or fallback: remove the inner card
            const innerCard = button.closest('.workout-exercise-card');
            if (innerCard) innerCard.remove();
        }

        // If on mobile view, refresh navigation UI (dots, counter, prev/next)
        if (document.getElementById('exercise-card-container')) {
            if (typeof window.refreshMobileWorkoutUI === 'function') {
                window.refreshMobileWorkoutUI(preferredIndex);
            } else {
                // Minimal fallback: update count text if present
                const container = document.getElementById('exercise-card-container');
                const cards = container ? container.querySelectorAll('.exercise-card') : [];
                const currentNumSpan = document.getElementById('current-exercise-num');
                if (currentNumSpan && cards.length > 0) {
                    // Clamp to valid range
                    const visibleIndex = Array.from(cards).findIndex(c => !c.classList.contains('d-none'));
                    currentNumSpan.textContent = String(Math.max(1, (visibleIndex >= 0 ? visibleIndex : 0) + 1));
                }
            }
        }
    } else {
        send_toast(response.data?.detail || 'Error removing exercise', 'danger');
    }
}

// Refresh the mobile workout navigation UI after dynamic changes (e.g., deletion)
// Rebuilds indicators, reindexes cards, updates counter and prev/next handlers.
window.refreshMobileWorkoutUI = function(preferredIndex = null) {
    const container = document.getElementById('exercise-card-container');
    if (!container) return;

    container.querySelectorAll('.exercise-card').forEach(card => {
        if (!card.querySelector('.workout-exercise-card')) {
            card.remove();
        }
    });

    const cards = Array.from(container.querySelectorAll('.exercise-card'));
    const total = cards.length;

    const navBottom = document.querySelector('.exercise-navigation-bottom');
    const indicatorsContainer = document.querySelector('.exercise-indicators');
    const currentNumSpan = document.getElementById('current-exercise-num');
    const totalNumSpan = document.getElementById('total-exercises-num');

    if (total === 0) {
        if (navBottom) navBottom.style.display = 'none';
        if (currentNumSpan) currentNumSpan.textContent = '0';
        if (totalNumSpan) totalNumSpan.textContent = '0';
        if (window.mobileWorkoutController && typeof window.mobileWorkoutController.refresh === 'function') {
            window.mobileWorkoutController.refresh();
        }
        return;
    }

    cards.forEach((card, idx) => {
        card.dataset.exerciseIndex = idx;
    });

    if (indicatorsContainer) {
        indicatorsContainer.innerHTML = '';
        for (let i = 0; i < total; i++) {
            const dot = document.createElement('div');
            dot.className = 'indicator';
            dot.dataset.exerciseIndex = i;
            indicatorsContainer.appendChild(dot);
        }
    }

    if (totalNumSpan) totalNumSpan.textContent = String(total);
    if (navBottom) navBottom.style.display = '';

    let targetIndex = null;
    if (Number.isInteger(preferredIndex)) {
        targetIndex = preferredIndex;
    }

    if (window.mobileWorkoutController && typeof window.mobileWorkoutController.refresh === 'function') {
        window.mobileWorkoutController.refresh(targetIndex);
    } else {
        const clampedIndex = targetIndex !== null ? Math.max(0, Math.min(targetIndex, total - 1)) : 0;
        cards.forEach(card => card.classList.add('d-none'));
        const targetCard = cards[clampedIndex];
        if (targetCard) targetCard.classList.remove('d-none');
        if (currentNumSpan) currentNumSpan.textContent = String(clampedIndex + 1);
        const prevBtn = document.getElementById('prev-exercise');
        const nextBtn = document.getElementById('next-exercise');
        if (prevBtn) prevBtn.disabled = clampedIndex === 0;
        if (nextBtn) nextBtn.disabled = clampedIndex === total - 1;
        document.querySelectorAll('.indicator').forEach((indicator, idx) => {
            indicator.classList.toggle('active', idx === clampedIndex);
        });
    }
};

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
    const exerciseSelect = container.querySelector('select[name="exercise"]'); // Use name selector instead of ID
    const typeSelect = container.querySelector('select[name="exercise_type"]');

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
    const customFilter = document.getElementById('custom-filter');
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
    if (customFilter && customFilter.value) { // Added custom filter
        params.append('custom_filter', customFilter.value);
    }

    // Don't update the URL - just make the AJAX request
    try {
        // Use the exercises URL directly
        const url = '/exercises/?' + params.toString();
        console.log('Fetching exercises from:', url);  // Debug log

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin'  // Include cookies for authentication
        });

        console.log('Response status:', response.status);  // Debug log

        if (!response.ok) {
            console.error('Error fetching exercise list:', response.status, response.statusText);
            const errorText = await response.text();
            console.error('Error details:', errorText);
            listContainer.innerHTML = '<p class="text-danger">Error loading exercises. Please try again.</p>';
            return;
        }

        const html = await response.text();
        listContainer.innerHTML = html;

        // Event listeners are automatically attached via MutationObserver and data-function attributes
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
        const newOrder = idx + 1;
        const orderSpan = card.querySelector('.exercise-order');
        if (orderSpan) orderSpan.textContent = newOrder;

        const orderInput = card.querySelector('.exercise-order-input');
        if (orderInput) orderInput.value = newOrder;

        const upButton = card.querySelector('[data-move-direction="up"]');
        const downButton = card.querySelector('[data-move-direction="down"]');
        if (upButton) upButton.disabled = idx === 0;
        if (downButton) downButton.disabled = idx === cards.length - 1;
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
    const container = document.getElementById('routine-exercises-container');
    const button = event.target;
    const cardToRemove = button.closest('.exercise-routine-card');
    if (cardToRemove) {
        cardToRemove.remove();
        updateRoutineFormCount();
        updateRoutineExerciseOrderNumbers();
        if (container && !container.querySelector('.exercise-routine-card')) {
            const nav = document.getElementById('routine-exercise-mobile-nav');
            if (nav) nav.remove();
            if (container.dataset) {
                delete container.dataset.routineMobileInit;
                delete container.dataset.routineCurrentIndex;
            }
            const emptyMessage = document.createElement('p');
            emptyMessage.className = 'text-muted routine-empty-message';
            emptyMessage.textContent = 'No exercises added yet. Use "Add Exercise" to get started.';
            container.appendChild(emptyMessage);
        } else {
            initializeRoutineMobileView();
        }
    }
};


window.handleRoutineExerciseMove = function(event) {
    const trigger = event.target.closest('[data-move-direction]');
    if (!trigger) return;

    const direction = trigger.dataset.moveDirection;
    const card = trigger.closest('.exercise-routine-card');
    const container = card ? card.parentElement : null;
    if (!card || !container) return;

    if (direction === 'up') {
        const previous = card.previousElementSibling;
        if (previous) {
            container.insertBefore(card, previous);
        }
    } else if (direction === 'down') {
        const next = card.nextElementSibling;
        if (next) {
            container.insertBefore(next, card);
        }
    }

    updateRoutineExerciseOrderNumbers();
    bindRoutineSetSyncHandlers(newCard);
};

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
    bindRoutineSetSyncHandlers(newCard);
    // draggedItem is reset in dragend
}

function setupDragAndDropListeners(cardElement) {
    if (!cardElement || cardElement.dataset.routineDragBound === 'true') {
        return;
    }
    cardElement.dataset.routineDragBound = 'true';
    cardElement.addEventListener('dragstart', handleDragStart);
    cardElement.addEventListener('dragend', handleDragEnd);
    // Add touch support for mobile (desktop drag will ignore this)
    addTouchDragSupport(cardElement, 'routine-exercises');
}

function isRoutineDragEnabled() {
    return !window.matchMedia('(pointer: coarse)').matches;
}

function prepareRoutineExerciseCard(cardElement) {
    if (!cardElement) {
        return;
    }

    if (isRoutineDragEnabled()) {
        cardElement.setAttribute('draggable', 'true');
        setupDragAndDropListeners(cardElement);
    } else {
        cardElement.setAttribute('draggable', 'false');
    }

    const { tbody } = getRoutineSetsElements(cardElement);
    if (tbody && !tbody.querySelector('.set-row')) {
        ensureRoutineSetsEmptyRow(tbody);
    }

    updateRoutineTypeSummary(cardElement);
}

const ROUTINE_SET_COLUMNS = 7;

function getRoutineSetsElements(exerciseCard) {
    if (!exerciseCard) {
        return { setsContainer: null, tbody: null };
    }
    const setsContainer = exerciseCard.querySelector('.sets-container');
    const tbody = setsContainer ? setsContainer.querySelector('.sets-tbody') : null;
    return { setsContainer, tbody };
}

function ensureRoutineSetsEmptyRow(tbody) {
    if (!tbody || tbody.querySelector('.sets-empty-message')) {
        return;
    }
    const emptyRow = document.createElement('tr');
    emptyRow.className = 'sets-empty-message';
    const cell = document.createElement('td');
    cell.colSpan = ROUTINE_SET_COLUMNS;
    cell.className = 'text-center text-muted py-3';
    cell.textContent = 'No sets planned yet.';
    emptyRow.appendChild(cell);
    tbody.appendChild(emptyRow);
}

function updateRoutineTypeSummary(exerciseCard, fallbackTypeDisplay) {
    if (!exerciseCard) {
        return;
    }
    const summary = exerciseCard.querySelector('.routine-type-summary');
    if (!summary) {
        return;
    }

    const typeSelect = exerciseCard.querySelector('.routine-type-select');
    if (typeSelect && typeSelect.value) {
        const selectedOption = typeSelect.options[typeSelect.selectedIndex];
        summary.textContent = selectedOption ? selectedOption.textContent : 'Custom type';
        return;
    }

    const exerciseSelect = exerciseCard.querySelector('.exercise-select');
    const selectedExerciseOption = exerciseSelect ? exerciseSelect.options[exerciseSelect.selectedIndex] : null;
    const defaultDisplay = fallbackTypeDisplay
        || (selectedExerciseOption ? selectedExerciseOption.dataset.defaultTypeDisplay : null)
        || 'Select Exercise First';

    summary.textContent = `Default (${defaultDisplay})`;
}

function updateRoutineSpecificTypeLabel(event) {
    if (event) {
        event.preventDefault?.();
    }
    const select = event?.target || null;
    const exerciseCard = select ? select.closest('.exercise-routine-card') : null;
    if (!exerciseCard) {
        return;
    }
    updateRoutineTypeSummary(exerciseCard);
}

function updateExerciseCardName(event) {
    if (!event || !event.target) {
        return;
    }
    const selectElement = event.target;
    const exerciseCard = selectElement.closest('.exercise-routine-card');
    if (!exerciseCard) {
        return;
    }

    const selectedOption = selectElement.options[selectElement.selectedIndex];
    const exerciseName = selectedOption?.dataset.name || selectedOption?.text || 'Select Exercise';
    const defaultTypeDisplay = selectedOption?.dataset.defaultTypeDisplay || 'Select Exercise First';

    const nameDisplay = exerciseCard.querySelector('.exercise-name-display');
    if (nameDisplay) {
        nameDisplay.textContent = exerciseName;
    }

    const routineTypeSelect = exerciseCard.querySelector('.routine-type-select');
    if (routineTypeSelect && routineTypeSelect.options.length > 0) {
        const defaultOption = routineTypeSelect.options[0];
        defaultOption.textContent = `Default (${defaultTypeDisplay})`;
        if (!routineTypeSelect.value) {
            updateRoutineTypeSummary(exerciseCard, defaultTypeDisplay);
        }
    } else {
        updateRoutineTypeSummary(exerciseCard, defaultTypeDisplay);
    }
}

function appendExerciseCardToRoutine(exerciseId, exerciseName, defaultTypeDisplay, routineSpecificType) {
    const template = document.getElementById('routine-exercise-template');
    if (!template) {
        console.error('#routine-exercise-template not found!');
        return null;
    }

    const container = document.getElementById('routine-exercises-container');
    if (!container) {
        console.error('#routine-exercises-container not found!');
        return null;
    }

    const nextIndex = getNextRoutineExerciseIndex();
    const defaultOrder = container.querySelectorAll('.exercise-routine-card').length + 1;
    const fallbackType = defaultTypeDisplay || 'Select Exercise First';

    let content = template.innerHTML;
    content = content.replace(/__INDEX__/g, nextIndex)
                     .replace(/__ORDER__/g, defaultOrder)
                     .replace(/__EXERCISE_NAME__/g, exerciseName || 'Select Exercise')
                     .replace(/__DEFAULT_TYPE__/g, fallbackType);

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = content;
    const newCard = tempDiv.firstElementChild;
    if (!newCard) {
        console.error('Could not create new exercise card from template content.');
        return null;
    }

    newCard.dataset.index = String(nextIndex);

    const orderInput = newCard.querySelector('.exercise-order-input');
    if (orderInput) {
        orderInput.value = defaultOrder;
    }

    const emptyMessage = container.querySelector('.routine-empty-message');
    if (emptyMessage) {
        emptyMessage.remove();
    }

    const exerciseSelect = newCard.querySelector('.exercise-select');
    if (exerciseSelect && exerciseId) {
        exerciseSelect.value = exerciseId;
        updateExerciseCardName({ target: exerciseSelect });
    } else {
        updateRoutineTypeSummary(newCard, fallbackType);
    }

    const routineTypeSelect = newCard.querySelector('.routine-type-select');
    if (routineTypeSelect && routineSpecificType) {
        routineTypeSelect.value = routineSpecificType;
        updateRoutineTypeSummary(newCard);
    }

    container.appendChild(newCard);
    prepareRoutineExerciseCard(newCard);
    addSetToExerciseCard(newCard);
    updateRoutineExerciseOrderNumbers();
    updateRoutineFormCount();
    updateSetRowFieldVisibility();
    bindRoutineSetSyncHandlers(newCard);`n    initializeRoutineMobileView();

    return newCard;
}

function addSetToExerciseCard(eventOrCardElement) {
    let exerciseCard = null;
    if (eventOrCardElement instanceof HTMLElement && eventOrCardElement.classList.contains('exercise-routine-card')) {
        exerciseCard = eventOrCardElement;
    } else if (eventOrCardElement?.target) {
        eventOrCardElement.preventDefault?.();
        exerciseCard = eventOrCardElement.target.closest('.exercise-routine-card');
    }

    if (!exerciseCard) {
        return null;
    }

    const { tbody } = getRoutineSetsElements(exerciseCard);
    if (!tbody) {
        return null;
    }

    const emptyRow = tbody.querySelector('.sets-empty-message');
    if (emptyRow) {
        emptyRow.remove();
    }

    const existingRows = Array.from(tbody.querySelectorAll('.set-row'));
    let newRow;

    if (existingRows.length > 0) {
        const sourceRow = existingRows[existingRows.length - 1];
        newRow = sourceRow.cloneNode(true);
        newRow.dataset.setIndex = existingRows.length;

        newRow.querySelectorAll('input, select, textarea').forEach(input => {
            if (!input.name) {
                return;
            }
            if (input.type === 'hidden' && input.name.endsWith('_id')) {
                input.value = '';
            } else if (input.classList.contains('set-number-input')) {
                input.value = existingRows.length + 1;
            }
            if (input.dataset) {
                input.dataset.originalValue = input.value ?? '';
            }
        });
    } else {
        const setTemplate = document.getElementById('set-row-template');
        if (!setTemplate) {
            console.error('#set-row-template not found!');
            return null;
        }

        const fragment = setTemplate.content.cloneNode(true);
        newRow = fragment.querySelector('.set-row');
        newRow.dataset.setIndex = 0;

        newRow.querySelectorAll('input, select, textarea').forEach(input => {
            if (!input.name) {
                return;
            }
            input.name = input.name
                .replace(/__EXERCISE_INDEX__/g, exerciseCard.dataset.index)
                .replace(/__SET_INDEX__/g, 0)
                .replace(/__SET_NUMBER__/g, 1);

            if (input.type === 'hidden' && input.name.endsWith('_id')) {
                input.value = '';
            } else if (input.classList.contains('set-number-input')) {
                input.value = 1;
            } else {
                input.value = '';
            }
            if (input.dataset) {
                input.dataset.originalValue = input.value ?? '';
            }
        });
    }

    tbody.appendChild(newRow);
    updateSetNumbers(exerciseCard);
    updateSetRowFieldVisibility();
    bindRoutineSetSyncHandlers(exerciseCard);`n    return newRow;
}
function removeSetFromExerciseCard(event) {
    if (event) {
        event.preventDefault?.();
    }
    const trigger = event?.target;
    const setRow = trigger ? trigger.closest('.set-row') : null;
    if (!setRow) {
        return;
    }

    const exerciseCard = setRow.closest('.exercise-routine-card');
    const { tbody } = getRoutineSetsElements(exerciseCard);
    setRow.remove();

    updateSetNumbers(exerciseCard);
    if (tbody && !tbody.querySelector('.set-row')) {
        ensureRoutineSetsEmptyRow(tbody);
    }
}

function duplicateSetRow(event) {
    if (event) {
        event.preventDefault?.();
    }
    const trigger = event?.target;
    const sourceRow = trigger ? trigger.closest('.set-row') : null;
    if (!sourceRow) {
        return;
    }

    const exerciseCard = sourceRow.closest('.exercise-routine-card');
    const { tbody } = getRoutineSetsElements(exerciseCard);
    if (!tbody) {
        return;
    }

    const emptyRow = tbody.querySelector('.sets-empty-message');
    if (emptyRow) {
        emptyRow.remove();
    }

    const clone = sourceRow.cloneNode(true);
    clone.querySelectorAll('input, select, textarea').forEach(input => {
        if (input.type === 'hidden' && input.name && input.name.endsWith('_id')) {
            input.value = '';
        }
    });

    tbody.appendChild(clone);
    updateSetNumbers(exerciseCard);
    updateSetRowFieldVisibility();
    bindRoutineSetSyncHandlers(container);
}
function getRoutineSetFieldKey(input) {
    const name = input?.name || '';
    if (name.includes('_target_reps')) {
        return 'target_reps';
    }
    if (name.includes('_target_weight')) {
        return 'target_weight';
    }
    return null;
}

function normalizeRoutineSetFieldValue(value, fieldKey) {
    if (value === null || value === undefined) {
        return '';
    }
    const trimmed = String(value).trim();
    if (!trimmed) {
        return '';
    }
    if (fieldKey === 'target_weight') {
        const numeric = Number(trimmed);
        return Number.isFinite(numeric) ? numeric : trimmed;
    }
    return trimmed;
}

function captureRoutineSetFieldOriginalValue(event) {
    const input = event?.target;
    if (!input) {
        return;
    }
    input.dataset.originalValue = input.value ?? '';
}

function handleRoutineSetFieldChange(event) {
    const input = event?.target;
    if (!input) {
        return;
    }

    const fieldKey = getRoutineSetFieldKey(input);
    const newValue = input.value ?? '';
    const originalValue = input.dataset.originalValue ?? '';
    input.dataset.originalValue = newValue;

    if (!fieldKey) {
        return;
    }

    const normalizedOriginal = normalizeRoutineSetFieldValue(originalValue, fieldKey);
    const normalizedNew = normalizeRoutineSetFieldValue(newValue, fieldKey);
    if (normalizedOriginal === normalizedNew) {
        return;
    }

    const exerciseCard = input.closest('.exercise-routine-card');
    if (!exerciseCard) {
        return;
    }

    const selector = `input[name*="_${fieldKey}"]`;

    exerciseCard.querySelectorAll(selector).forEach(otherInput => {
        if (otherInput === input) {
            return;
        }
        const otherValue = otherInput.value ?? '';
        if (normalizeRoutineSetFieldValue(otherValue, fieldKey) !== normalizedOriginal) {
            return;
        }
        otherInput.value = newValue;
        otherInput.dataset.originalValue = newValue;
    });
}

function updateSetNumbers(exerciseCard) {
    if (!exerciseCard) {
        return;
    }
    const exerciseIndex = exerciseCard.dataset.index;
    const { tbody } = getRoutineSetsElements(exerciseCard);
    if (!tbody) {
        return;
    }

    const rows = Array.from(tbody.querySelectorAll('.set-row'));
    rows.forEach((row, index) => {
        row.dataset.setIndex = index;

        const numberDisplay = row.querySelector('.set-number-display');
        if (numberDisplay) {
            numberDisplay.textContent = `Set ${index + 1}`;
        }

        row.querySelectorAll('input, select, textarea').forEach(input => {
            if (!input.name) {
                return;
            }
            let name = input.name;
            name = name.replace(/planned_sets_\d+_/g, `planned_sets_${index}_`)
                       .replace(/planned_sets\[\d+\]/g, `planned_sets[${index}]`)
                       .replace(/__SET_INDEX__/g, index)
                       .replace(/__SET_NUMBER__/g, index + 1);
            if (exerciseIndex !== undefined && exerciseIndex !== null && exerciseIndex !== "") {
                name = name.replace(/routine_exercise_\d+_/g, `routine_exercise_${exerciseIndex}_`)
                           .replace(/routine_exercise\[\d+\]/g, `routine_exercise[${exerciseIndex}]`)
                           .replace(/__EXERCISE_INDEX__/g, exerciseIndex);
            }
            input.name = name;

            if (input.classList.contains('set-number-input')) {
                input.value = index + 1;
            }
        });
    });

    if (!rows.length) {
        ensureRoutineSetsEmptyRow(tbody);
    }
}

function updateSetRowFieldVisibility() {
    const showRPE = document.getElementById('toggle-rpe-visibility')?.checked ?? true;
    const showRest = document.getElementById('toggle-rest-time-visibility')?.checked ?? true;
    const showNotes = document.getElementById('toggle-notes-visibility')?.checked ?? true;

    document.querySelectorAll('#routine-exercises-container .set-row').forEach(row => {
        const rpeField = row.querySelector('.rpe-field');
        if (rpeField) {
            rpeField.style.display = showRPE ? 'block' : 'none';
        }
        const restField = row.querySelector('.rest-time-field');
        if (restField) {
            restField.style.display = showRest ? 'block' : 'none';
        }
        const notesField = row.querySelector('.notes-field');
        if (notesField) {
            notesField.style.display = showNotes ? 'block' : 'none';
        }
    });
}

function addExerciseToRoutineFromForm(event) {
    if (event) {
        event.preventDefault?.();
    }

    const exerciseSelect = document.getElementById('routine-add-exercise-select');
    const typeSelect = document.getElementById('routine-add-exercise-type');

    if (!exerciseSelect) {
        return;
    }

    const exerciseId = exerciseSelect.value;
    if (!exerciseId) {
        if (typeof send_toast === 'function') {
            send_toast('Please select an exercise', 'warning');
        }
        return;
    }

    const selectedOption = exerciseSelect.options[exerciseSelect.selectedIndex];
    const exerciseName = selectedOption?.dataset.name || selectedOption?.text || 'Select Exercise';
    const defaultTypeDisplay = selectedOption?.dataset.defaultTypeDisplay || 'Select Exercise First';
    const routineSpecificType = typeSelect ? typeSelect.value : '';

    const newCard = appendExerciseCardToRoutine(exerciseId, exerciseName, defaultTypeDisplay, routineSpecificType);
    if (newCard && typeof send_toast === 'function') {
        send_toast('Exercise added to routine', 'success');
    }

    if (exerciseSelect) {
        exerciseSelect.value = '';
    }
    if (typeSelect) {
        typeSelect.value = '';
    }
}

function initializeRoutineForm() {
    const container = document.getElementById('routine-exercises-container');
    if (!container) {
        return;
    }

    container.querySelectorAll('.exercise-routine-card').forEach(card => {
        prepareRoutineExerciseCard(card);
        updateRoutineTypeSummary(card);
    });

    if (!container.dataset.routineListenersBound) {
        container.addEventListener('dragover', handleDragOver);
        container.addEventListener('drop', handleDrop);
        container.dataset.routineListenersBound = 'true';
    }

    updateRoutineExerciseOrderNumbers();
    updateRoutineFormCount();
    updateSetRowFieldVisibility();
    bindRoutineSetSyncHandlers(newCard);`n    initializeRoutineMobileView();
}

window.updateRoutineSpecificTypeLabel = updateRoutineSpecificTypeLabel;
window.captureRoutineSetFieldOriginalValue = captureRoutineSetFieldOriginalValue;
window.handleRoutineSetFieldChange = handleRoutineSetFieldChange;
window.captureWorkoutSetOriginalValue = captureWorkoutSetOriginalValue;
window.handleWorkoutSetChange = handleWorkoutSetChange;
window.updateExerciseCardName = updateExerciseCardName;
window.appendExerciseCardToRoutine = appendExerciseCardToRoutine;
window.addSetToExerciseCard = addSetToExerciseCard;
window.removeSetFromExerciseCard = removeSetFromExerciseCard;
window.duplicateSetRow = duplicateSetRow;
window.updateSetRowFieldVisibility = updateSetRowFieldVisibility;
window.addExerciseToRoutineFromForm = addExerciseToRoutineFromForm;

// ======================================
//      WORKOUT EXERCISES DRAG & DROP
// ======================================

let workoutDraggedItem = null;
let workoutFloatingClone = null;
let workoutDragOffsetX = 0;
let workoutDragOffsetY = 0;

function handleWorkoutExerciseDragStart(event) {
    workoutDraggedItem = event.target;
    if (!workoutDraggedItem.classList.contains('workout-exercise-card')) return;

    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', workoutDraggedItem.dataset.exerciseId);

    // Create transparent image to hide default ghost
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    event.dataTransfer.setDragImage(img, 0, 0);

    // Create visual clone
    workoutFloatingClone = workoutDraggedItem.cloneNode(true);
    workoutFloatingClone.classList.add('dragging-clone');

    const rect = workoutDraggedItem.getBoundingClientRect();
    workoutFloatingClone.style.width = `${rect.width}px`;
    workoutFloatingClone.style.height = `${rect.height}px`;

    document.body.appendChild(workoutFloatingClone);

    workoutDragOffsetX = event.clientX - rect.left;
    workoutDragOffsetY = event.clientY - rect.top;

    workoutFloatingClone.style.left = `${event.clientX - workoutDragOffsetX}px`;
    workoutFloatingClone.style.top = `${event.clientY - workoutDragOffsetY}px`;

    setTimeout(() => {
        if(workoutDraggedItem) workoutDraggedItem.classList.add('drag-source-hidden');
    }, 0);

    document.addEventListener('dragover', handleWorkoutExerciseDragMouseMove);
}

function handleWorkoutExerciseDragMouseMove(event) {
    if (workoutFloatingClone) {
        workoutFloatingClone.style.left = `${event.clientX - workoutDragOffsetX}px`;
        workoutFloatingClone.style.top = `${event.clientY - workoutDragOffsetY}px`;
    }
}

function handleWorkoutExerciseDragEnd(event) {
    if (workoutFloatingClone) {
        document.body.removeChild(workoutFloatingClone);
        workoutFloatingClone = null;
    }
    if (workoutDraggedItem) {
        workoutDraggedItem.classList.remove('drag-source-hidden');
        workoutDraggedItem.style.opacity = '';
    }
    workoutDraggedItem = null;
    document.removeEventListener('dragover', handleWorkoutExerciseDragMouseMove);
}

function handleWorkoutExerciseDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';

    const container = event.currentTarget;
    if (!workoutDraggedItem) return;

    const afterElement = getWorkoutDragAfterElement(container, event.clientY, workoutDraggedItem);
    if (afterElement === undefined && container.lastChild !== workoutDraggedItem) {
        // Can move to end
    } else if (afterElement && afterElement !== workoutDraggedItem) {
        // Can insert before afterElement
    }
}

function getWorkoutDragAfterElement(container, y, currentDraggedItem) {
    const draggableElements = [...container.querySelectorAll('.workout-exercise-card:not(.drag-source-hidden)')];

    return draggableElements.reduce((closest, child) => {
        if (child === currentDraggedItem) return closest;
        const box = child.getBoundingClientRect();
        const offset = y - box.top - box.height / 2;
        if (offset < 0 && offset > closest.offset) {
            return { offset: offset, element: child };
        } else {
            return closest;
        }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
}

function handleWorkoutExerciseDrop(event) {
    event.preventDefault();
    if (workoutDraggedItem) {
        const container = event.currentTarget;
        const afterElement = getWorkoutDragAfterElement(container, event.clientY, workoutDraggedItem);

        if (afterElement) {
            container.insertBefore(workoutDraggedItem, afterElement);
        } else {
            container.appendChild(workoutDraggedItem);
        }
        workoutDraggedItem.classList.remove('drag-source-hidden');

        // Update order in database
        updateWorkoutExerciseOrder(container);
    }
}

async function updateWorkoutExerciseOrder(container) {
    const workoutId = document.getElementById('workout-exercises-container').dataset.workoutId;
    const exercises = container.querySelectorAll('.workout-exercise-card');
    const updates = [];

    exercises.forEach((card, index) => {
        const exerciseId = card.dataset.exerciseId;
        updates.push({
            id: exerciseId,
            order: index + 1
        });
    });

    // Send update to backend
    try {
        const response = await httpRequestHelper(`/api/workouts/${workoutId}/reorder-exercises/`, 'POST', {
            exercises: updates
        });

        if (response.ok) {
            send_toast('Exercise order updated', 'success');
        } else {
            send_toast('Failed to update exercise order', 'danger');
            // Optionally reload to restore original order
        }
    } catch (error) {
        console.error('Error updating exercise order:', error);
        send_toast('Error updating exercise order', 'danger');
    }
}

function initializeWorkoutExercisesDragDrop() {
    bindWorkoutSetSyncHandlers(document);
    const container = document.getElementById('workout-exercises-container');
    if (!container) return;

    // Set up drag and drop for all exercise cards
    container.querySelectorAll('.workout-exercise-card').forEach(card => {
        card.addEventListener('dragstart', handleWorkoutExerciseDragStart);
        card.addEventListener('dragend', handleWorkoutExerciseDragEnd);
        // Add touch support for mobile
        addTouchDragSupport(card, 'workout-exercises');
    });

    // Set up drop zones for each category
    container.querySelectorAll('.exercise-category-container').forEach(categoryContainer => {
        categoryContainer.addEventListener('dragover', handleWorkoutExerciseDragOver);
        categoryContainer.addEventListener('drop', handleWorkoutExerciseDrop);
    });
}

// ======================================
//      PROGRAM ROUTINES DRAG & DROP
// ======================================

let programDraggedChip = null;
let programFloatingClone = null;

const DOUBLE_ACTIVATE_MAX_DELAY = 350;
const DOUBLE_ACTIVATE_MAX_DISTANCE = 12;
const ROUTINE_ACTIVATION_HINT = 'Double tap or double click to open routine';
const doubleActivateState = {
    lastTapTime: 0,
    lastTapX: 0,
    lastTapY: 0,
    lastTarget: null,
    resetTimer: null,
};

function resetDoubleActivateState() {
    if (doubleActivateState.resetTimer) {
        clearTimeout(doubleActivateState.resetTimer);
        doubleActivateState.resetTimer = null;
    }
    doubleActivateState.lastTapTime = 0;
    doubleActivateState.lastTarget = null;
    doubleActivateState.lastTapX = 0;
    doubleActivateState.lastTapY = 0;
}

function attachDoubleActivate(element, callback, options = {}) {
    if (!element || element.dataset.doubleActivateBound === 'true') {
        return;
    }

    element.dataset.doubleActivateBound = 'true';

    const isDragging = typeof options.isDragging === 'function' ? options.isDragging : () => false;
    const shouldIgnore = typeof options.shouldIgnore === 'function' ? options.shouldIgnore : () => false;
    const forceTabIndex = options.forceTabIndex !== false;

    if (forceTabIndex && element.tabIndex < 0) {
        element.tabIndex = 0;
    }

    element.addEventListener('dblclick', (event) => {
        if (isDragging() || shouldIgnore(event)) {
            resetDoubleActivateState();
            return;
        }
        resetDoubleActivateState();
        callback({ trigger: 'dblclick', event });
    });

    element.addEventListener('touchend', (event) => {
        if (isDragging() || shouldIgnore(event) || (event.touches && event.touches.length)) {
            resetDoubleActivateState();
            return;
        }

        const touch = event.changedTouches && event.changedTouches[0];
        if (!touch) {
            return;
        }

        const now = performance.now();
        const { lastTapTime, lastTapX, lastTapY, lastTarget, resetTimer } = doubleActivateState;

        if (resetTimer) {
            clearTimeout(resetTimer);
            doubleActivateState.resetTimer = null;
        }

        const isSameTarget = lastTarget === element;
        const withinTime = now - lastTapTime <= DOUBLE_ACTIVATE_MAX_DELAY;
        const withinDistance = Math.abs(touch.clientX - lastTapX) <= DOUBLE_ACTIVATE_MAX_DISTANCE &&
                               Math.abs(touch.clientY - lastTapY) <= DOUBLE_ACTIVATE_MAX_DISTANCE;

        if (isSameTarget && withinTime && withinDistance) {
            resetDoubleActivateState();
            event.preventDefault();
            callback({ trigger: 'doubletap', event });
            return;
        }

        doubleActivateState.lastTapTime = now;
        doubleActivateState.lastTapX = touch.clientX;
        doubleActivateState.lastTapY = touch.clientY;
        doubleActivateState.lastTarget = element;
        doubleActivateState.resetTimer = setTimeout(() => {
            resetDoubleActivateState();
        }, DOUBLE_ACTIVATE_MAX_DELAY);
    }, { passive: false });

    element.addEventListener('keydown', (event) => {
        if (isDragging() || shouldIgnore(event)) {
            return;
        }

        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            resetDoubleActivateState();
            callback({ trigger: 'keyboard', event });
        }
    });
}

function openRoutineDetail(routineId) {
    if (!routineId) {
        return;
    }

    const url = `/routines/${routineId}/`;
    const newWindow = window.open(url, '_blank');
    if (newWindow) {
        newWindow.opener = null;
    } else {
        window.location.assign(url);
    }
}

let programDragOffsetX = 0;
let programDragOffsetY = 0;

function handleProgramRoutineDragStart(event) {
    programDraggedChip = event.target;
    if (!programDraggedChip.classList.contains('routine-chip')) return;

    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', programDraggedChip.dataset.routineId);

    // Create transparent image to hide default ghost
    const img = new Image();
    img.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    event.dataTransfer.setDragImage(img, 0, 0);

    // Create visual clone
    programFloatingClone = programDraggedChip.cloneNode(true);
    programFloatingClone.classList.add('dragging-clone');

    const rect = programDraggedChip.getBoundingClientRect();
    programFloatingClone.style.width = `${rect.width}px`;
    programFloatingClone.style.height = `${rect.height}px`;

    document.body.appendChild(programFloatingClone);

    programDragOffsetX = event.clientX - rect.left;
    programDragOffsetY = event.clientY - rect.top;

    programFloatingClone.style.left = `${event.clientX - programDragOffsetX}px`;
    programFloatingClone.style.top = `${event.clientY - programDragOffsetY}px`;

    setTimeout(() => {
        if(programDraggedChip) programDraggedChip.classList.add('drag-source-hidden');
    }, 0);

    document.addEventListener('dragover', handleProgramRoutineDragMouseMove);
}

function handleProgramRoutineDragMouseMove(event) {
    if (programFloatingClone) {
        programFloatingClone.style.left = `${event.clientX - programDragOffsetX}px`;
        programFloatingClone.style.top = `${event.clientY - programDragOffsetY}px`;
    }
}

function handleProgramRoutineDragEnd(event) {
    if (programFloatingClone) {
        document.body.removeChild(programFloatingClone);
        programFloatingClone = null;
    }
    if (programDraggedChip) {
        programDraggedChip.classList.remove('drag-source-hidden');
        programDraggedChip.style.opacity = '';
    }
    programDraggedChip = null;
    document.removeEventListener('dragover', handleProgramRoutineDragMouseMove);
}

function handleProgramRoutineDragOver(event) {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';

    // Visual feedback: you could add a highlight to the container
    const container = event.currentTarget;
    container.classList.add('drag-over');
}

function handleProgramRoutineDragLeave(event) {
    const container = event.currentTarget;
    container.classList.remove('drag-over');
}

function handleProgramRoutineDrop(event) {
    event.preventDefault();
    const container = event.currentTarget;
    container.classList.remove('drag-over');

    if (programDraggedChip) {
        const newDayValue = container.closest('.day-column').dataset.dayValue;

        // Update the hidden input's name to reflect the new day
        const hiddenInput = programDraggedChip.querySelector('input[type="hidden"]');
        if (hiddenInput) {
            hiddenInput.name = `weekly_day_${newDayValue}_routines`;
        }

        // Move the chip to the new container
        container.appendChild(programDraggedChip);
        programDraggedChip.classList.remove('drag-source-hidden');
    }
}

function setupProgramRoutineDragListeners(chip) {
    if (!chip) {
        return;
    }

    if (chip.dataset.programRoutineListenersBound === 'true') {
        return;
    }

    chip.dataset.programRoutineListenersBound = 'true';

    chip.addEventListener('dragstart', (event) => {
        resetDoubleActivateState();
        handleProgramRoutineDragStart(event);
    });

    chip.addEventListener('dragend', (event) => {
        handleProgramRoutineDragEnd(event);
        resetDoubleActivateState();
    });

    addTouchDragSupport(chip, 'program-routines');

    if (!chip.hasAttribute('tabindex')) {
        chip.tabIndex = 0;
    }

    const routineName = chip.dataset.routineName || chip.querySelector('.routine-chip-label')?.textContent?.trim() || chip.textContent.trim();
    const labelText = routineName ? `${routineName}. ${ROUTINE_ACTIVATION_HINT}` : ROUTINE_ACTIVATION_HINT;
    chip.setAttribute('aria-label', labelText);
    chip.setAttribute('title', ROUTINE_ACTIVATION_HINT);

    attachDoubleActivate(chip, () => {
        const routineId = chip.dataset.routineId;
        if (routineId) {
            openRoutineDetail(routineId);
        }
    }, {
        isDragging: () => Boolean(programDraggedChip) || touchDragData.isDragging,
        shouldIgnore: (event) => Boolean(event.target.closest('[data-ignore-double-activate="true"]'))
    });
}

function setupSequentialRoutineActivation(row) {
    if (!row) {
        return;
    }

    const routineIdInput = row.querySelector('input[name*="_routine_id"]');
    const routineNameField = row.querySelector('input[type="text"][readonly]');

    if (!routineIdInput || !routineNameField) {
        return;
    }

    routineNameField.dataset.routineId = routineIdInput.value;
    routineNameField.dataset.routineName = routineNameField.value;
    routineNameField.setAttribute('title', ROUTINE_ACTIVATION_HINT);
    const routineLabel = routineNameField.value ? `${routineNameField.value}. ${ROUTINE_ACTIVATION_HINT}` : ROUTINE_ACTIVATION_HINT;
    routineNameField.setAttribute('aria-label', routineLabel);

    attachDoubleActivate(routineNameField, () => {
        const routineId = routineIdInput.value;
        if (routineId) {
            openRoutineDetail(routineId);
        }
    }, {
        forceTabIndex: false,
        isDragging: () => touchDragData.isDragging,
        shouldIgnore: (event) => Boolean(event.target.closest('.remove-pr-btn'))
    });
}

function initializeProgramRoutinesDragDrop() {
    const weeklyContainer = document.getElementById('weekly-schedule-container');
    if (!weeklyContainer) return;

    // Set up drag and drop for all existing routine chips
    weeklyContainer.querySelectorAll('.routine-chip').forEach(chip => {
        setupProgramRoutineDragListeners(chip);
    });

    // Set up drop zones for each day
    weeklyContainer.querySelectorAll('.routines-for-day-container').forEach(container => {
        container.addEventListener('dragover', handleProgramRoutineDragOver);
        container.addEventListener('dragleave', handleProgramRoutineDragLeave);
        container.addEventListener('drop', handleProgramRoutineDrop);
    });
}

// ======================================
//      PROGRAM FORM FUNCTIONS
// ======================================

window.handleAddRoutineToProgram = function() { // This function is now globally accessible
    const select = document.getElementById('add-routine-select');
    const selectedOption = select.options[select.selectedIndex];
    if (!selectedOption || !selectedOption.value) {
        send_toast('Please select a routine to add.', 'warning');
        return;
    }

    const routineId = selectedOption.value;
    const routineName = selectedOption.dataset.name;

    // Remove the option from the select to prevent adding it again
    selectedOption.remove();
    select.value = ''; // Reset select

    // Get the template
    const template = document.getElementById('program-routine-template');
    if (!template) {
        console.error('Program routine template not found!');
        return;
    }

    // Get the container and create a new row from the template
    const container = document.getElementById('program-routines-container');
    const newIndex = container.querySelectorAll('.program-routine-row').length;
    const newOrder = newIndex + 1; // Default order

    let newRowHTML = template.innerHTML;
    newRowHTML = newRowHTML.replace(/__INDEX__/g, newIndex)
                           .replace(/__ROUTINE_ID__/g, routineId)
                           .replace(/__ROUTINE_NAME__/g, routineName)
                           .replace(/__ORDER__/g, newOrder);

    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = newRowHTML;
    const newRow = tempDiv.firstElementChild; // The new .program-routine-row div

    container.appendChild(newRow);
    setupSequentialRoutineActivation(newRow);
}

window.handleRemoveProgramRoutine = function(event) { // This function is now globally accessible
    const row = event.target.closest('.program-routine-row');
    if (!row) return;

    const routineId = row.querySelector('input[name*="_routine_id"]').value;
    const routineName = row.querySelector('input[readonly]').value;

    // Add the routine back to the select dropdown
    const select = document.getElementById('add-routine-select');
    if (select && routineId && routineName) {
        const option = document.createElement('option');
        option.value = routineId;
        option.textContent = routineName;
        option.dataset.name = routineName;
        select.appendChild(option);
    }

    row.remove();

    // After removing, we might want to re-index the remaining rows
    // to ensure form submission works correctly if the backend expects
    // a continuous sequence of indices.
    const container = document.getElementById('program-routines-container');
    const rows = container.querySelectorAll('.program-routine-row');
    rows.forEach((r, index) => {
        r.dataset.index = index;
        r.querySelectorAll('input, select').forEach(input => {
            if (input.name) {
                input.name = input.name.replace(/program_routine_\d+/, `program_routine_${index}_`);
            }
            if (input.id) {
                input.id = input.id.replace(/_\d+$/, `_${index}`);
            }
        });
    });
}

function handleAddRoutineToDay(event) {
    const select = event.target;
    const selectedOption = select.options[select.selectedIndex];
    if (!selectedOption || !selectedOption.value) return;

    const routineId = selectedOption.value;
    const routineName = selectedOption.textContent;
    const dayColumn = select.closest('.day-column');
    const dayValue = dayColumn.dataset.dayValue;
    const container = dayColumn.querySelector('.routines-for-day-container');

    // Create the chip
    const chip = document.createElement('div');
    chip.className = 'routine-chip';
    chip.draggable = true; // Make it draggable
    chip.dataset.routineId = routineId;
    chip.dataset.routineName = routineName; // Store name for drag and drop
    chip.innerHTML = `
        <span class="routine-chip-label">${routineName}</span>
        <div class="d-flex align-items-center">
            <button type="button" class="btn-close btn-close-white btn-sm" data-ignore-double-activate="true" aria-label="Remove"></button>
        </div>
        <input type="hidden" name="weekly_day_${dayValue}_routines" value="${routineId}">
    `;

    container.appendChild(chip);

    // Set up drag and drop listeners for the new chip
    setupProgramRoutineDragListeners(chip);

    // Reset the select
    select.value = '';
}

function handleRemoveRoutineFromDay(chipElement) {
    chipElement.remove();
}


// ======================================
//      MOBILE TOUCH DRAG & DROP SUPPORT
// ======================================

let touchDragData = {
    isDragging: false,
    draggedElement: null,
    startX: 0,
    startY: 0,
    offsetX: 0,
    offsetY: 0,
    clone: null,
    originalParent: null,
    dragType: null // 'routine-exercises', 'workout-exercises', 'program-routines'
};

function addTouchDragSupport(element, dragType) {
    if (!element || element.dataset.touchDragBound === 'true') {
        return;
    }

    element.dataset.touchDragBound = 'true';
    element.addEventListener('touchstart', (e) => handleTouchStart(e, dragType), { passive: false });
    element.addEventListener('touchmove', handleTouchMove, { passive: false });
    element.addEventListener('touchend', handleTouchEnd, { passive: false });
}
function handleTouchStart(event, dragType) {
    if (event.touches.length !== 1) return;

    const touch = event.touches[0];
    const element = event.currentTarget;

    // Only start drag for draggable elements
    if (!element.draggable) return;

    touchDragData.isDragging = false; // Will be set to true in touchmove if threshold exceeded
    touchDragData.draggedElement = element;
    touchDragData.startX = touch.clientX;
    touchDragData.startY = touch.clientY;
    touchDragData.dragType = dragType;
    touchDragData.originalParent = element.parentNode;

    const rect = element.getBoundingClientRect();
    touchDragData.offsetX = touch.clientX - rect.left;
    touchDragData.offsetY = touch.clientY - rect.top;

    // Prevent default to avoid scrolling while potentially dragging
    event.preventDefault();
}

function handleTouchMove(event) {
    if (!touchDragData.draggedElement || event.touches.length !== 1) return;

    const touch = event.touches[0];
    const deltaX = Math.abs(touch.clientX - touchDragData.startX);
    const deltaY = Math.abs(touch.clientY - touchDragData.startY);

    // Threshold to start dragging (prevents accidental drags)
    if (!touchDragData.isDragging && (deltaX > 10 || deltaY > 10)) {
        touchDragData.isDragging = true;
        startTouchDrag(event);
    }

    if (touchDragData.isDragging) {
        updateTouchDrag(event);
    }

    event.preventDefault();
}

function startTouchDrag(event) {
    const element = touchDragData.draggedElement;

    // Create visual clone
    touchDragData.clone = element.cloneNode(true);
    touchDragData.clone.classList.add('dragging-clone');
    touchDragData.clone.style.pointerEvents = 'none';
    touchDragData.clone.style.transform = 'rotate(5deg)';
    touchDragData.clone.style.opacity = '0.8';

    const rect = element.getBoundingClientRect();
    touchDragData.clone.style.width = `${rect.width}px`;
    touchDragData.clone.style.height = `${rect.height}px`;

    document.body.appendChild(touchDragData.clone);

    // Hide original element
    element.classList.add('drag-source-hidden');

    // Call appropriate drag start handler
    simulateDragStart(element);
}

function updateTouchDrag(event) {
    if (!touchDragData.clone) return;

    const touch = event.touches[0];
    touchDragData.clone.style.left = `${touch.clientX - touchDragData.offsetX}px`;
    touchDragData.clone.style.top = `${touch.clientY - touchDragData.offsetY}px`;

    // Find element under touch (excluding the clone)
    touchDragData.clone.style.display = 'none';
    const elementBelow = document.elementFromPoint(touch.clientX, touch.clientY);
    touchDragData.clone.style.display = 'block';

    if (elementBelow) {
        handleTouchDragOver(elementBelow, touch);
    }
}

function handleTouchDragOver(elementBelow, touch) {
    const draggedElement = touchDragData.draggedElement;

    switch (touchDragData.dragType) {
        case 'routine-exercises':
            const routineContainer = document.getElementById('routine-exercises-container');
            if (routineContainer && routineContainer.contains(elementBelow)) {
                // Simulate routine exercise reordering
                const afterElement = getDragAfterElement(routineContainer, touch.clientY, draggedElement);
                if (afterElement && afterElement !== draggedElement) {
                    routineContainer.insertBefore(draggedElement, afterElement);
                } else if (!afterElement) {
                    routineContainer.appendChild(draggedElement);
                }
            }
            break;

        case 'workout-exercises':
            const categoryContainer = elementBelow.closest('.exercise-category-container');
            if (categoryContainer) {
                const afterElement = getWorkoutDragAfterElement(categoryContainer, touch.clientY, draggedElement);
                if (afterElement && afterElement !== draggedElement) {
                    categoryContainer.insertBefore(draggedElement, afterElement);
                } else if (!afterElement) {
                    categoryContainer.appendChild(draggedElement);
                }
            }
            break;

        case 'program-routines':
            const dayContainer = elementBelow.closest('.routines-for-day-container');
            if (dayContainer && dayContainer !== touchDragData.originalParent) {
                // Update hidden input for new day
                const newDayValue = dayContainer.closest('.day-column').dataset.dayValue;
                const hiddenInput = draggedElement.querySelector('input[type="hidden"]');
                if (hiddenInput) {
                    hiddenInput.name = `weekly_day_${newDayValue}_routines`;
                }
                dayContainer.appendChild(draggedElement);
            }
            break;
    }
}

function handleTouchEnd(event) {
    if (!touchDragData.isDragging) {
        // Not a drag, might be a tap - reset and allow normal behavior
        resetTouchDrag();
        return;
    }

    event.preventDefault();

    if (touchDragData.draggedElement) {
        // Restore visibility
        touchDragData.draggedElement.classList.remove('drag-source-hidden');

        // Call appropriate update functions
        switch (touchDragData.dragType) {
            case 'routine-exercises':
                updateRoutineExerciseOrderNumbers();
    bindRoutineSetSyncHandlers(newCard);
                break;
            case 'workout-exercises':
                const container = touchDragData.draggedElement.closest('.exercise-category-container');
                if (container) {
                    updateWorkoutExerciseOrder(container);
                }
                break;
            case 'program-routines':
                // Program routine updates are handled in handleTouchDragOver
                break;
        }
    }

    resetTouchDrag();
}

function simulateDragStart(element) {
    // Set the appropriate global drag variables based on drag type
    switch (touchDragData.dragType) {
        case 'routine-exercises':
            draggedItem = element;
            break;
        case 'workout-exercises':
            workoutDraggedItem = element;
            break;
        case 'program-routines':
            programDraggedChip = element;
            break;
    }
}

function resetTouchDrag() {
    if (touchDragData.clone) {
        document.body.removeChild(touchDragData.clone);
    }

    if (touchDragData.draggedElement) {
        touchDragData.draggedElement.classList.remove('drag-source-hidden');
    }

    // Reset global drag variables
    draggedItem = null;
    workoutDraggedItem = null;
    programDraggedChip = null;

    touchDragData = {
        isDragging: false,
        draggedElement: null,
        startX: 0,
        startY: 0,
        offsetX: 0,
        offsetY: 0,
        clone: null,
        originalParent: null,
        dragType: null
    };
    resetDoubleActivateState();
}

// ======================================
//      INITIALIZE TOUCH SUPPORT
// ======================================

function initializeTouchDragSupport() {
    // Routine exercises
    const routineContainer = document.getElementById('routine-exercises-container');
    if (routineContainer) {
        routineContainer.querySelectorAll('.exercise-routine-card[draggable="true"]').forEach(card => {
            addTouchDragSupport(card, 'routine-exercises');
        });
    }

    // Workout exercises
    const workoutContainer = document.getElementById('workout-exercises-container');
    if (workoutContainer) {
        workoutContainer.querySelectorAll('.workout-exercise-card[draggable="true"]').forEach(card => {
            addTouchDragSupport(card, 'workout-exercises');
        });
    }

    // Program routine chips
    const weeklyContainer = document.getElementById('weekly-schedule-container');
    if (weeklyContainer) {
        weeklyContainer.querySelectorAll('.routine-chip[draggable="true"]').forEach(chip => {
            addTouchDragSupport(chip, 'program-routines');
        });
    }
}
let gainzAppInitialized = false;

function bootstrapGainzApp() {
    if (gainzAppInitialized) {
        return;
    }
    gainzAppInitialized = true;

    if (!mutationObserverStarted && document.body) {
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            attributes: true,
            attributeFilter: ['data-function']
        });
        mutationObserverStarted = true;

        document.querySelectorAll('[data-function]').forEach(element => {
            const attr = element.getAttributeNode('data-function');
            if (attr) {
                handle_attribute(element, attr);
            }
        });
    }

    initializeRoutineForm();
    initializeWorkoutExercisesDragDrop();
    initializeProgramRoutinesDragDrop();
    initializeTouchDragSupport();
    window.addEventListener('resize', initializeRoutineMobileView);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrapGainzApp);
} else {
    bootstrapGainzApp();
}
function bindRoutineSetSyncHandlers(root) {
    const scope = root || document;
    const inputs = scope.querySelectorAll('#routine-exercises-container input[name*="_target_reps"], #routine-exercises-container input[name*="_target_weight"]');
    inputs.forEach(input => {
        if (input.dataset.routineSyncBound === 'true') {
            return;
        }
        input.addEventListener('focus', captureRoutineSetFieldOriginalValue);
        input.addEventListener('change', handleRoutineSetFieldChange);
        input.dataset.routineSyncBound = 'true';
    });
}

function bindWorkoutSetSyncHandlers(root) {
    const scope = root || document;
    const inputs = scope.querySelectorAll('.sets-container [data-field="reps"], .sets-container [data-field="weight"]');
    inputs.forEach(input => {
        if (input.dataset.workoutSyncBound === 'true') {
            return;
        }
        input.addEventListener('focus', captureWorkoutSetOriginalValue);
        input.addEventListener('blur', handleWorkoutSetChange);
        input.dataset.workoutSyncBound = 'true';
    });
}
function initializeRoutineMobileView() {
    const container = document.getElementById('routine-exercises-container');
    if (!container) return;
    if (!window.matchMedia('(max-width: 767px)').matches) {
        // Clear mobile wrappers if any
        if (container.dataset.routineMobileInit === 'true') {
            container.querySelectorAll('.routine-mobile-card').forEach(wrapper => {
                const inner = wrapper.querySelector('.exercise-routine-card');
                if (inner) container.insertBefore(inner, wrapper);
                wrapper.remove();
            });
            const nav = document.getElementById('routine-exercise-mobile-nav');
            if (nav) nav.remove();
            delete container.dataset.routineMobileInit;
        }
        return;
    }
    refreshMobileRoutineUI();
}

function refreshMobileRoutineUI(preferredIndex = null) {
    const container = document.getElementById('routine-exercises-container');
    if (!container) return;

    // Wrap cards if not already
    const cards = Array.from(container.querySelectorAll(':scope > .exercise-routine-card'));
    cards.forEach((card, idx) => {
        if (!card.parentElement.classList.contains('routine-mobile-card')) {
            const wrapper = document.createElement('div');
            wrapper.className = 'exercise-card routine-mobile-card d-none';
            wrapper.dataset.exerciseIndex = String(idx);
            container.insertBefore(wrapper, card);
            wrapper.appendChild(card);
        }
    });

    const wrappers = Array.from(container.querySelectorAll(':scope > .routine-mobile-card'));
    wrappers.forEach((w, i) => w.dataset.exerciseIndex = String(i));

    // Build nav if missing
    if (!document.getElementById('routine-exercise-mobile-nav')) {
        const nav = document.createElement('div');
        nav.id = 'routine-exercise-mobile-nav';
        nav.className = 'exercise-navigation-bottom d-flex justify-content-between align-items-center mt-3';
        nav.innerHTML = `
            <button class="btn btn-outline-secondary" id="routine-prev-exercise"><i class="fas fa-chevron-left"></i></button>
            <div class="d-flex align-items-center gap-3">
                <div class="exercise-indicators" id="routine-exercise-indicators"></div>
                <div class="exercise-counter"><span id="routine-current-exercise-num">1</span>/<span id="routine-total-exercises-num">${wrappers.length}</span></div>
            </div>
            <button class="btn btn-outline-secondary" id="routine-next-exercise"><i class="fas fa-chevron-right"></i></button>
        `;
        container.parentElement.appendChild(nav);

        nav.querySelector('#routine-prev-exercise').addEventListener('click', () => stepRoutineMobile(-1));
        nav.querySelector('#routine-next-exercise').addEventListener('click', () => stepRoutineMobile(1));
    }

    // Rebuild indicators
    const indicators = document.getElementById('routine-exercise-indicators');
    if (indicators) {
        indicators.innerHTML = '';
        wrappers.forEach((_, i) => {
            const dot = document.createElement('div');
            dot.className = 'indicator';
            dot.dataset.index = String(i);
            dot.addEventListener('click', () => showRoutineMobileIndex(i));
            indicators.appendChild(dot);
        });
    }

    const totalSpan = document.getElementById('routine-total-exercises-num');
    if (totalSpan) totalSpan.textContent = String(wrappers.length);

    let target = 0;
    const current = Number(container.dataset.routineCurrentIndex || '0');
    if (preferredIndex !== null && Number.isFinite(preferredIndex)) {
        target = Math.max(0, Math.min(preferredIndex, wrappers.length - 1));
    } else if (current >= 0 && current < wrappers.length) {
        target = current;
    }
    showRoutineMobileIndex(target);
    container.dataset.routineMobileInit = 'true';
}

function showRoutineMobileIndex(idx) {
    const container = document.getElementById('routine-exercises-container');
    if (!container) return;
    const wrappers = Array.from(container.querySelectorAll(':scope > .routine-mobile-card'));
    if (!wrappers.length) return;
    const clamped = Math.max(0, Math.min(idx, wrappers.length - 1));
    wrappers.forEach(w => w.classList.add('d-none'));
    wrappers[clamped].classList.remove('d-none');
    container.dataset.routineCurrentIndex = String(clamped);

    const prev = document.getElementById('routine-prev-exercise');
    const next = document.getElementById('routine-next-exercise');
    const curSpan = document.getElementById('routine-current-exercise-num');
    document.querySelectorAll('#routine-exercise-indicators .indicator').forEach((dot, i) => dot.classList.toggle('active', i === clamped));
    if (prev) prev.disabled = clamped === 0;
    if (next) next.disabled = clamped === wrappers.length - 1;
    if (curSpan) curSpan.textContent = String(clamped + 1);
}

function stepRoutineMobile(delta) {
    const container = document.getElementById('routine-exercises-container');
    if (!container) return;
    const current = Number(container.dataset.routineCurrentIndex || '0');
    showRoutineMobileIndex(current + delta);
}




