(function (global) {
    'use strict';

    const API_ENDPOINT = '/api/progress/filter-options/';
    const FALLBACK_POINTS = 6;

    let filterOptionsPromise = null;

    function fetchFilterOptions() {
        if (!filterOptionsPromise) {
            filterOptionsPromise = fetch(API_ENDPOINT, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error(`Request failed with status ${response.status}`);
                    }
                    const contentType = response.headers.get('content-type') || '';
                    if (!contentType.includes('application/json')) {
                        throw new Error('Unexpected response type when loading progress filter options.');
                    }
                    return response.json();
                })
                .catch((error) => {
                    console.error('Failed to load progress filter options:', error);
                    return null;
                });
        }
        return filterOptionsPromise;
    }

    function qs(selector, root) {
        if (!selector) {
            return null;
        }
        if (selector instanceof Element) {
            return selector;
        }
        return (root || document).querySelector(selector);
    }

    function show(element) {
        if (element) {
            element.classList.remove('d-none');
        }
    }

    function hide(element) {
        if (element) {
            element.classList.add('d-none');
        }
    }

    function setSelectOptions(select, options, selectedValue) {
        if (!select || !Array.isArray(options) || !options.length) {
            return;
        }

        const desiredValue = selectedValue !== undefined && selectedValue !== null
            ? String(selectedValue)
            : String(select.value || '');

        select.innerHTML = '';
        options.forEach((entry) => {
            if (!entry) {
                return;
            }
            const option = document.createElement('option');
            option.value = String(entry.value ?? entry.id ?? '');
            option.textContent = entry.label ?? entry.name ?? option.value;
            if (option.value === desiredValue) {
                option.selected = true;
            }
            select.appendChild(option);
        });

        if (!select.value && select.options.length) {
            select.options[0].selected = true;
        }
    }

    function formatDateLabel(isoString) {
        if (!isoString) {
            return '';
        }
        const date = new Date(isoString);
        if (Number.isNaN(date.valueOf())) {
            return '';
        }
        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    }

    function getFallbackLabels() {
        const labels = [];
        const today = new Date();
        for (let index = FALLBACK_POINTS - 1; index >= 0; index -= 1) {
            const date = new Date(today);
            date.setDate(date.getDate() - index * 7);
            labels.push(date.toISOString());
        }
        return labels;
    }

    function buildFallbackData(chartType) {
        const labels = getFallbackLabels();
        const primary = labels.map(() => null);
        const weight = chartType === 'volume' ? null : labels.map(() => null);
        return { labels, primary, weight };
    }

    function setCustomInvalid(customRange, message) {
        if (!customRange) {
            return;
        }
        if (customRange.minInput) {
            customRange.minInput.classList.add('is-invalid');
        }
        if (customRange.maxInput) {
            customRange.maxInput.classList.add('is-invalid');
        }
        if (customRange.feedback) {
            if (message) {
                customRange.feedback.textContent = message;
            }
            customRange.feedback.classList.remove('d-none');
        }
    }

    function clearCustomInvalid(customRange) {
        if (!customRange) {
            return;
        }
        if (customRange.minInput) {
            customRange.minInput.classList.remove('is-invalid');
        }
        if (customRange.maxInput) {
            customRange.maxInput.classList.remove('is-invalid');
        }
        if (customRange.feedback) {
            customRange.feedback.classList.add('d-none');
        }
    }

    function validateCustomRange(customRange) {
        if (!customRange || !customRange.container || customRange.container.classList.contains('d-none')) {
            clearCustomInvalid(customRange);
            return { valid: true };
        }

        const minValue = Number.parseInt(customRange.minInput?.value, 10);
        const maxValue = Number.parseInt(customRange.maxInput?.value, 10);

        if (Number.isNaN(minValue) || Number.isNaN(maxValue)) {
            setCustomInvalid(customRange, 'Enter both minimum and maximum reps.');
            return { valid: false };
        }

        if (minValue > maxValue) {
            setCustomInvalid(customRange, 'Min reps must be less than or equal to max reps.');
            return { valid: false };
        }

        clearCustomInvalid(customRange);
        return {
            valid: true,
            min: minValue,
            max: maxValue,
        };
    }

    function buildChartUrl(exerciseId, filters) {
        const params = new URLSearchParams();
        if (filters.period) {
            params.set('period', filters.period);
        }
        if (filters.repRange) {
            params.set('rep_range', filters.repRange);
        }
        if (filters.chartType) {
            params.set('chart_type', filters.chartType);
        }
        if (filters.comparisonType) {
            params.set('comparison', filters.comparisonType);
        }
        if (filters.repRange === 'custom') {
            if (filters.minReps) {
                params.set('min_reps', filters.minReps);
            }
            if (filters.maxReps) {
                params.set('max_reps', filters.maxReps);
            }
        }
        return `/api/progress/exercise/${exerciseId}/chart-data/?${params.toString()}`;
    }

    function debounce(fn, delay) {
        let timer = null;
        return function debounced(...args) {
            if (timer) {
                clearTimeout(timer);
            }
            timer = setTimeout(() => {
                fn.apply(this, args);
            }, delay);
        };
    }

    function createChartController(config) {
        let canvas = qs(config?.canvas);
        if (!canvas) {
            return null;
        }

        const loadingEl = qs(config?.loading);
        const emptyEl = qs(config?.empty);
        const emptyText = emptyEl ? emptyEl.querySelector('[data-empty-text]') : null;
        let chartInstance = null;
        let requestToken = 0;

        function clearEmpty() {
            hide(emptyEl);
        }

        function setEmpty(message) {
            if (!emptyEl) {
                return;
            }
            if (emptyText) {
                emptyText.textContent = message || emptyText.textContent || '';
            } else if (message) {
                emptyEl.textContent = message;
            }
            show(emptyEl);
        }

        function resetCanvas() {
            if (!canvas || !canvas.parentNode) {
                return;
            }
            const replacement = canvas.cloneNode(false);
            canvas.parentNode.replaceChild(replacement, canvas);
            canvas = replacement;
        }

        function destroy() {
            if (typeof global.Chart?.getChart === 'function') {
                const existing = global.Chart.getChart(canvas);
                if (existing && existing !== chartInstance) {
                    try {
                        existing.destroy();
                    } catch (error) {
                        console.warn('Failed to destroy existing Chart.js instance:', error);
                    }
                }
            }

            if (chartInstance) {
                try {
                    chartInstance.destroy();
                } catch (error) {
                    console.warn('Failed to destroy Chart.js instance:', error);
                }
                chartInstance = null;
            }

            resetCanvas();
        }

        function renderChart(dataPoints, chartType, options = {}) {
            if (typeof global.Chart !== 'function') {
                console.warn('Chart.js is required for rendering progress charts.');
                return;
            }

            const fallback = options.fallback === true;
            const hasData = !fallback && Array.isArray(dataPoints) && dataPoints.length > 0;
            const isVolume = chartType === 'volume';

            let labels;
            let primaryData;
            let weightData;

            if (hasData) {
                labels = dataPoints.map((point) => point.x || point.date || '');
                primaryData = dataPoints.map((point) => {
                    if (isVolume) {
                        if (point.volume !== undefined && point.volume !== null) {
                            return Number(point.volume);
                        }
                        return Number(point.y ?? 0);
                    }
                    const estimate = point.estimated_1rm !== undefined && point.estimated_1rm !== null
                        ? point.estimated_1rm
                        : point.y;
                    return estimate !== undefined && estimate !== null ? Number(estimate) : null;
                });
                weightData = isVolume
                    ? null
                    : dataPoints.map((point) => (point.weight !== undefined && point.weight !== null ? Number(point.weight) : null));
            } else {
                const fallbackData = buildFallbackData(chartType);
                labels = fallbackData.labels;
                primaryData = fallbackData.primary;
                weightData = fallbackData.weight;
            }

            destroy();
            const ctx = canvas.getContext('2d');

            const datasets = [];
            datasets.push({
                label: isVolume ? 'Set Volume' : 'Estimated 1RM',
                data: primaryData,
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.15)',
                borderWidth: 2,
                pointRadius: 3,
                tension: 0.3,
                spanGaps: true,
                borderDash: fallback ? [6, 4] : undefined,
            });

            if (!isVolume && weightData) {
                datasets.push({
                    label: 'Logged Weight',
                    data: weightData,
                    borderColor: '#20c997',
                    backgroundColor: 'rgba(32, 201, 151, 0.1)',
                    borderDash: [6, 4],
                    borderWidth: 2,
                    pointRadius: 3,
                    tension: 0.3,
                    spanGaps: true,
                });
            }

            chartInstance = new global.Chart(ctx, {
                type: 'line',
                data: {
                    labels,
                    datasets,
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index',
                    },
                    plugins: {
                        legend: {
                            position: 'bottom',
                        },
                        tooltip: {
                            callbacks: {
                                title(items) {
                                    if (!items.length) {
                                        return '';
                                    }
                                    const index = items[0].dataIndex;
                                    return formatDateLabel(labels[index]);
                                },
                                label(context) {
                                    const value = context.dataset.data[context.dataIndex];
                                    if (value === null || value === undefined) {
                                        return `${context.dataset.label}: --`;
                                    }
                                    const numericValue = Number(value);
                                    const formatted = Number.isFinite(numericValue)
                                        ? numericValue.toFixed(isVolume ? 0 : 1)
                                        : value;
                                    const suffix = isVolume ? ' kg x reps' : ' kg';
                                    return `${context.dataset.label}: ${formatted}${suffix}`;
                                },
                                afterBody(items) {
                                    if (!items.length || !hasData) {
                                        return undefined;
                                    }
                                    const point = dataPoints[items[0].dataIndex];
                                    const details = [];
                                    if (point.weight !== undefined && point.weight !== null) {
                                        const numericWeight = Number(point.weight);
                                        const formattedWeight = Number.isFinite(numericWeight)
                                            ? numericWeight.toFixed(1)
                                            : point.weight;
                                        details.push(`Weight: ${formattedWeight} kg`);
                                    }
                                    if (point.reps !== undefined && point.reps !== null) {
                                        details.push(`Reps: ${point.reps}`);
                                    }
                                    return details.length ? details : undefined;
                                },
                            },
                        },
                    },
                    scales: {
                        x: {
                            ticks: {
                                callback(value, index) {
                                    return formatDateLabel(labels[index]);
                                },
                            },
                            grid: {
                                display: false,
                            },
                        },
                        y: {
                            beginAtZero: isVolume,
                            title: {
                                display: true,
                                text: isVolume ? 'Volume (kg x reps)' : 'Weight (kg)',
                            },
                            grid: {
                                color: 'rgba(0,0,0,0.05)',
                            },
                        },
                    },
                },
            });
        }

        async function load(exerciseId, filters) {
            requestToken += 1;
            const token = requestToken;

            if (loadingEl) {
                show(loadingEl);
            }
            clearEmpty();
            canvas.classList.add('d-none');

            if (!exerciseId) {
                renderChart([], filters.chartType || '1rm', { fallback: true });
                canvas.classList.remove('d-none');
                if (loadingEl) {
                    hide(loadingEl);
                }
                return { data: [], empty: true };
            }

            try {
                const response = await fetch(buildChartUrl(exerciseId, filters), {
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                });

                if (!response.ok) {
                    throw new Error(`Request failed with status ${response.status}`);
                }

                const contentType = response.headers.get('content-type') || '';
                if (!contentType.includes('application/json')) {
                    throw new Error('Unexpected response type when loading chart data.');
                }

                const payload = await response.json();
                if (token !== requestToken) {
                    return { data: [], empty: true };
                }

                if (payload && payload.success === false) {
                    throw new Error(payload.error || 'Progress API returned an error response.');
                }

                const dataPoints = Array.isArray(payload?.data) ? payload.data : [];
                canvas.classList.remove('d-none');

                if (!dataPoints.length) {
                    renderChart([], filters.chartType || '1rm', { fallback: true });
                    return { data: [], empty: true };
                }

                renderChart(dataPoints, filters.chartType || '1rm');
                return { data: dataPoints, empty: false };
            } catch (error) {
                if (token !== requestToken) {
                    return { data: [], empty: true };
                }
                console.error('Unable to load progress chart data:', error);
                destroy();
                canvas.classList.add('d-none');
                setEmpty('Unable to load chart data.');
                return { data: [], empty: true, error: true };
            } finally {
                if (token === requestToken && loadingEl) {
                    hide(loadingEl);
                }
            }
        }

        function renderInitial(dataPoints, chartType) {
            clearEmpty();
            canvas.classList.remove('d-none');
            renderChart(dataPoints, chartType || '1rm');
        }

        return {
            load,
            destroy,
            renderFallback(chartType) {
                canvas.classList.remove('d-none');
                renderChart([], chartType || '1rm', { fallback: true });
            },
            renderInitial,
            showError(message) {
                destroy();
                canvas.classList.add('d-none');
                setEmpty(message || 'Unable to load chart data.');
            },
        };
    }

    function ensureDefaultValue(input, fallback) {
        if (input && !input.value) {
            input.value = fallback;
        }
    }

    function initOverview(config) {
        const exerciseSelect = qs(config?.exerciseSelect);
        const periodSelect = qs(config?.periodSelect);
        const repRangeSelect = qs(config?.repRangeSelect);
        const chartTypeSelect = qs(config?.chartTypeSelect);
        const customRange = config?.customRange
            ? {
                container: qs(config.customRange.container),
                minInput: qs(config.customRange.minInput),
                maxInput: qs(config.customRange.maxInput),
                feedback: qs(config.customRange.feedback),
            }
            : null;

        const controller = createChartController(config?.chart);
        if (!controller) {
            return;
        }

        const defaults = config?.defaults || {};
        ensureDefaultValue(customRange?.minInput, defaults.minReps || '3');
        ensureDefaultValue(customRange?.maxInput, defaults.maxReps || '12');

        function updateCustomRangeVisibility() {
            if (!customRange || !customRange.container) {
                return;
            }
            const value = (repRangeSelect?.value || defaults.repRange || '').toLowerCase();
            if (value === 'custom') {
                show(customRange.container);
            } else {
                hide(customRange.container);
                clearCustomInvalid(customRange);
            }
        }

        function collectFilters() {
            const filters = {
                period: periodSelect?.value || String(defaults.period || '30'),
                repRange: repRangeSelect?.value || (defaults.repRange || ''),
                chartType: (chartTypeSelect?.value || defaults.chartType || '1rm').toLowerCase(),
            };

            updateCustomRangeVisibility();

            if (filters.repRange === 'custom') {
                const validation = validateCustomRange(customRange);
                if (!validation.valid) {
                    return null;
                }
                filters.minReps = validation.min;
                filters.maxReps = validation.max;
            }

            return filters;
        }

        function loadChart() {
            const filters = collectFilters();
            if (!filters) {
                return;
            }
            const exerciseId = exerciseSelect?.value || defaults.exerciseId || '';
            if (!exerciseId) {
                controller.renderFallback(filters.chartType || '1rm');
                return;
            }
            controller.load(exerciseId, filters);
        }

        const debouncedCustomRange = debounce(loadChart, 350);

        if (exerciseSelect) {
            exerciseSelect.addEventListener('change', loadChart);
        }
        if (periodSelect) {
            periodSelect.addEventListener('change', loadChart);
        }
        if (repRangeSelect) {
            repRangeSelect.addEventListener('change', () => {
                updateCustomRangeVisibility();
                loadChart();
            });
        }
        if (chartTypeSelect) {
            chartTypeSelect.addEventListener('change', loadChart);
        }
        if (customRange?.minInput) {
            customRange.minInput.addEventListener('input', debouncedCustomRange);
        }
        if (customRange?.maxInput) {
            customRange.maxInput.addEventListener('input', debouncedCustomRange);
        }

        fetchFilterOptions().then((options) => {
            if (options) {
                if (exerciseSelect && Array.isArray(options.exercises) && options.exercises.length) {
                    const mappedExercises = options.exercises.map((entry) => ({
                        value: entry.id,
                        label: entry.name,
                    }));
                    setSelectOptions(exerciseSelect, mappedExercises, defaults.exerciseId || exerciseSelect.value);
                }

                if (periodSelect && Array.isArray(options.date_ranges) && options.date_ranges.length) {
                    setSelectOptions(periodSelect, options.date_ranges, defaults.period || periodSelect.value);
                }

                if (repRangeSelect && Array.isArray(options.rep_ranges) && options.rep_ranges.length) {
                    setSelectOptions(repRangeSelect, options.rep_ranges, defaults.repRange || repRangeSelect.value);
                }
            }

            if (exerciseSelect && defaults.exerciseId) {
                exerciseSelect.value = String(defaults.exerciseId);
            }
            if (periodSelect && defaults.period) {
                periodSelect.value = String(defaults.period);
            }
            if (repRangeSelect && defaults.repRange !== undefined) {
                repRangeSelect.value = String(defaults.repRange);
            }
            if (chartTypeSelect && defaults.chartType) {
                chartTypeSelect.value = String(defaults.chartType).toLowerCase();
            }

            updateCustomRangeVisibility();
            loadChart();
        });

        global.addEventListener('beforeunload', () => {
            controller.destroy();
        });
    }

    function formatNumber(value, decimals) {
        if (value === null || value === undefined || Number.isNaN(value)) {
            return '--';
        }
        const formatter = new Intl.NumberFormat(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
        return formatter.format(value);
    }

    function computeExerciseStats(dataPoints, chartType) {
        if (!Array.isArray(dataPoints) || !dataPoints.length) {
            return {
                currentMax: null,
                best1rm: null,
                totalVolume: null,
                workoutCount: 0,
            };
        }

        let currentMax = null;
        let best1rm = null;
        let totalVolume = 0;
        const workoutIds = new Set();

        dataPoints.forEach((point) => {
            if (point.weight !== undefined && point.weight !== null) {
                const weightValue = Number(point.weight);
                if (Number.isFinite(weightValue)) {
                    currentMax = currentMax === null ? weightValue : Math.max(currentMax, weightValue);
                }
            }

            const estimatedValue = point.estimated_1rm !== undefined && point.estimated_1rm !== null
                ? Number(point.estimated_1rm)
                : (chartType === '1rm' && point.y !== undefined && point.y !== null ? Number(point.y) : null);
            if (estimatedValue !== null && Number.isFinite(estimatedValue)) {
                best1rm = best1rm === null ? estimatedValue : Math.max(best1rm, estimatedValue);
            }

            const volumeValue = point.volume !== undefined && point.volume !== null
                ? Number(point.volume)
                : (chartType === 'volume' && point.y !== undefined && point.y !== null ? Number(point.y) : null);
            if (volumeValue !== null && Number.isFinite(volumeValue)) {
                totalVolume += volumeValue;
            }

            const workoutKey = point.workout_id ?? point.x ?? point.date;
            if (workoutKey) {
                workoutIds.add(workoutKey);
            }
        });

        return {
            currentMax,
            best1rm,
            totalVolume,
            workoutCount: workoutIds.size,
        };
    }

    function updateExerciseStats(elements, stats) {
        if (!elements) {
            return;
        }
        if (elements.currentMax) {
            elements.currentMax.textContent = formatNumber(stats.currentMax, 1);
        }
        if (elements.best1rm) {
            elements.best1rm.textContent = formatNumber(stats.best1rm, 1);
        }
        if (elements.totalVolume) {
            elements.totalVolume.textContent = formatNumber(stats.totalVolume, 0);
        }
        if (elements.workoutCount) {
            elements.workoutCount.textContent = stats.workoutCount ? stats.workoutCount : '--';
        }
    }

    function initExerciseDetail(config) {
        const exerciseId = String(config?.exerciseId ?? '').trim();
        if (!exerciseId) {
            console.warn('initExerciseDetail requires an exerciseId.');
        }

        const controller = createChartController(config?.chart);
        if (!controller) {
            return;
        }

        const statElements = {
            currentMax: document.querySelector('[data-progress-current-max]'),
            best1rm: document.querySelector('[data-progress-best-1rm]'),
            totalVolume: document.querySelector('[data-progress-total-volume]'),
            workoutCount: document.querySelector('[data-progress-workout-count]'),
        };

        const periodSelect = qs(config?.periodSelect);
        const repRangeSelect = qs(config?.repRangeSelect);
        const chartTypeSelect = qs(config?.chartTypeSelect);
        const comparisonSelect = qs(config?.comparisonSelect);
        const customRange = config?.customRange
            ? {
                container: qs(config.customRange.container),
                minInput: qs(config.customRange.minInput),
                maxInput: qs(config.customRange.maxInput),
                feedback: qs(config.customRange.feedback),
            }
            : null;

        const defaults = config?.defaults || {};
        ensureDefaultValue(customRange?.minInput, defaults.minReps || '3');
        ensureDefaultValue(customRange?.maxInput, defaults.maxReps || '12');

        function updateCustomRangeVisibility() {
            if (!customRange || !customRange.container) {
                return;
            }
            const value = (repRangeSelect?.value || defaults.repRange || '').toLowerCase();
            if (value === 'custom') {
                show(customRange.container);
            } else {
                hide(customRange.container);
                clearCustomInvalid(customRange);
            }
        }

        function collectFilters() {
            const comparisonRaw = comparisonSelect?.value || defaults.comparisonType || 'average';
            let comparisonType = String(comparisonRaw).toLowerCase();
            if (comparisonType === 'heaviest') {
                comparisonType = 'peak';
            }
            if (comparisonType !== 'peak') {
                comparisonType = 'average';
            }

            const filters = {
                period: periodSelect?.value || String(defaults.period || '90'),
                repRange: repRangeSelect?.value || (defaults.repRange || ''),
                chartType: (chartTypeSelect?.value || defaults.chartType || '1rm').toLowerCase(),
                comparisonType,
            };

            updateCustomRangeVisibility();

            if (filters.repRange === 'custom') {
                const validation = validateCustomRange(customRange);
                if (!validation.valid) {
                    return null;
                }
                filters.minReps = validation.min;
                filters.maxReps = validation.max;
            }

            return filters;
        }

        async function loadChart() {
            const filters = collectFilters();
            if (!filters) {
                return;
            }
            const result = await controller.load(exerciseId, filters);
            updateExerciseStats(statElements, computeExerciseStats(result.data, filters.chartType || '1rm'));
        }

        const debouncedCustomRange = debounce(loadChart, 350);

        if (periodSelect) {
            periodSelect.addEventListener('change', loadChart);
        }
        if (repRangeSelect) {
            repRangeSelect.addEventListener('change', () => {
                updateCustomRangeVisibility();
                loadChart();
            });
        }
        if (chartTypeSelect) {
            chartTypeSelect.addEventListener('change', loadChart);
        }
        if (comparisonSelect) {
            comparisonSelect.addEventListener('change', loadChart);
        }
        if (customRange?.minInput) {
            customRange.minInput.addEventListener('input', debouncedCustomRange);
        }
        if (customRange?.maxInput) {
            customRange.maxInput.addEventListener('input', debouncedCustomRange);
        }

        const initialData = Array.isArray(config?.initialData) ? config.initialData : [];
        const initialChartType = (defaults.chartType || '1rm').toLowerCase();

        if (initialData.length) {
            controller.renderInitial(initialData, initialChartType);
            updateExerciseStats(statElements, computeExerciseStats(initialData, initialChartType));
        }

        loadChart();

        fetchFilterOptions().then((options) => {
            if (options) {
                if (periodSelect && Array.isArray(options.date_ranges) && options.date_ranges.length) {
                    setSelectOptions(periodSelect, options.date_ranges, defaults.period || periodSelect.value);
                }

                if (repRangeSelect && Array.isArray(options.rep_ranges) && options.rep_ranges.length) {
                    setSelectOptions(repRangeSelect, options.rep_ranges, defaults.repRange || repRangeSelect.value);
                }
            }

            if (periodSelect && defaults.period) {
                periodSelect.value = String(defaults.period);
            }
            if (repRangeSelect && defaults.repRange !== undefined) {
                repRangeSelect.value = String(defaults.repRange);
            }
            if (chartTypeSelect && defaults.chartType) {
                chartTypeSelect.value = String(defaults.chartType).toLowerCase();
            }
            if (comparisonSelect && defaults.comparisonType) {
                comparisonSelect.value = String(defaults.comparisonType).toLowerCase();
            }

            updateCustomRangeVisibility();
            loadChart();
        });

        global.addEventListener('beforeunload', () => {
            controller.destroy();
        });
    }

    global.ProgressCharts = {
        initOverview,
        initExerciseDetail,
    };
})(window);
