/**
 * Timer Module for Gainz Workout App
 *
 * This module contains all timer-related functionality including:
 * - WorkoutTimer class for rest timer management
 * - Timer utility functions for user interactions
 * - Timer display management
 * - Auto-start timer integration
 * - Timer preferences form handling
 *
 * Dependencies:
 * - httpRequestHelper (from gainz.js)
 * - send_toast (from gainz.js)
 * - displayFormErrors (from gainz.js)
 */

// ============================================================================
// WORKOUT TIMER CLASS DEFINITION
// ============================================================================

/**
 * WorkoutTimer class for handling workout rest timers
 * Provides functionality for starting, pausing, stopping, and managing workout rest periods
 */
class WorkoutTimer {
    constructor() {
        this.currentTimer = null;
        this.startTime = null;
        this.duration = 0;
        this.remaining = 0;
        this.isRunning = false;
        this.isPaused = false;
        this.intervalId = null;
        this.callbacks = {
            onTick: null,
            onComplete: null,
            onStart: null,
            onPause: null,
            onStop: null,
            onReset: null
        };

        // Load timer state from localStorage on initialization
        this.loadFromStorage();

        // Handle page visibility changes for tab switching
        this.setupVisibilityHandling();
    }

    /**
     * Format seconds to MM:SS display format
     * @param {number} seconds - Number of seconds to format
     * @returns {string} Formatted time string (MM:SS)
     */
    formatTime(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Start timer with specified duration in seconds
     * @param {number|null} durationSeconds - Timer duration in seconds
     * @returns {boolean} True if timer started successfully
     */
    start(durationSeconds = null) {
        if (durationSeconds !== null) {
            this.duration = durationSeconds;
            this.remaining = durationSeconds;
        }

        if (this.remaining <= 0) return false;

        this.startTime = Date.now() - ((this.duration - this.remaining) * 1000);
        this.isRunning = true;
        this.isPaused = false;

        this.intervalId = setInterval(() => {
            this.tick();
        }, 1000);

        this.saveToStorage();

        if (this.callbacks.onStart) {
            this.callbacks.onStart(this.remaining);
        }

        return true;
    }

    /**
     * Pause the running timer
     * @returns {boolean} True if timer paused successfully
     */
    pause() {
        if (!this.isRunning || this.isPaused) return false;

        this.isPaused = true;
        this.isRunning = false;

        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        this.saveToStorage();

        if (this.callbacks.onPause) {
            this.callbacks.onPause(this.remaining);
        }

        return true;
    }

    /**
     * Resume paused timer
     * @returns {boolean} True if timer resumed successfully
     */
    resume() {
        if (!this.isPaused || this.isRunning) return false;

        this.startTime = Date.now() - ((this.duration - this.remaining) * 1000);
        this.isRunning = true;
        this.isPaused = false;

        this.intervalId = setInterval(() => {
            this.tick();
        }, 1000);

        this.saveToStorage();

        if (this.callbacks.onStart) {
            this.callbacks.onStart(this.remaining);
        }

        return true;
    }

    /**
     * Stop the timer completely
     * @returns {boolean} True if timer stopped successfully
     */
    stop() {
        this.isRunning = false;
        this.isPaused = false;

        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        this.clearStorage();

        if (this.callbacks.onStop) {
            this.callbacks.onStop();
        }

        return true;
    }

    /**
     * Reset timer to initial state
     * @returns {boolean} True if timer reset successfully
     */
    reset() {
        this.stop();
        this.remaining = this.duration;
        this.startTime = null;

        if (this.callbacks.onReset) {
            this.callbacks.onReset(this.remaining);
        }

        return true;
    }

    /**
     * Add time to current timer (can be negative to subtract)
     * @param {number} seconds - Seconds to add/subtract
     * @returns {number} New remaining time in seconds
     */
    adjustTime(seconds) {
        this.remaining = Math.max(0, this.remaining + seconds);
        this.duration = Math.max(0, this.duration + seconds);

        if (this.isRunning) {
            this.startTime = Date.now() - ((this.duration - this.remaining) * 1000);
        }

        this.saveToStorage();

        if (this.callbacks.onTick) {
            this.callbacks.onTick(this.remaining);
        }

        return this.remaining;
    }

    /**
     * Timer tick handler - called every second
     */
    tick() {
        if (!this.isRunning || this.isPaused) return;

        const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
        this.remaining = Math.max(0, this.duration - elapsed);

        if (this.callbacks.onTick) {
            this.callbacks.onTick(this.remaining);
        }

        if (this.remaining <= 0) {
            this.complete();
        } else {
            this.saveToStorage();
        }
    }

    /**
     * Timer completion handler
     */
    complete() {
        this.isRunning = false;
        this.isPaused = false;
        this.remaining = 0;

        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }

        this.clearStorage();
        this.playNotification();

        if (this.callbacks.onComplete) {
            this.callbacks.onComplete();
        }
    }

    /**
     * Play notification sound/alert when timer completes
     */
    playNotification() {
        this.showBrowserNotification();
    }

