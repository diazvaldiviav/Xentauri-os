"""
Scene Graph Extractor - Phase 3: DOM geometry extraction.

Sprint 6: Visual-based validation system.

This module extracts geometric truth from the DOM:
- Enumerate visible nodes
- Extract bounding boxes
- Determine node types (button, input, text, etc.)
- Track visibility and z-index

This gives us real positions, not what HTML "should" render.
"""

import logging
import time
from typing import Optional, Tuple, TYPE_CHECKING

from .contracts import (
    BoundingBox,
    ObservedSceneGraph,
    PhaseResult,
    SceneNode,
)

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger("jarvis.ai.scene.custom_layout.validation.scene_graph")


# ---------------------------------------------------------------------------
# JAVASCRIPT FOR DOM EXTRACTION
# ---------------------------------------------------------------------------

JS_EXTRACT_SCENE_GRAPH = """
() => {
    const nodes = [];
    const seen = new Set();

    function getUniqueSelector(el, index) {
        // Try ID first
        if (el.id) return '#' + el.id;

        // Try data attributes
        for (const attr of ['data-testid', 'data-option', 'data-submit', 'data-question']) {
            if (el.hasAttribute(attr)) {
                const val = el.getAttribute(attr);
                return `[${attr}="${val}"]`;
            }
        }

        // Build path with class
        const tag = el.tagName.toLowerCase();
        if (el.className && typeof el.className === 'string') {
            const firstClass = el.className.split(' ')[0];
            if (firstClass) {
                const selector = `${tag}.${firstClass}`;
                // Check if unique
                if (document.querySelectorAll(selector).length === 1) {
                    return selector;
                }
            }
        }

        // Fallback: tag with nth-child
        const parent = el.parentElement;
        if (parent) {
            const siblings = Array.from(parent.children).filter(c => c.tagName === el.tagName);
            if (siblings.length > 1) {
                const idx = siblings.indexOf(el) + 1;
                return `${tag}:nth-of-type(${idx})`;
            }
        }

        return `${tag}[data-idx="${index}"]`;
    }

    function getNodeType(el) {
        const tag = el.tagName.toLowerCase();
        const role = el.getAttribute('role');

        // Buttons
        if (tag === 'button' || role === 'button' ||
            (tag === 'input' && ['button', 'submit'].includes(el.type))) {
            return 'button';
        }

        // Links
        if (tag === 'a' && el.href) {
            return 'button';  // Treat as clickable
        }

        // Form inputs
        if (['input', 'select', 'textarea'].includes(tag)) {
            return 'input';
        }

        // Images/media
        if (['img', 'svg', 'canvas', 'video'].includes(tag)) {
            return 'image';
        }

        // Text nodes (leaf nodes with text)
        if (el.childNodes.length > 0) {
            const hasOnlyText = Array.from(el.childNodes).every(
                n => n.nodeType === Node.TEXT_NODE ||
                     (n.nodeType === Node.ELEMENT_NODE && getComputedStyle(n).display === 'inline')
            );
            if (hasOnlyText && el.innerText && el.innerText.trim()) {
                return 'text';
            }
        }

        return 'container';
    }

    function isVisible(el) {
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;

        const style = window.getComputedStyle(el);
        if (style.display === 'none') return false;
        if (style.visibility === 'hidden') return false;
        if (parseFloat(style.opacity) === 0) return false;

        // Check if in viewport
        return rect.top < window.innerHeight && rect.left < window.innerWidth &&
               rect.bottom > 0 && rect.right > 0;
    }

    // Walk DOM and extract nodes
    const elements = document.body.querySelectorAll('*');
    let index = 0;

    for (const el of elements) {
        index++;

        // Skip invisible elements
        if (!isVisible(el)) continue;

        const rect = el.getBoundingClientRect();
        const style = window.getComputedStyle(el);

        // Skip very small elements (likely decorative)
        if (rect.width < 5 || rect.height < 5) continue;

        const selector = getUniqueSelector(el, index);

        // Skip duplicates
        if (seen.has(selector)) continue;
        seen.add(selector);

        // Extract relevant attributes
        const attrs = {};
        const interestingAttrs = [
            'type', 'role', 'disabled', 'href', 'onclick',
            'data-option', 'data-submit', 'data-question', 'data-feedback',
            'data-trivia', 'data-game', 'data-dashboard',
            'aria-selected', 'aria-checked', 'aria-pressed'
        ];
        for (const attr of interestingAttrs) {
            if (el.hasAttribute(attr)) {
                attrs[attr] = el.getAttribute(attr);
            }
        }

        // Check for cursor pointer (indicates clickable)
        if (style.cursor === 'pointer') {
            attrs['cursor'] = 'pointer';
        }

        nodes.push({
            selector: selector,
            tag: el.tagName.toLowerCase(),
            nodeType: getNodeType(el),
            boundingBox: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            },
            visible: true,
            zIndex: parseInt(style.zIndex) || 0,
            textContent: (el.innerText || '').slice(0, 100).trim(),
            attributes: attrs
        });
    }

    return {
        nodes: nodes,
        viewport: [window.innerWidth, window.innerHeight]
    };
}
"""


