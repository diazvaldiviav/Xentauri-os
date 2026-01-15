"""
JavaScript Evaluators - Code snippets for Playwright page.evaluate().

All JavaScript code is designed to return serializable dictionaries
(no DOM nodes, functions, or circular references).
"""


class JSEvaluators:
    """
    JavaScript code snippets for browser evaluation.

    Each constant is a JavaScript function body that can be passed
    to page.evaluate(). All return plain objects suitable for JSON.
    """

    # =========================================================================
    # MAIN DIAGNOSTIC (T2-01)
    # =========================================================================

    DIAGNOSE_ELEMENT = """
    (selector) => {
        const element = document.querySelector(selector);
        if (!element) {
            return { found: false };
        }

        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();

        // Get visibility info
        const visibility = {
            display: style.display,
            visibility: style.visibility,
            opacity: parseFloat(style.opacity),
            width: rect.width,
            height: rect.height,
            inViewport: (
                rect.x < window.innerWidth &&
                rect.y < window.innerHeight &&
                rect.right > 0 &&
                rect.bottom > 0
            )
        };

        // Get stacking info
        const zIndexValue = style.zIndex;
        const stacking = {
            zIndex: zIndexValue === 'auto' ? null : parseInt(zIndexValue),
            position: style.position,
            hasTransform: style.transform !== 'none',
            transformValue: style.transform !== 'none' ? style.transform : null,
            createsStackingContext: (
                style.position !== 'static' && zIndexValue !== 'auto'
            ) || style.opacity !== '1' || style.transform !== 'none'
        };

        // Get pointer events info
        const parentStyle = element.parentElement ?
            window.getComputedStyle(element.parentElement) : null;
        const pointerEvents = {
            value: style.pointerEvents,
            inherited: parentStyle ?
                (style.pointerEvents === 'none' && parentStyle.pointerEvents === 'none') :
                false,
            effective: style.pointerEvents !== 'none'
        };

        // Check for interceptor at center point
        const centerX = rect.x + rect.width / 2;
        const centerY = rect.y + rect.height / 2;
        const elementAtPoint = document.elementFromPoint(centerX, centerY);

        let interceptor = null;
        if (elementAtPoint && elementAtPoint !== element &&
            !element.contains(elementAtPoint) && !elementAtPoint.contains(element)) {

            const intStyle = window.getComputedStyle(elementAtPoint);
            const intRect = elementAtPoint.getBoundingClientRect();

            // Generate selector for interceptor
            let intSelector = elementAtPoint.tagName.toLowerCase();
            if (elementAtPoint.id) {
                intSelector = '#' + elementAtPoint.id;
            } else if (elementAtPoint.className && typeof elementAtPoint.className === 'string') {
                const classes = elementAtPoint.className.split(' ').filter(c => c).slice(0, 3);
                if (classes.length) {
                    intSelector += '.' + classes.join('.');
                }
            }

            interceptor = {
                selector: intSelector,
                tagName: elementAtPoint.tagName.toLowerCase(),
                classes: elementAtPoint.className ?
                    (typeof elementAtPoint.className === 'string' ?
                        elementAtPoint.className.split(' ').filter(c => c) : []) : [],
                isOverlay: (
                    intRect.width >= window.innerWidth * 0.9 &&
                    intRect.height >= window.innerHeight * 0.9
                ) || (elementAtPoint.className &&
                      typeof elementAtPoint.className === 'string' &&
                      elementAtPoint.className.includes('inset-0')),
                hasPointerEventsNone: intStyle.pointerEvents === 'none',
                zIndex: intStyle.zIndex === 'auto' ? null : parseInt(intStyle.zIndex)
            };
        }

        return {
            found: true,
            visibility,
            stacking,
            pointerEvents,
            interceptor,
            rect: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            }
        };
    }
    """

    # =========================================================================
    # ELEMENT FROM POINT (T2-02)
    # =========================================================================

    ELEMENT_FROM_POINT = """
    ({x, y}) => {
        const element = document.elementFromPoint(x, y);
        if (!element) {
            return null;
        }

        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();

        // Generate unique selector
        let selector = element.tagName.toLowerCase();
        if (element.id) {
            selector = '#' + element.id;
        } else {
            // Build path from nearest ID or use classes
            const classes = element.className && typeof element.className === 'string' ?
                element.className.split(' ').filter(c => c).slice(0, 3) : [];
            if (classes.length) {
                selector += '.' + classes.join('.');
            }

            // Add nth-child for uniqueness
            if (element.parentElement) {
                const siblings = Array.from(element.parentElement.children)
                    .filter(el => el.tagName === element.tagName);
                if (siblings.length > 1) {
                    const index = siblings.indexOf(element) + 1;
                    selector += ':nth-child(' + index + ')';
                }
            }
        }

        return {
            selector: selector,
            tagName: element.tagName.toLowerCase(),
            classes: element.className && typeof element.className === 'string' ?
                element.className.split(' ').filter(c => c) : [],
            isOverlay: (
                rect.width >= window.innerWidth * 0.9 &&
                rect.height >= window.innerHeight * 0.9
            ) || (element.className &&
                  typeof element.className === 'string' &&
                  element.className.includes('inset-0')),
            hasPointerEventsNone: style.pointerEvents === 'none',
            zIndex: style.zIndex === 'auto' ? null : parseInt(style.zIndex),
            rect: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            }
        };
    }
    """

    # =========================================================================
    # TRANSFORM DETECTION (T2-03, T2-04)
    # =========================================================================

    CHECK_BACKFACE_VISIBILITY = """
    (selector) => {
        const element = document.querySelector(selector);
        if (!element) {
            return { found: false };
        }

        const style = window.getComputedStyle(element);
        const transform = style.transform;

        // Parse rotation from transform matrix
        let rotationY = 0;
        let rotationX = 0;

        if (transform && transform !== 'none') {
            // For 3D transforms, we get a matrix3d
            const match3d = transform.match(/matrix3d\\(([^)]+)\\)/);
            if (match3d) {
                const values = match3d[1].split(',').map(v => parseFloat(v.trim()));
                // Extract rotation from matrix (simplified)
                if (values.length >= 10) {
                    rotationY = Math.abs(Math.asin(Math.max(-1, Math.min(1, values[8])))) * (180 / Math.PI);
                    rotationX = Math.abs(Math.asin(Math.max(-1, Math.min(1, -values[9])))) * (180 / Math.PI);
                }
            }
        }

        const backfaceHidden = style.backfaceVisibility === 'hidden';
        const isBackfacing = rotationY > 90 || rotationX > 90;

        // Check parent for preserve-3d
        let parentHasPreserve3d = false;
        if (element.parentElement) {
            const parentStyle = window.getComputedStyle(element.parentElement);
            parentHasPreserve3d = parentStyle.transformStyle === 'preserve-3d';
        }

        return {
            found: true,
            backfaceVisibility: style.backfaceVisibility,
            backfaceHidden: backfaceHidden,
            isBackfacing: isBackfacing,
            hiddenByBackface: backfaceHidden && isBackfacing,
            rotationY: rotationY,
            rotationX: rotationX,
            parentHasPreserve3d: parentHasPreserve3d,
            transformStyle: style.transformStyle
        };
    }
    """

    CHECK_TRANSFORM_OFFSCREEN = """
    (selector) => {
        const element = document.querySelector(selector);
        if (!element) {
            return { found: false };
        }

        const style = window.getComputedStyle(element);
        const rect = element.getBoundingClientRect();
        const transform = style.transform;

        // Check if transformed off screen
        const offScreen = (
            rect.right < 0 ||
            rect.bottom < 0 ||
            rect.x > window.innerWidth ||
            rect.y > window.innerHeight
        );

        // Check for scale(0) or very small scale
        let hasZeroScale = false;
        if (transform && transform !== 'none') {
            // Check for scale in matrix
            const match = transform.match(/matrix\\(([^)]+)\\)/);
            if (match) {
                const values = match[1].split(',').map(v => parseFloat(v.trim()));
                // values[0] is scaleX, values[3] is scaleY
                if (values.length >= 4) {
                    hasZeroScale = Math.abs(values[0]) < 0.01 || Math.abs(values[3]) < 0.01;
                }
            }
            // Also check matrix3d
            const match3d = transform.match(/matrix3d\\(([^)]+)\\)/);
            if (match3d) {
                const values = match3d[1].split(',').map(v => parseFloat(v.trim()));
                if (values.length >= 6) {
                    hasZeroScale = Math.abs(values[0]) < 0.01 || Math.abs(values[5]) < 0.01;
                }
            }
        }

        // Check for zero dimensions (could be from scale)
        const hasZeroDimensions = rect.width < 1 || rect.height < 1;

        return {
            found: true,
            transform: transform,
            rect: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            },
            offScreen: offScreen,
            hasZeroScale: hasZeroScale,
            hasZeroDimensions: hasZeroDimensions,
            isHiddenByTransform: offScreen || hasZeroScale || hasZeroDimensions
        };
    }
    """

    # =========================================================================
    # BATCH OPERATIONS
    # =========================================================================

    DIAGNOSE_ALL_INTERACTIVE = """
    () => {
        // Find all potentially interactive elements
        const selectors = [
            'button',
            'a[href]',
            'input',
            'select',
            'textarea',
            '[onclick]',
            '[role="button"]',
            '[tabindex]:not([tabindex="-1"])',
            '.cursor-pointer'
        ];

        const elements = document.querySelectorAll(selectors.join(','));
        const results = [];

        elements.forEach((element, index) => {
            const style = window.getComputedStyle(element);
            const rect = element.getBoundingClientRect();

            // Generate selector
            let selector = element.tagName.toLowerCase();
            if (element.id) {
                selector = '#' + element.id;
            } else {
                const attrs = ['data-option', 'data-filter', 'data-submit', 'data-action'];
                for (const attr of attrs) {
                    if (element.hasAttribute(attr)) {
                        const val = element.getAttribute(attr);
                        selector = val ? '[' + attr + '="' + val + '"]' : '[' + attr + ']';
                        break;
                    }
                }
            }

            // Check for interceptor
            const centerX = rect.x + rect.width / 2;
            const centerY = rect.y + rect.height / 2;
            const atPoint = document.elementFromPoint(centerX, centerY);
            const hasInterceptor = atPoint && atPoint !== element &&
                !element.contains(atPoint) && !atPoint.contains(element);

            results.push({
                index: index,
                selector: selector,
                tagName: element.tagName.toLowerCase(),
                isVisible: style.display !== 'none' &&
                           style.visibility !== 'hidden' &&
                           parseFloat(style.opacity) > 0,
                hasInterceptor: hasInterceptor,
                pointerEvents: style.pointerEvents,
                zIndex: style.zIndex === 'auto' ? null : parseInt(style.zIndex),
                rect: {
                    x: rect.x,
                    y: rect.y,
                    width: rect.width,
                    height: rect.height
                }
            });
        });

        return results;
    }
    """

    # =========================================================================
    # UNIQUE SELECTOR GENERATION
    # =========================================================================

    GENERATE_UNIQUE_SELECTOR = """
    (selector) => {
        const element = document.querySelector(selector);
        if (!element) return null;

        if (element.id) {
            return '#' + element.id;
        }

        // Try data attributes
        const dataAttrs = Array.from(element.attributes)
            .filter(attr => attr.name.startsWith('data-'));
        if (dataAttrs.length > 0) {
            const attr = dataAttrs[0];
            if (attr.value) {
                return '[' + attr.name + '="' + attr.value + '"]';
            }
            return '[' + attr.name + ']';
        }

        // Build path from root
        const path = [];
        let current = element;

        while (current && current !== document.body) {
            let sel = current.tagName.toLowerCase();

            if (current.id) {
                path.unshift('#' + current.id);
                break;
            }

            const classes = current.className && typeof current.className === 'string' ?
                current.className.split(' ').filter(c => c).slice(0, 2) : [];
            if (classes.length) {
                sel += '.' + classes.join('.');
            }

            // Add nth-child if needed
            if (current.parentElement) {
                const siblings = Array.from(current.parentElement.children)
                    .filter(el => el.tagName === current.tagName);
                if (siblings.length > 1) {
                    const idx = siblings.indexOf(current) + 1;
                    sel += ':nth-child(' + idx + ')';
                }
            }

            path.unshift(sel);
            current = current.parentElement;
        }

        return path.join(' > ');
    }
    """

    # =========================================================================
    # CLICK TEST
    # =========================================================================

    TEST_CLICK_REACHABLE = """
    (selector) => {
        const element = document.querySelector(selector);
        if (!element) {
            return { reachable: false, reason: 'not_found' };
        }

        const rect = element.getBoundingClientRect();
        const style = window.getComputedStyle(element);

        // Check display
        if (style.display === 'none') {
            return { reachable: false, reason: 'display_none' };
        }

        // Check visibility
        if (style.visibility === 'hidden') {
            return { reachable: false, reason: 'visibility_hidden' };
        }

        // Check opacity
        if (parseFloat(style.opacity) < 0.01) {
            return { reachable: false, reason: 'opacity_zero' };
        }

        // Check dimensions
        if (rect.width < 1 || rect.height < 1) {
            return { reachable: false, reason: 'zero_dimensions' };
        }

        // Check pointer-events
        if (style.pointerEvents === 'none') {
            return { reachable: false, reason: 'pointer_events_none' };
        }

        // Check elementFromPoint
        const centerX = rect.x + rect.width / 2;
        const centerY = rect.y + rect.height / 2;
        const atPoint = document.elementFromPoint(centerX, centerY);

        if (!atPoint) {
            return { reachable: false, reason: 'outside_viewport' };
        }

        if (atPoint !== element && !element.contains(atPoint) && !atPoint.contains(element)) {
            let blockerSelector = atPoint.tagName.toLowerCase();
            if (atPoint.id) {
                blockerSelector = '#' + atPoint.id;
            }
            return {
                reachable: false,
                reason: 'blocked',
                blocker: blockerSelector
            };
        }

        return { reachable: true };
    }
    """