    /**
     * Show browser notification when timer completes
     */
    showBrowserNotification() {
        if (!('Notification' in window)) {
            return;
        }

        if (Notification.permission === 'granted') {
            this.dispatchTimerNotification();
        } else if (Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                if (permission === 'granted') {
                    this.dispatchTimerNotification();
                }
            });
        }
    }

    dispatchTimerNotification() {
        const title = 'Rest timer complete';
        const options = {
            body: 'Time to start your next set.',
            icon: '/static/favicon.ico',
            tag: 'gainz-timer'
        };

        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
            navigator.serviceWorker.ready.then(reg => {
                reg.showNotification(title, options).catch(() => {
                    new Notification(title, options);
                });
            }).catch(() => {
                new Notification(title, options);
            });
        } else {
            new Notification(title, options);
        }
    }

    /**
     * Set callback functions for timer events
     * @param {string} event - Event name (tick, start, pause, stop, reset, complete)
     * @param {function} callback - Callback function to execute
     */
    on(event, callback) {
        if (this.callbacks.hasOwnProperty(`on${event.charAt(0).toUpperCase() + event.slice(1)}`)) {
            this.callbacks[`on${event.charAt(0).toUpperCase() + event.slice(1)}`] = callback;
        }
    }

    /**
     * Get current timer state
     * @returns {object} Current timer state object
     */
    getState() {
        return {
            duration: this.duration,
            remaining: this.remaining,
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            formattedTime: this.formatTime(this.remaining)
        };
    }

    /**
     * Save timer state to localStorage for persistence
     */
    saveToStorage() {
        const state = {
            duration: this.duration,
            remaining: this.remaining,
            isRunning: this.isRunning,
            isPaused: this.isPaused,
            startTime: this.startTime,
            timestamp: Date.now()
        };

        try {
            localStorage.setItem('gainz.workoutTimer', JSON.stringify(state));
        } catch (e) {
            console.warn('Could not save timer state to localStorage:', e);
        }
    }

    /**
     * Load timer state from localStorage on page load
     */
    loadFromStorage() {
        try {
            const saved = localStorage.getItem('gainz.workoutTimer');
            if (!saved) return;

            const state = JSON.parse(saved);
            const now = Date.now();
            const timeSinceLastUpdate = (now - state.timestamp) / 1000;

            this.duration = state.duration;
            this.startTime = state.startTime;

            if (state.isRunning && !state.isPaused) {
                // Calculate how much time has passed since last save
                const elapsed = Math.floor((now - state.startTime) / 1000);
                this.remaining = Math.max(0, state.duration - elapsed);

                if (this.remaining > 0) {
                    this.isRunning = true;
                    this.isPaused = false;
                    this.intervalId = setInterval(() => {
                        this.tick();
                    }, 1000);
                } else {
                    // Timer completed while tab was inactive
                    this.complete();
                }
            } else {
                this.remaining = state.remaining;
                this.isRunning = false;
                this.isPaused = state.isPaused;
            }
        } catch (e) {
            console.warn('Could not load timer state from localStorage:', e);
            this.clearStorage();
        }
    }

    /**
     * Clear timer state from localStorage
     */
    clearStorage() {
        try {
            localStorage.removeItem('gainz.workoutTimer');
        } catch (e) {
            console.warn('Could not clear timer state from localStorage:', e);
        }
    }

    /**
     * Handle page visibility changes for tab switching
     */
    setupVisibilityHandling() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.isRunning) {
                // Page became visible again, recalculate remaining time
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                this.remaining = Math.max(0, this.duration - elapsed);

                if (this.remaining <= 0) {
                    this.complete();
                } else if (this.callbacks.onTick) {
                    this.callbacks.onTick(this.remaining);
                }
            }
        });

        // Handle page unload
        window.addEventListener('beforeunload', () => {
            if (this.isRunning || this.isPaused) {
                this.saveToStorage();
            }
        });
    }
}

// ============================================================================
// TIMER MANAGER AND UTILITY FUNCTIONS
// ============================================================================

/**
 * TimerManager class to manage multiple exercise-specific timer instances
 * Ensures only one timer can be active at a time across all exercises
 */
class TimerManager {
    constructor() {
        this.timers = new Map(); // exerciseId -> WorkoutTimer instance
        this.activeTimerId = null; // Currently active timer exercise ID
    }

    /**
     * Get or create timer instance for specific exercise
     * @param {string} exerciseId - Exercise ID
     * @returns {WorkoutTimer} Timer instance for the exercise
     */
    getTimer(exerciseId) {
        if (!this.timers.has(exerciseId)) {
            const timer = new WorkoutTimer();

            // Override storage methods to be exercise-specific
            const originalSaveToStorage = timer.saveToStorage.bind(timer);
            const originalLoadFromStorage = timer.loadFromStorage.bind(timer);
            const originalClearStorage = timer.clearStorage.bind(timer);

            timer.saveToStorage = () => {
                const state = {
                    duration: timer.duration,
                    remaining: timer.remaining,
                    isRunning: timer.isRunning,
                    isPaused: timer.isPaused,
                    startTime: timer.startTime,
                    timestamp: Date.now()
                };

                try {
                    localStorage.setItem(`gainz.workoutTimer.${exerciseId}`, JSON.stringify(state));
                } catch (e) {
                    console.warn(`Could not save timer state for exercise ${exerciseId}:`, e);
                }
            };

            timer.loadFromStorage = () => {
                try {
                    const saved = localStorage.getItem(`gainz.workoutTimer.${exerciseId}`);
                    if (!saved) return;

                    const state = JSON.parse(saved);
                    const now = Date.now();

                    timer.duration = state.duration;
                    timer.startTime = state.startTime;

                    if (state.isRunning && !state.isPaused) {
                        // Calculate how much time has passed since last save
                        const elapsed = Math.floor((now - state.startTime) / 1000);
                        timer.remaining = Math.max(0, state.duration - elapsed);

                        if (timer.remaining > 0) {
                            timer.isRunning = true;
                            timer.isPaused = false;
                            this.activeTimerId = exerciseId;
                            timer.intervalId = setInterval(() => {
                                timer.tick();
                            }, 1000);
                        } else {
                            // Timer completed while tab was inactive
                            timer.complete();
                        }
                    } else {
                        timer.remaining = state.remaining;
                        timer.isRunning = false;
                        timer.isPaused = state.isPaused;
                        if (state.isPaused) {
                            this.activeTimerId = exerciseId;
                        }
                    }
                } catch (e) {
                    console.warn(`Could not load timer state for exercise ${exerciseId}:`, e);
                    timer.clearStorage();
                }
            };

            timer.clearStorage = () => {
                try {
                    localStorage.removeItem(`gainz.workoutTimer.${exerciseId}`);
                } catch (e) {
                    console.warn(`Could not clear timer state for exercise ${exerciseId}:`, e);
                }
            };

            // Load saved state for this exercise
            timer.loadFromStorage();

            // Set up event callbacks for this timer
            this.setupTimerCallbacks(timer, exerciseId);

            this.timers.set(exerciseId, timer);
        }

        return this.timers.get(exerciseId);
    }