# ---------------------------------------------------------------------------
# SCENE GRAPH EXTRACTOR
# ---------------------------------------------------------------------------

class SceneGraphExtractor:
    """
    Phase 3: Extract visible nodes with geometry from DOM.

    Uses injected JavaScript to enumerate all visible elements
    and extract their bounding boxes, types, and attributes.
    """

    async def extract(
        self,
        page: "Page",
    ) -> Tuple[PhaseResult, Optional[ObservedSceneGraph]]:
        """
        Extract scene graph from current page state.

        Args:
            page: Playwright page with HTML loaded

        Returns:
            (PhaseResult, ObservedSceneGraph) - Graph is None if extraction failed
        """
        start_time = time.time()

        try:
            # Execute extraction script
            data = await page.evaluate(JS_EXTRACT_SCENE_GRAPH)

            # Convert to dataclasses
            nodes = []
            for n in data.get("nodes", []):
                try:
                    bbox_data = n.get("boundingBox", {})
                    bbox = BoundingBox(
                        x=bbox_data.get("x", 0),
                        y=bbox_data.get("y", 0),
                        width=bbox_data.get("width", 0),
                        height=bbox_data.get("height", 0),
                    )

                    node = SceneNode(
                        selector=n.get("selector", ""),
                        tag=n.get("tag", ""),
                        node_type=n.get("nodeType", "unknown"),
                        bounding_box=bbox,
                        visible=n.get("visible", False),
                        z_index=n.get("zIndex", 0),
                        text_content=n.get("textContent"),
                        attributes=n.get("attributes", {}),
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"Failed to parse node: {e}")
                    continue

            viewport_data = data.get("viewport", [1920, 1080])
            viewport = (viewport_data[0], viewport_data[1])

            duration_ms = (time.time() - start_time) * 1000

            graph = ObservedSceneGraph(
                nodes=nodes,
                viewport=viewport,
                capture_time_ms=duration_ms,
            )

            # Count by type for logging
            type_counts = {}
            for node in nodes:
                type_counts[node.node_type] = type_counts.get(node.node_type, 0) + 1

            # Phase passes if we found any nodes
            passed = len(nodes) > 0
            interactive_count = len(graph.interactive_nodes())

            if not passed:
                logger.warning("Phase 3 (scene_graph): No visible nodes found")
                return PhaseResult(
                    phase=3,
                    phase_name="scene_graph",
                    passed=False,
                    error="No visible nodes found in DOM",
                    duration_ms=duration_ms,
                ), graph

            logger.info(
                f"Phase 3 (scene_graph) passed - "
                f"{len(nodes)} nodes, {interactive_count} interactive, "
                f"types={type_counts}"
            )

            return PhaseResult(
                phase=3,
                phase_name="scene_graph",
                passed=True,
                details={
                    "total_nodes": len(nodes),
                    "interactive_nodes": interactive_count,
                    "type_counts": type_counts,
                    "viewport": f"{viewport[0]}x{viewport[1]}",
                },
                duration_ms=duration_ms,
            ), graph

        except Exception as e:
            logger.error(f"Scene graph extraction error: {e}", exc_info=True)
            return PhaseResult(
                phase=3,
                phase_name="scene_graph",
                passed=False,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            ), None

    async def extract_quick(self, page: "Page") -> ObservedSceneGraph:
        """
        Quick extraction without PhaseResult (for interaction testing).

        Raises:
            Exception if extraction fails
        """
        start_time = time.time()
        data = await page.evaluate(JS_EXTRACT_SCENE_GRAPH)

        nodes = []
        for n in data.get("nodes", []):
            bbox_data = n.get("boundingBox", {})
            bbox = BoundingBox(
                x=bbox_data.get("x", 0),
                y=bbox_data.get("y", 0),
                width=bbox_data.get("width", 0),
                height=bbox_data.get("height", 0),
            )

            node = SceneNode(
                selector=n.get("selector", ""),
                tag=n.get("tag", ""),
                node_type=n.get("nodeType", "unknown"),
                bounding_box=bbox,
                visible=n.get("visible", False),
                z_index=n.get("zIndex", 0),
                text_content=n.get("textContent"),
                attributes=n.get("attributes", {}),
            )
            nodes.append(node)

        viewport_data = data.get("viewport", [1920, 1080])

        return ObservedSceneGraph(
            nodes=nodes,
            viewport=(viewport_data[0], viewport_data[1]),
            capture_time_ms=(time.time() - start_time) * 1000,
        )


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

scene_graph_extractor = SceneGraphExtractor()
