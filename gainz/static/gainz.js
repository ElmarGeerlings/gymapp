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
                    <span>${routine.name}</span>
                    <div class="d-flex align-items-center">
                        <a href="/routines/${routine.routine_id || routine.id}/" class="text-white me-2" draggable="false" target="_blank" rel="noopener" title="Open routine in a new tab">
                            <i class="fas fa-external-link-alt"></i>
                        </a>
                        <button type="button" class="btn-close btn-close-white btn-sm" aria-label="Remove"></button>
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
                        <span>${routine.name}</span>
                        <div class="d-flex align-items-center">
                            <a href="/routines/${routine.routine_id}/" class="text-white me-2" draggable="false" target="_blank" rel="noopener" title="Open routine in a new tab">
                                <i class="fas fa-external-link-alt"></i>
                            </a>
                            <button type="button" class="btn-close btn-close-white btn-sm" aria-label="Remove"></button>
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
async function updateSet(event) {
    const element = event.target;
    const setId = element.dataset.setId;
    const field = element.dataset.field;
    
    if (!setId || !field) {
        console.error('Missing data-set-id or data-field on element');
        return;
    }
    
    let value = element.value;
    // Handle checkbox for is_warmup field
    if (field === 'is_warmup') {
        value = element.checked;
    }
    
    const url = `/api/workouts/sets/${setId}/`;
    const data = { [field]: value };
    
    const response = await httpRequestHelper(url, 'PATCH', data);
    
    if (response.ok) {
        send_toast('Set updated', 'success');
        // Update data attributes if reps or weight changed
        if (field === 'reps' || field === 'weight') {
            const row = element.closest('.set-row');
            if (row) {
                row.dataset[field] = value;
            }
        }
    } else {
        send_toast(response.data?.detail || 'Error updating set', 'danger');
        // Optionally revert the value
        // element.value = element.dataset.originalValue;
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
                                <th width="100">Reps</th>
                                <th width="120">Weight (kg)</th>
                                <th width="80">Warmup</th>
                                <th width="60">Done</th>
                                <th width="40"></th>
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
                <td class="text-center">
                    <button type="button" class="btn btn-sm btn-outline-success mark-set-btn"
                            data-function="click->toggleSetCompletion"
                            data-set-id="${setData.id}"
                            data-exercise-id="${exerciseId}"
                            data-completed="${setData.is_completed ? 'true' : 'false'}"
                            title="Toggle completion">
                        <i class="fas fa-check"></i>
                    </button>
                </td>
                <td class="text-center">
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
    // Add touch support for mobile
    addTouchDragSupport(cardElement, 'routine-exercises');
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
    const rpeToggleForDebug = document.getElementById('toggle-rpe-visibility');
    if (rpeToggleForDebug) {
        // This log confirmed the initial state was correct, so we can remove it or keep for future.
        // console.log('[gainz.js] initializeRoutineForm: Initial state of RPE checkbox (id: toggle-rpe-visibility) IS CHECKED:', rpeToggleForDebug.checked);
    }

    // Enable drag and drop functionality
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

    updateRoutineExerciseOrderNumbers(); // Reintroducing this first

    // The main call to update visibility based on checkbox states
    window.updateSetRowFieldVisibility();
}

// Initialization on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOMContentLoaded event fired from gainz.js');

    // This block correctly wires up the program form buttons.
    if (document.getElementById('program-routines-container')) {
        // initializeProgramForm(); // Removed as per edit hint
    }

    // New logic for program form scheduling type
    const weeklyRadio = document.getElementById('scheduling-weekly');
    const sequentialRadio = document.getElementById('scheduling-sequential');
    if (weeklyRadio && sequentialRadio) {
        // Save the initial state for cancel functionality
        originalProgramState = saveProgramState();
        
        // Set initial visibility based on current selection
        const weeklyContainer = document.getElementById('weekly-schedule-container');
        const sequentialContainer = document.getElementById('sequential-schedule-container');
        const sequentialAdder = document.getElementById('sequential-routine-adder');
        
        if (weeklyRadio.checked) {
            weeklyContainer.style.display = 'block';
            sequentialContainer.style.display = 'none';
            sequentialAdder.style.display = 'none';
            initializeProgramRoutinesDragDrop();
        } else {
            weeklyContainer.style.display = 'none';
            sequentialContainer.style.display = 'block';
            sequentialAdder.style.display = 'block';
        }
        
        // Add event listeners for changes
        weeklyRadio.addEventListener('change', toggleScheduleType);
        sequentialRadio.addEventListener('change', toggleScheduleType);
        
        // Handle cancel button to restore original state
        const cancelButton = document.querySelector('a.btn-secondary[href*="program"]');
        if (cancelButton && cancelButton.textContent.includes('Cancel')) {
            cancelButton.addEventListener('click', async function(e) {
                e.preventDefault();
                const href = this.href;
                
                if (originalProgramState) {
                    // Get program ID from the form or URL
                    const programForm = document.querySelector('form[action*="/programs/"]');
                    let programId = null;
                    
                    if (programForm) {
                        const actionUrl = programForm.getAttribute('action');
                        const match = actionUrl.match(/\/programs\/(\d+)\//);
                        if (match) {
                            programId = match[1];
                        }
                    }
                    
                    if (programId) {
                        // Restore state in database
                        const restored = await restoreProgramStateViaAPI(programId, originalProgramState);
                        if (restored) {
                            window.location.href = href;
                        } else {
                            // If API restore fails, still navigate away but warn user
                            if (confirm('Failed to restore original state. Continue anyway?')) {
                                window.location.href = href;
                            }
                        }
                    } else {
                        // No program ID means this is a new program, just navigate away
                        window.location.href = href;
                    }
                } else {
                    window.location.href = href;
                }
            });
        }
    }

    const weeklyPlanner = document.querySelector('.weekly-planner');
    if (weeklyPlanner) {
        weeklyPlanner.addEventListener('change', function(event) {
            if (event.target.classList.contains('add-routine-to-day-select')) {
                handleAddRoutineToDay(event);
            }
        });
        weeklyPlanner.addEventListener('click', function(event) {
            if (event.target.classList.contains('btn-close')) {
                const chip = event.target.closest('.routine-chip');
                if (chip) {
                    handleRemoveRoutineFromDay(chip);
                }
            }
        });
    }

    document.querySelectorAll('[data-function]').forEach(element => {
        const attrNode = element.getAttributeNode('data-function');
        if (attrNode) {
            handle_attribute(element, attrNode);
        } else {
            console.warn('Element found by querySelectorAll but getAttributeNode("data-function") is null for:', element);
        }
    });

    if (document.getElementById('routineForm')) {
        initializeRoutineForm();
    }

    // Initialize workout exercises drag and drop
    if (document.getElementById('workout-exercises-container')) {
        initializeWorkoutExercisesDragDrop();
    }

    // Initialize touch drag support for all existing draggable elements
    initializeTouchDragSupport();

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
    const isInitializationCall = !event;
    if (isInitializationCall) {
        console.log('[gainz.js] updateSetRowFieldVisibility: Called during page initialization.');
    }

    const rpeToggle = document.getElementById('toggle-rpe-visibility');
    const restToggle = document.getElementById('toggle-rest-time-visibility');
    const notesToggle = document.getElementById('toggle-notes-visibility');

    // Log the state of the checkbox as seen by THIS function, especially during initialization
    if (rpeToggle && isInitializationCall) {
        console.log('[gainz.js] updateSetRowFieldVisibility (init call): RPE checkbox (id: toggle-rpe-visibility) IS CHECKED:', rpeToggle.checked);
    }

    const showRPE = rpeToggle?.checked;
    const showRestTime = restToggle?.checked;
    const showNotes = notesToggle?.checked;

    if (isInitializationCall) {
        console.log(`[gainz.js] updateSetRowFieldVisibility (init call): showRPE=${showRPE}, showRestTime=${showRestTime}, showNotes=${showNotes}`);
    }

    // Save states to Redis via backend API call
    if (event && event.target) { // Check if called by an event on a specific toggle
        const checkbox = event.target;
        let preferenceKeyForBackend;
        switch (checkbox.id) {
            case 'toggle-rpe-visibility':
                preferenceKeyForBackend = 'routineForm.showRPE';
                break;
            case 'toggle-rest-time-visibility':
                preferenceKeyForBackend = 'routineForm.showRestTime';
                break;
            case 'toggle-notes-visibility':
                preferenceKeyForBackend = 'routineForm.showNotes';
                break;
            default:
                console.error(`[gainz.js] Unknown checkbox ID for preference saving: ${checkbox.id}`);
                // Optionally, you might want to return or skip saving if the ID is unknown.
                // For now, it will proceed and likely result in an unhandled preferenceKeyForBackend.
                // Consider adding: return;
        }

        // Only proceed if preferenceKeyForBackend was successfully determined
        if (preferenceKeyForBackend) {
            const preferenceValue = checkbox.checked;
            console.log(`[gainz.js] Attempting to save preference: Key='${preferenceKeyForBackend}', Value=${preferenceValue}`);
            await httpRequestHelper('/ajax/update_user_preferences/', 'POST', {
                preference_key: preferenceKeyForBackend, // This will now be correct
                preference_value: preferenceValue
            }).then(response => {
                console.log('[gainz.js] Save preference response:', response);
                if (!response.ok) {
                    send_toast(response.data?.message || 'Failed to save preference.', 'danger', 'Preference Error');
                }
            }).catch(error => {
                console.error('[gainz.js] Save preference error:', error);
                send_toast('Error communicating with server to save preference.', 'danger', 'Network Error');
            });
        } else if (checkbox.id) { // Log if key was not determined but it was an attempt to save
             console.warn(`[gainz.js] Did not save preference for unknown checkbox ID: ${checkbox.id}`);
        }
    }
    // Removed localStorage saving logic
    // if(rpeToggle) localStorage.setItem('gainz.routineForm.showRPE', showRPE);
    // if(restToggle) localStorage.setItem('gainz.routineForm.showRestTime', showRestTime);
    // if(notesToggle) localStorage.setItem('gainz.routineForm.showNotes', showNotes);

    document.querySelectorAll('.set-row').forEach(setRow => {
        const rpeField = setRow.querySelector('.rpe-field');
        const restTimeField = setRow.querySelector('.rest-time-field');
        const notesField = setRow.querySelector('.notes-field');

        if (rpeField) {
            const newRpeDisplay = showRPE ? 'block' : 'none';
            if (isInitializationCall) {
                console.log(`[gainz.js] updateSetRowFieldVisibility (init call): Setting .rpe-field display to: ${newRpeDisplay}`);
            }
            rpeField.style.display = newRpeDisplay;
        }
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
                newName = newName.replace(/routine_exercise\[(?:\|__EXERCISE_INDEX__\|)\]/g, `routine_exercise[${exerciseIndex}]`);
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
    chip.addEventListener('dragstart', handleProgramRoutineDragStart);
    chip.addEventListener('dragend', handleProgramRoutineDragEnd);
    // Add touch support for mobile
    addTouchDragSupport(chip, 'program-routines');
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
        <span>${routineName}</span>
        <div class="d-flex align-items-center">
            <a href="/routines/${routineId}/" class="text-white me-2" draggable="false" target="_blank" rel="noopener" title="Open routine in a new tab">
                <i class="fas fa-external-link-alt"></i>
            </a>
            <button type="button" class="btn-close btn-close-white btn-sm" aria-label="Remove"></button>
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