    /**
     * Start timer for specific exercise, stopping any other active timers
     * @param {string} exerciseId - Exercise ID
     * @param {number} durationSeconds - Timer duration in seconds
     * @returns {boolean} True if timer started successfully
     */
    async startTimer(exerciseId, durationSeconds = null) {
        // Stop any currently active timer and reset its display
        if (this.activeTimerId && this.activeTimerId !== exerciseId) {
            const oldTimerId = this.activeTimerId; // Save the ID before stop() clears it
            const activeTimer = this.timers.get(oldTimerId);
            if (activeTimer) {
                activeTimer.stop();
                // Reset the old timer's display to its actual default duration
                const oldDisplay = document.querySelector(`[data-timer-display][data-exercise-id="${oldTimerId}"]`);
                if (oldDisplay) {
                    try {
                        // Get the actual default duration from user settings (not hardcoded values)
                        const realDuration = await this.getDefaultDurationForExercise(oldTimerId);
                        activeTimer.duration = realDuration;
                        activeTimer.remaining = realDuration;
                        oldDisplay.textContent = activeTimer.formatTime(realDuration);
                    } catch (error) {
                        console.error(`Failed to get user settings for timer ${oldTimerId}:`, error);
                    }
                }
            }
        }

        const timer = this.getTimer(exerciseId);

        // If timer is already running for this exercise, stop it first to allow restart
        if (timer.isRunning) {
            timer.stop();
        }

        const result = timer.start(durationSeconds);

        if (result) {
            this.activeTimerId = exerciseId;
            this.updateTimerDisplays();
        }

        return result;
    }

    /**
     * Pause/resume timer for specific exercise
     * @param {string} exerciseId - Exercise ID
     * @returns {boolean} True if timer paused/resumed successfully
     */
    pauseTimer(exerciseId) {
        const timer = this.getTimer(exerciseId);
        let result;

        if (timer.isPaused) {
            result = timer.resume();
            if (result) {
                this.activeTimerId = exerciseId;
            }
        } else {
            result = timer.pause();
        }

        if (result) {
            this.updateTimerDisplays();
        }

        return result;
    }

    /**
     * Stop timer for specific exercise
     * @param {string} exerciseId - Exercise ID
     * @returns {boolean} True if timer stopped successfully
     */
    stopTimer(exerciseId) {
        const timer = this.getTimer(exerciseId);
        const result = timer.stop();

        if (result && this.activeTimerId === exerciseId) {
            this.activeTimerId = null;
        }

        // Reset timer display to default duration
        const display = document.querySelector(`[data-timer-display][data-exercise-id="${exerciseId}"]`);
        if (display) {
            const timer = this.getTimer(exerciseId);

            // First check if mobile view already set a default duration
            const startBtn = document.querySelector(`[data-function*="startTimer"][data-exercise-id="${exerciseId}"]`);
            const storedDuration = startBtn?.dataset?.duration;

            if (storedDuration) {
                // Use the duration that mobile view already determined
                const defaultDuration = parseInt(storedDuration);
                timer.duration = defaultDuration;
                timer.remaining = defaultDuration;
                display.textContent = timer.formatTime(defaultDuration);
            } else {
                // Fallback to fetching default duration (desktop view)
                this.getDefaultDurationForExercise(exerciseId).then(defaultDuration => {
                    timer.duration = defaultDuration;
                    timer.remaining = defaultDuration;
                    display.textContent = timer.formatTime(defaultDuration);
                }).catch(() => {
                    // Fallback to current duration
                    display.textContent = timer.formatTime(timer.duration);
                });
            }
        }
        this.updateTimerDisplays();

        return result;
    }

    /**
     * Reset timer for specific exercise
     * @param {string} exerciseId - Exercise ID
     * @returns {boolean} True if timer reset successfully
     */
    resetTimer(exerciseId) {
        const timer = this.getTimer(exerciseId);
        const result = timer.reset();

        if (result && this.activeTimerId === exerciseId) {
            this.activeTimerId = null;
        }

        // Reset timer display to default duration
        const display = document.querySelector(`[data-timer-display][data-exercise-id="${exerciseId}"]`);
        if (display) {
            const timer = this.getTimer(exerciseId);

            // First check if mobile view already set a default duration
            const startBtn = document.querySelector(`[data-function*="startTimer"][data-exercise-id="${exerciseId}"]`);
            const storedDuration = startBtn?.dataset?.duration;

            if (storedDuration) {
                // Use the duration that mobile view already determined
                const defaultDuration = parseInt(storedDuration);
                timer.duration = defaultDuration;
                timer.remaining = defaultDuration;
                display.textContent = timer.formatTime(defaultDuration);
            } else {
                // Fallback to fetching default duration (desktop view)
                this.getDefaultDurationForExercise(exerciseId).then(defaultDuration => {
                    timer.duration = defaultDuration;
                    timer.remaining = defaultDuration;
                    display.textContent = timer.formatTime(defaultDuration);
                }).catch(() => {
                    // Fallback to current duration
                    display.textContent = timer.formatTime(timer.duration);
                });
            }
        }
        this.updateTimerDisplays();

        return result;
    }

    /**
     * Adjust timer for specific exercise
     * @param {string} exerciseId - Exercise ID
     * @param {number} seconds - Seconds to add/subtract
     * @returns {number} New remaining time in seconds
     */
    adjustTimer(exerciseId, seconds) {
        const timer = this.getTimer(exerciseId);
        const newRemaining = timer.adjustTime(seconds);
        this.updateTimerDisplays();
        return newRemaining;
    }

    /**
     * Get default duration for a specific exercise
     * @param {string} exerciseId - Exercise ID
     * @returns {Promise<number>} Default duration in seconds
     */
    async getDefaultDurationForExercise(exerciseId) {
        try {
            // Get exercise type from DOM
            const exerciseCard = document.querySelector(`[data-exercise-id="${exerciseId}"]`);
            // First check if exercise card has the type directly (mobile view)
            let exerciseType = exerciseCard?.dataset.exerciseType;
            if (!exerciseType) {
                // Fall back to checking category container (desktop view)
                const categoryContainer = exerciseCard?.closest('.exercise-category-container');
                exerciseType = categoryContainer?.dataset.category || 'accessory';
            }

            // Fetch user preferences
            const preferencesResponse = await httpRequestHelper('/api/timer-preferences/', 'GET');
            if (preferencesResponse.ok) {
                const preferences = preferencesResponse.data;
                return await determineTimerDuration(exerciseId, preferences);
            } else {
                console.error('Failed to fetch user timer preferences - API returned error');
                throw new Error('Unable to fetch user timer preferences');
            }
        } catch (error) {
            console.error('Error getting default duration:', error);
            throw error; // Don't use hardcoded fallbacks that ignore user settings
        }
    }

    /**
     * Static method to format time without instance
     * @param {number} seconds - Seconds to format
     * @returns {string} Formatted time string
     */
    formatTimeStatic(seconds) {
        const minutes = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Reset timer display to default duration for specific exercise
     * @param {string} exerciseId - Exercise ID
     */
    async resetTimerDisplay(exerciseId) {
        try {
            const timerDisplay = document.querySelector(`[data-timer-display][data-exercise-id="${exerciseId}"]`);
            if (timerDisplay) {
                const defaultDuration = await this.getDefaultDurationForExercise(exerciseId);
                const timer = this.getTimer(exerciseId);

                // Update timer instance
                timer.duration = defaultDuration;
                timer.remaining = defaultDuration;

                const formattedDefault = timer.formatTime(defaultDuration);
                timerDisplay.textContent = formattedDefault;
            }
        } catch (error) {
            console.warn('Error resetting timer display:', error);
            const timerDisplay = document.querySelector(`[data-timer-display][data-exercise-id="${exerciseId}"]`);
            if (timerDisplay) {
                timerDisplay.textContent = '01:30'; // Fallback
            }
        }
    }

    /**
     * Update all timer displays on the page
     */
    updateTimerDisplays() {
        // Update timer displays for all exercises
        document.querySelectorAll('[data-timer-display]').forEach(async element => {
            const exerciseId = element.dataset.exerciseId;
            if (exerciseId) {
                const timer = this.timers.get(exerciseId);
                if (timer) {
                    const state = timer.getState();
                    element.textContent = state.formattedTime;
                    // Reflect running/paused state via classes for styling and mobile checks
                    element.classList.toggle('active', state.isRunning && !state.isPaused);
                    element.classList.toggle('paused', !!state.isPaused);

                    // Update timer control buttons for this exercise
                    this.updateTimerControls(exerciseId, state);
                } else {
                    // For mobile view, don't override what's already displayed
                    const isMobileView = document.querySelector('#exercise-card-container');
                    if (!isMobileView) {
                        // Show default duration instead of 00:00 (desktop only)
                        try {
                            const defaultDuration = await this.getDefaultDurationForExercise(exerciseId);
                            const formattedDefault = this.formatTimeStatic(defaultDuration);
                            element.textContent = formattedDefault;
                        } catch (error) {
                            element.textContent = '01:30'; // Fallback to 90 seconds
                        }
                    }
                    // Ensure classes reflect idle state
                    element.classList.remove('active');
                    element.classList.remove('paused');

                    this.updateTimerControls(exerciseId, {
                        isRunning: false,
                        isPaused: false
                    });
                }
            }
        });
    }

    /**
     * Update timer control buttons for specific exercise
     * @param {string} exerciseId - Exercise ID
     * @param {object} state - Timer state
     */
    updateTimerControls(exerciseId, state) {
        // Update start buttons
        document.querySelectorAll(`[data-function*="startTimer"][data-exercise-id="${exerciseId}"]`).forEach(element => {
            element.disabled = state.isRunning && !state.isPaused;
        });

        // Update pause buttons
        document.querySelectorAll(`[data-function*="pauseTimer"][data-exercise-id="${exerciseId}"]`).forEach(element => {
            element.disabled = !state.isRunning && !state.isPaused;
            const spanElement = element.querySelector('span');
            if (spanElement) {
                spanElement.textContent = state.isPaused ? 'Resume' : 'Pause';
            }
        });

        // Update stop buttons
        document.querySelectorAll(`[data-function*="stopTimer"][data-exercise-id="${exerciseId}"], [data-function*="resetTimer"][data-exercise-id="${exerciseId}"]`).forEach(element => {
            element.disabled = !state.isRunning && !state.isPaused;
        });
    }

    /**
     * Set up callbacks for a specific timer
     */
    setupTimerCallbacks(timer, exerciseId) {
        // Only set up callbacks once
        if (timer._callbacksSetup) {
            return;
        }

        const updateDisplays = () => this.updateTimerDisplays();

        timer.on('tick', updateDisplays);
        timer.on('start', updateDisplays);
        timer.on('pause', updateDisplays);
        timer.on('stop', () => {
            if (this.activeTimerId === exerciseId) {
                this.activeTimerId = null;
            }
            updateDisplays();
        });
        timer.on('reset', () => {
            if (this.activeTimerId === exerciseId) {
                this.activeTimerId = null;
            }
            updateDisplays();
        });
        timer.on('complete', () => {
            if (this.activeTimerId === exerciseId) {
                this.activeTimerId = null;
            }
            updateDisplays();

            if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
                try {
                    window.dispatchEvent(new CustomEvent('timer:complete', {
                        detail: { exerciseId }
                    }));
                } catch (e) {
                    console.warn('Unable to dispatch timer completion event:', e);
                }
            }

            // Show completion message for this specific exercise
            const timerMessages = document.querySelectorAll(`[data-timer-message][data-exercise-id="${exerciseId}"]`);
            timerMessages.forEach(element => {
                element.textContent = 'Timer Complete!';
                element.classList.add('timer-complete');
                setTimeout(() => {
                    element.classList.remove('timer-complete');
                    element.textContent = '';
                }, 5000);
            });
        });

        timer._callbacksSetup = true;
    }
}

/**
 * Global timer manager instance
 */
window.timerManager = new TimerManager();

window.timerManager.requestNotificationPermission = function() {
    if (!('Notification' in window)) {
        return Promise.resolve('unsupported');
    }

    if (Notification.permission === 'granted' || Notification.permission === 'denied') {
        return Promise.resolve(Notification.permission);
    }

    return Notification.requestPermission();
};

window.timerManager.ensureNotificationPermission = function() {
    this.requestNotificationPermission().catch(() => {});
};

/**
 * Start timer with duration from data attributes or exercise type
 * Used by data-function="click->startTimer"
 */
window.startTimer = async function(event) {
    if (event && event.preventDefault) {
        event.preventDefault();
    }

    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;


    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return false;
    }

    window.timerManager.ensureNotificationPermission();

    // Prefer computed duration from user preferences and overrides; fallback to data attributes
    let seconds = null;
    try {
        const computed = await window.timerManager.getDefaultDurationForExercise(exerciseId);
        seconds = parseInt(computed, 10);
    } catch (error) {
        console.error('Failed to compute timer duration, checking data attributes:', error);
        const fromAttr = element?.dataset?.duration || element?.dataset?.timer;
        if (fromAttr) {
            seconds = parseInt(fromAttr, 10);
        } else {
            const exerciseType = element?.dataset?.exerciseType;
            seconds = parseInt(getDefaultTimerDuration(exerciseType) || 60, 10);
        }
    }

    return await window.timerManager.startTimer(exerciseId, seconds || 60);
};

/**
 * Pause or resume timer based on current state
 * Used by data-function="click->pauseTimer"
 */
window.pauseTimer = function(event) {
    if (event && event.preventDefault) {
        event.preventDefault();
    }

    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;

    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return false;
    }

    return window.timerManager.pauseTimer(exerciseId);
};

/**
 * Stop the timer completely
 * Used by data-function="click->stopTimer"
 */
window.stopTimer = function(event) {
    if (event && event.preventDefault) {
        event.preventDefault();
    }

    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;

    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return false;
    }

    return window.timerManager.stopTimer(exerciseId);
};

/**
 * Reset timer to initial duration
 * Used by data-function="click->resetTimer"
 */
window.resetTimer = function(event) {
    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;

    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return false;
    }

    return window.timerManager.resetTimer(exerciseId);
};

/**
 * Adjust timer by specified amount from data attributes
 * Used by data-function="click->adjustTimer"
 */
window.adjustTimer = function(event) {
    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;
    const adjustment = parseInt(element?.dataset?.adjust || '30', 10);

    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return 0;
    }

    return window.timerManager.adjustTimer(exerciseId, adjustment);
};

/**
 * Add 30 seconds to current timer
 * Used by data-function="click->addThirtySeconds"
 */
window.addThirtySeconds = function(event) {
    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;

    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return 0;
    }

    return window.timerManager.adjustTimer(exerciseId, 30);
};

/**
 * Subtract 30 seconds from current timer
 * Used by data-function="click->subtractThirtySeconds"
 */
window.subtractThirtySeconds = function(event) {
    // Use currentTarget to get the button element, not the clicked icon/span inside
    const element = event?.currentTarget || event?.target || event;
    const exerciseId = element?.dataset?.exerciseId;

    if (!exerciseId) {
        console.error('No exercise ID found for timer');
        return 0;
    }

    return window.timerManager.adjustTimer(exerciseId, -30);
};

/**
 * Get default timer duration based on exercise type
 * @param {string} exerciseType - Exercise type (primary, secondary, accessory)
 * @returns {number} Default duration in seconds
 */
function getDefaultTimerDuration(exerciseType) {
    // Default durations if user preferences not available
    const defaults = {
        'primary': 180,    // 3 minutes
        'secondary': 120,  // 2 minutes
        'accessory': 90    // 90 seconds (fixed from 60)
    };

    return defaults[exerciseType] || defaults.accessory;
}

// ============================================================================
// TIMER DISPLAY MANAGEMENT
// ============================================================================

/**
 * Update all timer displays on the page
 * Updates timer display elements and control button states
 * This function is kept for backward compatibility and delegates to timer manager
 */
window.updateTimerDisplays = function() {
    window.timerManager.updateTimerDisplays();
};

// ============================================================================
// TIMER EVENT CALLBACKS SETUP
// ============================================================================

// Timer callbacks are now handled by the TimerManager class

// ============================================================================
// DATA-FUNCTION INTEGRATION
// ============================================================================

/**
 * Handle timer auto-start after adding a set
 * Automatically starts rest timer based on exercise type and user preferences
 */
async function handleTimerAutoStart(addSetButton) {
    try {
        // Fetch user timer preferences
        const preferencesResponse = await httpRequestHelper('/api/timer-preferences/', 'GET');

        if (!preferencesResponse.ok) {
            console.warn('Failed to fetch timer preferences, skipping auto-start');
            return;
        }

        const preferences = preferencesResponse.data;

        // Only auto-start if user has the preference enabled
        if (!preferences.auto_start_timer) {
            return;
        }

        // Determine exercise type from parent container
        const exerciseCard = addSetButton.closest('.workout-exercise-card');
        if (!exerciseCard) {
            console.warn('Could not find exercise card for timer auto-start');
            return;
        }

        // Get the exercise ID from the button's parent container
        const exerciseCardForTimer = addSetButton.closest('.workout-exercise-card');
        const exerciseId = exerciseCardForTimer?.dataset.exerciseId;

        if (!exerciseId) {
            console.warn('Could not find exercise ID for timer auto-start');
            return;
        }

        // Determine timer duration using override hierarchy
        let timerDuration = await determineTimerDuration(exerciseId, preferences);

        // Start the timer if we have a valid duration and exercise ID
        if (timerDuration && timerDuration > 0) {
            if (window.timerManager.startTimer(exerciseId, timerDuration)) {
                console.log(`Timer auto-started for exercise ${exerciseId}: ${timerDuration} seconds`);
            }
        }

    } catch (error) {
        console.error('Error in timer auto-start:', error);
        // Silently fail - don't show error to user as this is a convenience feature
    }
}

/**
 * Determine timer duration using the complete override hierarchy:
 * 1. Program-specific setting (highest priority)
 * 2. Routine-specific setting
 * 3. Exercise-specific override
 * 4. Exercise type default (primary/secondary/accessory)
 * 5. System defaults (lowest priority)
 *
 * @param {string} exerciseId - Exercise ID
 * @param {object} preferences - User timer preferences
 * @returns {Promise<number>} Timer duration in seconds
 */
async function determineTimerDuration(exerciseId, preferences) {
    try {
        // Get exercise type first (needed for all levels)
        const exerciseCard = document.querySelector(`[data-exercise-id="${exerciseId}"]`);
        // First check if exercise card has the type directly (mobile view)
        let exerciseType = exerciseCard?.dataset.exerciseType;
        if (!exerciseType) {
            // Fall back to checking category container (desktop view)
            const categoryContainer = exerciseCard?.closest('.exercise-category-container');
            exerciseType = categoryContainer?.dataset.category || 'accessory';
        }

        // Step 1: Check for program-specific setting (highest priority)
        const programTimerDuration = await getProgramTimerDuration(exerciseType);
        if (programTimerDuration) {
            return programTimerDuration;
        }

        // Step 2: Check for routine-specific setting
        const routineTimerDuration = await getRoutineTimerDuration(exerciseType);
        if (routineTimerDuration) {
            return routineTimerDuration;
        }

        // Step 3: Check for exercise-specific override
        const overridesResponse = await httpRequestHelper('/api/exercise-timer-overrides/', 'GET');

        if (overridesResponse.ok && overridesResponse.data.overrides) {
            const exerciseOverride = overridesResponse.data.overrides.find(
                override => override.exercise_id == exerciseId
            );

            if (exerciseOverride) {
                return exerciseOverride.timer_seconds;
            }
        }

        // Step 4: Fall back to exercise type default (from user preferences)
        if (exerciseCard) {
            let typeDuration;
            switch (exerciseType) {
                case 'primary':
                    typeDuration = preferences.primary_timer_seconds;
                    break;
                case 'secondary':
                    typeDuration = preferences.secondary_timer_seconds;
                    break;
                case 'accessory':
                    typeDuration = preferences.accessory_timer_seconds;
                    break;
                default:
                    typeDuration = preferences.accessory_timer_seconds; // Default fallback
            }

            if (typeDuration && typeDuration > 0) {
                return typeDuration;
            }
        }

        // Step 5: Use user preferences as final fallback (lowest priority)
        if (preferences) {
            const fallbackDuration = preferences.accessory_timer_seconds || 90;
            return fallbackDuration;
        }

        console.error(`No timer preferences available for exercise ${exerciseId}`);
        throw new Error('No timer preferences available');

    } catch (error) {
        console.error('Error determining timer duration:', error);
        throw error;
    }
}

/**
 * Get program-specific timer duration for exercise type
 * @param {string} exerciseType - Exercise type (primary/secondary/accessory)
 * @returns {Promise<number|null>} Timer duration in seconds or null if not set
 */
async function getProgramTimerDuration(exerciseType) {
    try {
        // Check if we're in a workout that has a program context
        const workoutElement = document.querySelector('[data-workout-id]');
        const programElement = document.querySelector('[data-program-id]');

        if (!programElement) {
            return null; // No program context
        }

        const programId = programElement.dataset.programId;
        const response = await httpRequestHelper(`/api/programs/${programId}/timer-preferences/`, 'GET');

        if (response.ok && response.data) {
            const programPrefs = response.data;
            let timerSeconds = null;

            switch (exerciseType) {
                case 'primary':
                    timerSeconds = programPrefs.primary_timer_seconds;
                    break;
                case 'secondary':
                    timerSeconds = programPrefs.secondary_timer_seconds;
                    break;
                case 'accessory':
                    timerSeconds = programPrefs.accessory_timer_seconds;
                    break;
            }

            return timerSeconds && timerSeconds > 0 ? timerSeconds : null;
        }

        return null;
    } catch (error) {
        console.warn('Error fetching program timer preferences:', error);
        return null;
    }
}

/**
 * Get routine-specific timer duration for exercise type
 * @param {string} exerciseType - Exercise type (primary/secondary/accessory)
 * @returns {Promise<number|null>} Timer duration in seconds or null if not set
 */
async function getRoutineTimerDuration(exerciseType) {
    try {
        // Check if we're in a workout that has a routine context
        const workoutElement = document.querySelector('[data-workout-id]');
        const routineElement = document.querySelector('[data-routine-id]');

        if (!routineElement) {
            return null; // No routine context
        }

        const routineId = routineElement.dataset.routineId;
        const response = await httpRequestHelper(`/api/routines/${routineId}/timer-preferences/`, 'GET');

        if (response.ok && response.data) {
            const routinePrefs = response.data;
            let timerSeconds = null;

            switch (exerciseType) {
                case 'primary':
                    timerSeconds = routinePrefs.primary_timer_seconds;
                    break;
                case 'secondary':
                    timerSeconds = routinePrefs.secondary_timer_seconds;
                    break;
                case 'accessory':
                    timerSeconds = routinePrefs.accessory_timer_seconds;
                    break;
            }

            return timerSeconds && timerSeconds > 0 ? timerSeconds : null;
        }

        return null;
    } catch (error) {
        console.warn('Error fetching routine timer preferences:', error);
        return null;
    }
}

// ============================================================================
// TIMER PREFERENCES FORM HANDLING
// ============================================================================

/**
 * Save Timer Preferences
 * This function will be triggered by data-function="click->saveTimerPreferences"
 */
window.saveTimerPreferences = async function(event) {
    event.preventDefault();
    const button = event.target;
    const form = button.closest('form');
    if (!form) return;

    // Disable button during request
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = 'Saving...';

    // Clear any previous errors
    clearTimerPreferencesErrors();

    try {
        // Extract form data
        const formData = new FormData(form);
        const data = {};

        // Extract timer preference fields
        const timerFields = [
            'primary_timer_seconds',
            'secondary_timer_seconds',
            'accessory_timer_seconds',
            'preferred_weight_unit',
            'default_weight_increment',
            'default_rep_increment'
        ];

        timerFields.forEach(field => {
            const value = formData.get(field);
            if (value !== null) {
                data[field] = value;
            }
        });

        // Handle checkbox fields
        data.auto_start_timer = formData.has('auto_start_timer');
        data.timer_sound_enabled = formData.has('timer_sound_enabled');
        data.auto_progression_enabled = formData.has('auto_progression_enabled');

        // Make AJAX request
        const response = await httpRequestHelper('/api/timer-preferences/', 'POST', data);

        if (response.ok) {
            send_toast('Timer preferences saved successfully!', 'success');
            clearTimerPreferencesErrors();
        } else {
            // Handle validation errors
            if (response.data && typeof response.data === 'object') {
                displayTimerPreferencesErrors(response.data);
                const errorMsg = response.data.detail || 'Please correct the errors below.';
                send_toast(errorMsg, 'danger');
            } else {
                send_toast(response.data?.detail || 'Error saving timer preferences.', 'danger');
            }
        }
    } catch (error) {
        console.error('Error saving timer preferences:', error);
        const message = error.data?.detail || error.message || 'Error saving timer preferences.';
        send_toast(message, 'danger', 'Request Failed');
    } finally {
        // Re-enable button
        button.disabled = false;
        button.textContent = originalText;
    }
};

/**
 * Helper function to display timer preferences errors
 * @param {object} errors - Error object from API response
 */
function displayTimerPreferencesErrors(errors) {
    // Handle field-specific errors
    Object.keys(errors).forEach(fieldName => {
        const fieldErrors = errors[fieldName];
        if (Array.isArray(fieldErrors) && fieldErrors.length > 0) {
            const input = document.getElementById(fieldName) || document.querySelector(`[name="${fieldName}"]`);
            if (input) {
                // Remove any existing error styling
                input.classList.remove('is-invalid');
                const existingErrorDiv = input.parentElement.querySelector('.invalid-feedback');
                if (existingErrorDiv) {
                    existingErrorDiv.remove();
                }

                // Add error styling and message
                input.classList.add('is-invalid');
                const errorDiv = document.createElement('div');
                errorDiv.className = 'invalid-feedback';
                errorDiv.textContent = fieldErrors[0]; // Show first error
                input.parentElement.appendChild(errorDiv);
            }
        }
    });
}

/**
 * Helper function to clear timer preferences errors
 */
function clearTimerPreferencesErrors() {
    const timerFields = [
        'primary_timer_seconds',
        'secondary_timer_seconds',
        'accessory_timer_seconds',
        'preferred_weight_unit',
        'auto_start_timer',
        'timer_sound_enabled',
        'auto_progression_enabled',
        'default_weight_increment',
        'default_rep_increment'
    ];

    timerFields.forEach(fieldName => {
        const input = document.getElementById(fieldName) || document.querySelector(`[name="${fieldName}"]`);
        if (input) {
            input.classList.remove('is-invalid');
            const existingErrorDiv = input.parentElement.querySelector('.invalid-feedback');
            if (existingErrorDiv) {
                existingErrorDiv.remove();
            }
        }
    });
}

// ============================================================================
// INITIALIZATION
// ============================================================================

// Removed duplicate DOMContentLoaded - initialization handled by the one at line 1794

// Make handleTimerAutoStart available globally for use in gainz.js
window.handleTimerAutoStart = handleTimerAutoStart;

// ============================================================================
// EXERCISE TIMER OVERRIDE MANAGEMENT
// ============================================================================

/**
 * Initialize exercise timer overrides functionality
 */
window.initExerciseTimerOverrides = function() {
    loadExerciseTimerOverrides();
    setupExerciseSearch();
};

/**
 * Load and display existing exercise timer overrides
 */
async function loadExerciseTimerOverrides() {
    try {
        const response = await httpRequestHelper('/api/exercise-timer-overrides/', 'GET');

        if (response.ok && response.data.overrides) {
            displayExerciseTimerOverrides(response.data.overrides);
        } else {
            console.warn('Failed to load exercise timer overrides');
        }
    } catch (error) {
        console.error('Error loading exercise timer overrides:', error);
    }
}

/**
 * Display exercise timer overrides in the UI
 * @param {Array} overrides - Array of override objects
 */
function displayExerciseTimerOverrides(overrides) {
    const overridesList = document.getElementById('exercise-timer-overrides-list');
    const noOverridesMessage = document.getElementById('no-overrides-message');

    if (!overridesList) return;

    // Clear existing content
    overridesList.innerHTML = '';

    if (!overrides || overrides.length === 0) {
        if (noOverridesMessage) {
            overridesList.appendChild(noOverridesMessage);
        }
        return;
    }

    // Create override items
    overrides.forEach(override => {
        const overrideItem = createOverrideItem(override);
        overridesList.appendChild(overrideItem);
    });
}

/**
 * Create HTML element for a single timer override
 * @param {Object} override - Override object
 * @returns {HTMLElement} Override item element
 */
function createOverrideItem(override) {
    const div = document.createElement('div');
    div.className = 'timer-override-item d-flex justify-content-between align-items-center border-bottom py-2';
    div.setAttribute('data-override-id', override.id);

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return mins > 0 ? `${mins}m ${secs}s` : `${secs}s`;
    };

    div.innerHTML = `
        <div class="override-info flex-grow-1">
            <div class="fw-semibold text-dark">${escapeHtml(override.exercise_name)}</div>
            <div class="text-muted small">
                <i class="fas fa-tag me-1"></i>${escapeHtml(override.exercise_category || 'Uncategorized')}
                <span class="mx-2">•</span>
                <i class="fas fa-stopwatch me-1"></i>${formatTime(override.timer_seconds)}
            </div>
        </div>
        <div class="override-actions">
            <button type="button" class="btn btn-sm btn-outline-danger"
                    data-function="click->deleteExerciseTimerOverride"
                    data-override-id="${override.id}"
                    data-exercise-name="${escapeHtml(override.exercise_name)}"
                    title="Delete override">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;

    return div;
}

/**
 * Setup exercise search functionality
 */
function setupExerciseSearch() {
    const searchSelect = document.getElementById('override_exercise_search');
    if (!searchSelect) return;

    // Load initial exercises
    loadExerciseOptions('');

    // Add search functionality (debounced)
    let searchTimeout;
    searchSelect.addEventListener('input', function() {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            const query = this.value;
            if (query.length >= 2 || query.length === 0) {
                loadExerciseOptions(query);
            }
        }, 300);
    });
}

/**
 * Load exercise options for the search dropdown
 * @param {string} query - Search query
 */
async function loadExerciseOptions(query = '') {
    try {
        const searchSelect = document.getElementById('override_exercise_search');
        if (!searchSelect) return;

        const response = await httpRequestHelper(`/api/exercises/search/?q=${encodeURIComponent(query)}&limit=50`, 'GET');

        if (response.ok && response.data.exercises) {
            // Clear existing options (except the first placeholder)
            const placeholder = searchSelect.firstElementChild;
            searchSelect.innerHTML = '';
            searchSelect.appendChild(placeholder);

            // Add exercise options
            response.data.exercises.forEach(exercise => {
                const option = document.createElement('option');
                option.value = exercise.id;
                option.textContent = `${exercise.name} (${exercise.category})`;
                option.setAttribute('data-exercise-type', exercise.exercise_type);
                searchSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading exercise options:', error);
    }
}

/**
 * Add a new exercise timer override
 */
window.addExerciseTimerOverride = async function(event) {
    event.preventDefault();

    const form = document.getElementById('exercise-timer-override-form');
    if (!form) return;

    const button = event.target;
    const originalText = button.innerHTML;

    // Disable button during request
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Adding...';

    try {
        // Clear previous errors
        clearExerciseOverrideFormErrors();

        // Get form data
        const formData = new FormData(form);
        const data = {
            exercise_id: parseInt(formData.get('exercise_id')),
            timer_seconds: parseInt(formData.get('timer_seconds'))
        };

        // Validate data
        if (!data.exercise_id) {
            showExerciseOverrideFieldError('override_exercise_search', 'Please select an exercise.');
            return;
        }

        if (!data.timer_seconds || data.timer_seconds < 10 || data.timer_seconds > 3600) {
            showExerciseOverrideFieldError('override_timer_seconds', 'Timer duration must be between 10 and 3600 seconds.');
            return;
        }

        // Make API request
        const response = await httpRequestHelper('/api/exercise-timer-overrides/', 'POST', data);

        if (response.ok) {
            send_toast('Exercise timer override added successfully!', 'success');

            // Clear form
            form.reset();
            const searchSelect = document.getElementById('override_exercise_search');
            if (searchSelect) searchSelect.selectedIndex = 0;

            // Reload overrides list
            await loadExerciseTimerOverrides();
        } else {
            // Handle validation errors
            if (response.data && response.data.errors) {
                displayExerciseOverrideFormErrors(response.data.errors);
            } else {
                send_toast(response.data?.error || 'Error adding timer override.', 'danger');
            }
        }
    } catch (error) {
        console.error('Error adding exercise timer override:', error);
        send_toast('Error adding timer override.', 'danger');
    } finally {
        // Re-enable button
        button.disabled = false;
        button.innerHTML = originalText;
    }
};

/**
 * Delete an exercise timer override
 */
window.deleteExerciseTimerOverride = async function(event) {
    event.preventDefault();

    const button = event.target.closest('button');
    const overrideId = button.getAttribute('data-override-id');
    const exerciseName = button.getAttribute('data-exercise-name');

    if (!overrideId) {
        console.error('No override ID found');
        return;
    }

    // Confirm deletion
    if (!confirm(`Delete timer override for "${exerciseName}"?`)) {
        return;
    }

    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';

    try {
        const response = await httpRequestHelper(`/api/exercise-timer-overrides/${overrideId}/delete/`, 'DELETE');

        if (response.ok) {
            send_toast('Exercise timer override deleted successfully!', 'success');

            // Remove the item from the DOM
            const overrideItem = document.querySelector(`[data-override-id="${overrideId}"]`);
            if (overrideItem) {
                overrideItem.remove();
            }

            // If no more overrides, show the "no overrides" message
            const overridesList = document.getElementById('exercise-timer-overrides-list');
            if (overridesList && overridesList.children.length === 0) {
                const noOverridesMessage = document.getElementById('no-overrides-message');
                if (noOverridesMessage) {
                    overridesList.appendChild(noOverridesMessage.cloneNode(true));
                }
            }
        } else {
            send_toast(response.data?.error || 'Error deleting timer override.', 'danger');
        }
    } catch (error) {
        console.error('Error deleting exercise timer override:', error);
        send_toast('Error deleting timer override.', 'danger');
    } finally {
        button.disabled = false;
        button.innerHTML = originalText;
    }
};

/**
 * Clear exercise override form errors
 */
function clearExerciseOverrideFormErrors() {
    const fields = ['override_exercise_search', 'override_timer_seconds'];

    fields.forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
            field.classList.remove('is-invalid');
            const feedback = field.parentElement.querySelector('.invalid-feedback');
            if (feedback) {
                feedback.style.display = 'none';
            }
        }
    });
}

/**
 * Show field-specific error for exercise override form
 * @param {string} fieldId - Field ID
 * @param {string} message - Error message
 */
function showExerciseOverrideFieldError(fieldId, message) {
    const field = document.getElementById(fieldId);
    if (field) {
        field.classList.add('is-invalid');
        const feedback = field.parentElement.querySelector('.invalid-feedback');
        if (feedback) {
            feedback.textContent = message;
            feedback.style.display = 'block';
        }
    }
}

/**
 * Display exercise override form errors
 * @param {object} errors - Error object from API response
 */
function displayExerciseOverrideFormErrors(errors) {
    Object.keys(errors).forEach(fieldName => {
        const fieldErrors = errors[fieldName];
        if (Array.isArray(fieldErrors) && fieldErrors.length > 0) {
            let fieldId;
            if (fieldName === 'exercise_id') {
                fieldId = 'override_exercise_search';
            } else if (fieldName === 'timer_seconds') {
                fieldId = 'override_timer_seconds';
            }

            if (fieldId) {
                showExerciseOverrideFieldError(fieldId, fieldErrors[0]);
            }
        }
    });
}

/**
 * Escape HTML to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text ? text.replace(/[&<>"']/g, m => map[m]) : '';
}

// ============================================================================
// TIMER INITIALIZATION ON PAGE LOAD
// ============================================================================

/**
 * Initialize all timer displays with default values on page load
 */
async function initializeTimerDisplays() {
    try {
        // Find all timer displays and set them to default values
        // This is only called for desktop view (mobile check happens before calling)
        const timerDisplays = document.querySelectorAll('[data-timer-display][data-exercise-id]');

        for (const display of timerDisplays) {
            const exerciseId = display.dataset.exerciseId;
            if (exerciseId) {
                await window.timerManager.resetTimerDisplay(exerciseId);
            }
        }
    } catch (error) {
        console.error('Error initializing timer displays:', error);
    }
}

// Initialize timer displays when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize for desktop view (mobile handles its own initialization)
    const isMobileView = document.querySelector('#exercise-card-container');
    if (!isMobileView) {
        // Use MutationObserver to initialize timers when they appear in DOM
        // This is more reliable than arbitrary timeouts
        initializeTimerDisplays();
    }
});

// Also initialize when new content is dynamically added
if (typeof window.observer !== 'undefined') {
    // Hook into the existing MutationObserver to catch new timer displays
    const originalCallback = window.observer.callback;
    if (originalCallback) {
        window.observer.callback = function(mutations) {
            // Call original callback first
            originalCallback(mutations);

            // Then initialize any new timer displays
            mutations.forEach(mutation => {
                if (mutation.type === 'childList') {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === Node.ELEMENT_NODE) {
                            const newDisplays = node.querySelectorAll ? node.querySelectorAll('[data-timer-display][data-exercise-id]') : [];
                            newDisplays.forEach(display => {
                                const exerciseId = display.dataset.exerciseId;
                                if (exerciseId) {
                                    window.timerManager.resetTimerDisplay(exerciseId);
                                }
                            });
                        }
                    });
                }
            });
        };
    }
}
