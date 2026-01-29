"""
Scene Service - Core service for generating and populating Scene Graphs.

Sprint 4.0: This service orchestrates scene generation by:
1. Normalizing layout hints from user requests
2. Generating layouts via Gemini 3 Flash (primary) or Claude (fallback)
3. Fetching data for each component (calendar events, etc.)
4. Validating the final Scene Graph

Usage:
======
    from app.ai.scene import scene_service
    
    # Generate a complete scene
    scene = await scene_service.generate_scene(
        layout_hints=[LayoutHint(component="calendar", position="left")],
        info_type="calendar",
        target_devices=["device-uuid"],
        user_id="user-uuid",
        user_request="calendar on the left",
        db=db,
    )
"""

import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from uuid import uuid4

from sqlalchemy.orm import Session

from app.ai.scene.schemas import (
    SceneGraph,
    SceneComponent,
    LayoutSpec,
    LayoutIntent,
    LayoutEngine,
    ComponentPriority,
    ComponentPosition,
    ComponentStyle,
    LayoutHint,
    SceneMetadata,
    GlobalStyle,
)
from app.ai.scene.registry import component_registry
from app.ai.providers.gemini import gemini_provider


logger = logging.getLogger("jarvis.ai.scene.service")


# ---------------------------------------------------------------------------
# POSITION KEYWORDS
# ---------------------------------------------------------------------------

POSITION_KEYWORDS = {
    "left", "right", "center", "top", "bottom", "corner",
    "top-left", "top-right", "bottom-left", "bottom-right",
    "sidebar", "main", "fullscreen",
}

SIZE_KEYWORDS = {
    "small", "large", "full", "fullscreen", "compact", "big", "tiny",
}


# ---------------------------------------------------------------------------
# SCENE SERVICE
# ---------------------------------------------------------------------------

class SceneService:
    """
    Service for generating and populating Scene Graphs.
    
    This class is responsible for:
    - Normalizing layout hints from natural language
    - Generating custom layouts via Claude
    - Fetching data for components (calendar, weather, etc.)
    - Validating Scene Graphs before sending to devices
    
    All scene-related operations go through this service.
    """
    
    def __init__(self):
        """Initialize the scene service."""
        logger.info("Scene service initialized")
    
    # -------------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -------------------------------------------------------------------------
    
    async def generate_scene(
        self,
        layout_hints: List[LayoutHint],
        info_type: str,
        target_devices: List[str],
        user_id: str,
        user_request: str,
        db: Session,
        realtime_data: Dict[str, Any] = None,
        conversation_context: Dict[str, Any] = None,
    ) -> SceneGraph:
        """
        Generate a complete Scene Graph with embedded data.
        
        This is the main entry point for scene generation. It:
        1. Attempts to generate layout via Claude
        2. Falls back to default scene if generation fails
        3. Fetches data for each component
        4. Validates the final scene
        
        Args:
            layout_hints: Normalized layout hints from user request
            info_type: Content type (calendar, weather, mixed)
            target_devices: List of device IDs to display on
            user_id: User ID for data fetching (OAuth credentials)
            user_request: Original user request for metadata
            db: Database session
            realtime_data: Pre-fetched real-time data from Gemini (Sprint 4.1)
            conversation_context: Conversation history and generated content (Sprint 4.2)
            
        Returns:
            Complete SceneGraph ready for sending to device
        """
        logger.info(
            f"Generating scene",
            extra={
                "info_type": info_type,
                "hint_count": len(layout_hints),
                "device_count": len(target_devices),
                "has_conversation_context": conversation_context is not None,
            }
        )
        
        from app.core.config import settings
        
        scene = None
        generated_by = "unknown"
        last_validation_error = None
        last_invalid_json = None
        
        # Sprint 5.1.2: Try Gemini 3 Flash first (faster, native JSON schema)
        try:
            scene = await self._generate_layout_via_gemini(
                hints=layout_hints,
                info_type=info_type,
                user_request=user_request,
                target_devices=target_devices,
                realtime_data=realtime_data or {},
                conversation_context=conversation_context or {},
            )
            generated_by = "gemini_3_flash"
            
            # Validate generated scene
            if scene:
                is_valid, error = self._validate_scene(scene)
                if not is_valid:
                    logger.warning(f"Gemini scene validation failed: {error}, attempting repair")
                    last_validation_error = error
                    scene = None
                    
        except Exception as e:
            logger.warning(f"Gemini scene generation failed: {e}, attempting repair")
            last_validation_error = str(e)
            scene = None
        
        # Sprint 5.1.2: Intelligent repair with Gemini (NO Claude)
        if scene is None:
            if getattr(settings, 'JSON_REPAIR_ENABLED', True):
                try:
                    scene = await self._repair_scene_with_gemini(
                        validation_error=last_validation_error,
                        invalid_json=last_invalid_json,
                        hints=layout_hints,
                        info_type=info_type,
                        user_request=user_request,
                        target_devices=target_devices,
                        realtime_data=realtime_data or {},
                        conversation_context=conversation_context or {},
                    )
                    if scene:
                        generated_by = "gemini_3_flash_repaired"
                except Exception as e:
                    logger.warning(f"Scene repair failed: {e}")
        
        # Final fallback to default template
        if scene is None:
            scene = await self._get_fallback_scene(
                info_type=info_type,
                layout_hints=layout_hints,
                target_devices=target_devices,
                user_request=user_request,
            )
            generated_by = "default_template"
        
        # Apply default styles to any components with null/missing styles
        scene = self._apply_default_styles(scene)
        
        # Populate data for all components
        scene = await self.populate_scene_data(
            scene=scene,
            user_id=user_id,
            db=db,
        )
        
        logger.info(
            f"Scene generated successfully",
            extra={
                "scene_id": scene.scene_id,
                "component_count": len(scene.components),
                "layout_intent": scene.layout.intent.value,
            }
        )
        
        return scene

    # -------------------------------------------------------------------------
    # CONTENT DATA GENERATION (Sprint 7 - Skip SceneGraph)
    # -------------------------------------------------------------------------

    async def generate_content_data(
        self,
        user_request: str,
        layout_hints: List[LayoutHint] = None,
        realtime_data: Dict[str, Any] = None,
        conversation_context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """
        Generate content data for Opus WITHOUT SceneGraph structure.

        This is a faster alternative to generate_scene() that skips the
        SceneGraph format and returns raw content data that Opus can use
        directly for HTML generation.

        Args:
            user_request: Original user request
            layout_hints: Optional layout hints
            realtime_data: Pre-fetched real-time data
            conversation_context: Conversation history

        Returns:
            Dict with content_type, title, and data fields

        Raises:
            Exception: If content generation fails
        """
        from app.core.config import settings

        # Build a simpler prompt for content generation (no SceneGraph structure)
        hints_str = ""
        if layout_hints:
            hints_str = f"\nLayout hints: {', '.join(h.raw_hint or h.component for h in layout_hints)}"

        realtime_str = ""
        if realtime_data:
            # Sanitize external real-time data before embedding in LLM prompt
            from app.services.external_data_sanitizer import external_data_sanitizer
            sanitized_realtime = external_data_sanitizer.sanitize_dict(
                realtime_data, source="scene_service.realtime_data"
            )
            realtime_str = f"\n\nReal-time data available:\n{json.dumps(sanitized_realtime, ensure_ascii=False, indent=2, default=str)}"

        context_str = ""
        if conversation_context:
            context_parts = []

            # Include conversation history for topic context
            if "history" in conversation_context and conversation_context["history"]:
                history = conversation_context["history"]
                # Format recent conversation turns (last 3-5 turns for context)
                recent_turns = history[-5:] if len(history) > 5 else history
                history_text = []
                for turn in recent_turns:
                    if isinstance(turn, dict):
                        user_msg = turn.get("user", turn.get("user_message", ""))
                        assistant_msg = turn.get("assistant", turn.get("assistant_response", ""))
                        if user_msg:
                            history_text.append(f"User: {user_msg[:200]}")
                        if assistant_msg:
                            history_text.append(f"Assistant: {assistant_msg[:400]}")
                if history_text:
                    context_parts.append(
                        "⚠️ CONVERSATION CONTEXT — Your content MUST be about THIS topic:\n"
                        + "\n".join(history_text)
                    )

            # Include last assistant response for immediate context
            if "last_response" in conversation_context and conversation_context["last_response"]:
                last_resp = conversation_context["last_response"]
                if isinstance(last_resp, str) and last_resp.strip():
                    context_parts.append(f"Last assistant response (use this for topic details):\n{last_resp[:500]}")

            # Include last doc content if available
            if "last_doc" in conversation_context:
                last_doc = conversation_context["last_doc"]
                if isinstance(last_doc, dict):
                    doc_title = last_doc.get("title", "")
                    doc_content = last_doc.get("content", "")
                    if doc_title or doc_content:
                        doc_parts = []
                        if doc_title:
                            doc_parts.append(f"Document title: {doc_title}")
                        if doc_content:
                            doc_parts.append(f"Document content:\n{doc_content[:800]}")
                        context_parts.append("Referenced document:\n" + "\n".join(doc_parts))

            # Include generated content if available
            if "generated_content" in conversation_context:
                gen_content = conversation_context["generated_content"]
                # generated_content is a Dict with 'content', 'type', 'title' keys
                if isinstance(gen_content, dict):
                    content_text = gen_content.get("content", "")
                    content_type = gen_content.get("type", "")
                    content_title = gen_content.get("title", "")
                    context_parts.append(f"Previous content ({content_type}): {content_title}\n{str(content_text)[:500]}")
                elif isinstance(gen_content, str):
                    context_parts.append(f"Previous generated content:\n{gen_content[:500]}")
                else:
                    context_parts.append(f"Previous generated content:\n{str(gen_content)[:500]}")

            if context_parts:
                context_str = "\n\n" + "\n\n".join(context_parts)

        prompt = f"""Generate content data for this display request:

REQUEST: "{user_request}"{hints_str}{realtime_str}{context_str}

Return JSON with this structure:
{{
    "content_type": "trivia|game|visualization|calendar|weather|dashboard|info|creative",
    "title": "Display title",
    "data": {{
        // Content-specific data structure
        // For trivia: {{"questions": [{{"question": "...", "options": [...], "correct": 0}}]}}
        // For visualization: {{"elements": [...], "animations": [...]}}
        // For calendar: {{"events": [...]}}
        // etc.
    }}
}}

IMPORTANT:
- Generate COMPLETE data, not placeholders
- For trivia/quiz: include 5-10 real questions with answers
- For visualizations: include all elements needed
- For games: include game state and rules
- ⚠️ CRITICAL: If CONVERSATION CONTEXT is provided above, your content MUST be about that specific topic. Do NOT generate content about a different or random topic. The user is referring to what was discussed in the conversation. Use the actual data, dates, events, and details from the conversation context.
- Match the language of the user request"""

        logger.info(f"Generating content data (skip SceneGraph) for: {user_request[:50]}...")
        logger.info(
            f"[CONTEXT_DEBUG] generate_content_data: "
            f"conversation_context keys={list(conversation_context.keys()) if conversation_context else 'None'}, "
            f"context_str_len={len(context_str)}"
        )
        if context_str:
            logger.info(f"[CONTEXT_DEBUG] context_str preview: {context_str[:300]}...")

        response = await gemini_provider.generate(
            prompt=prompt,
            temperature=0.4,
            max_tokens=4096,
            response_mime_type="application/json",
            model_override=settings.GEMINI_REASONING_MODEL,
        )

        if not response.success:
            raise Exception(f"Content data generation failed: {response.error}")

        try:
            content_data = json.loads(response.content)

            # Handle case where Gemini returns array instead of object
            if isinstance(content_data, list):
                logger.warning("Gemini returned array instead of object, wrapping in expected structure")
                content_data = {
                    "content_type": "creative",
                    "title": user_request[:50],
                    "data": content_data
                }

            # Validate basic structure
            if not isinstance(content_data, dict):
                raise Exception(f"Expected dict, got {type(content_data).__name__}")

            if "content_type" not in content_data:
                content_data["content_type"] = "creative"
            if "title" not in content_data:
                content_data["title"] = user_request[:50]
            if "data" not in content_data:
                content_data["data"] = {}

            logger.info(
                f"Content data generated: type={content_data['content_type']}, "
                f"title={content_data['title'][:30]}"
            )

            return content_data

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse content data JSON: {e}")
            raise Exception(f"Invalid content data JSON: {e}")

    # -------------------------------------------------------------------------
    # LAYOUT HINT NORMALIZATION
    # -------------------------------------------------------------------------
    
    def normalize_layout_hints(self, hints: Union[str, List[str]]) -> List[LayoutHint]:
        """
        Convert string hints to structured LayoutHint objects.
        
        Parses natural language hints like "calendar left" or "clock corner"
        into structured LayoutHint objects with component and position.
        
        Args:
            hints: Single hint string or list of raw hint strings from intent parser
        Returns:
            List of structured LayoutHint objects
        Examples:
            normalize_layout_hints("calendar left")
            → [LayoutHint(component="calendar", position="left")]
            normalize_layout_hints(["clock corner", "weather small"])
            → [LayoutHint(component="clock", position="corner"),
               LayoutHint(component="weather", size="small")]
        """
        # Handle single string input (split by comma if needed)
        if isinstance(hints, str):
            if "," in hints:
                hints = [h.strip() for h in hints.split(",") if h.strip()]
            elif hints.strip():
                hints = [hints.strip()]
            else:
                hints = []
        result = []
        for hint in hints:
            if not hint or not hint.strip():
                continue
            parsed = self._parse_single_hint(hint.strip())
            if parsed:
                result.append(parsed)
        logger.debug(f"Normalized {len(hints)} hints to {len(result)} LayoutHints")
        return result
    
    def _parse_single_hint(self, hint: str) -> Optional[LayoutHint]:
        """
        Parse a single hint string into a LayoutHint.
        
        Pattern matching:
            "{component} {position}" - calendar left, clock right
            "{component} {size}" - weather small, calendar large
            "{component}" - just the component name
        """
        hint_lower = hint.lower().strip()
        words = hint_lower.split()
        
        if not words:
            return None
        
        component = None
        position = None
        size = None
        
        # Try to extract component, position, and size from words
        remaining_words = []
        
        for word in words:
            if word in POSITION_KEYWORDS:
                position = word
            elif word in SIZE_KEYWORDS:
                size = word
            else:
                remaining_words.append(word)
        
        # Join remaining words as component name
        if remaining_words:
            component_hint = "_".join(remaining_words)
            
            # Try to map to a specific component type
            mapped_component = component_registry.get_component_for_hint(component_hint)
            if mapped_component:
                component = mapped_component
            else:
                # Keep the original hint as component (Claude can interpret)
                component = component_hint
        
        if not component:
            # If no component found, treat the whole hint as component
            component = hint_lower.replace(" ", "_")
        
        return LayoutHint(
            component=component,
            position=position,
            size=size,
            raw_hint=hint,
        )
    
    # -------------------------------------------------------------------------
    # GEMINI 3 FLASH GENERATION (Primary)
    # -------------------------------------------------------------------------
    
    async def _generate_layout_via_gemini(
        self,
        hints: List[LayoutHint],
        info_type: str,
        user_request: str,
        target_devices: List[str],
        realtime_data: Dict[str, Any] = None,
        conversation_context: Dict[str, Any] = None,
    ) -> SceneGraph:
        """
        Use Gemini 3 Flash to generate a layout with native JSON schema support.
        
        Sprint 5.1.2: This is the new high-performance path using Gemini's 
        structured output with schema validation. Faster than Claude with
        native JSON mode.
        
        Args:
            hints: Normalized layout hints
            info_type: Content type
            user_request: Original user request
            target_devices: Target device IDs
            realtime_data: Pre-fetched real-time data from Gemini
            conversation_context: Previous conversation history and generated content
            
        Returns:
            SceneGraph from Gemini's response
            
        Raises:
            Exception: If Gemini fails or returns invalid JSON
        """
        from app.ai.prompts.scene_prompts import (
            build_scene_system_prompt,
            build_scene_generation_prompt,
        )
        from app.core.config import settings
        
        # Build prompts (reuse existing prompt logic)
        system_prompt = build_scene_system_prompt(
            components_context=component_registry.to_prompt_context()
        )
        
        # Pass realtime_data and conversation_context to prompt builder
        generation_prompt = build_scene_generation_prompt(
            user_request=user_request,
            layout_hints=hints,
            info_type=info_type,
            device_count=len(target_devices),
            realtime_data=realtime_data or {},
            conversation_context=conversation_context or {},
        )
        
        logger.debug("Calling Gemini 3 Flash for scene generation")
        
        # NOTE: We use response_mime_type="application/json" WITHOUT response_schema
        # because SceneGraph contains Dict[str, Any] fields (props, data) which
        # Gemini's structured output rejects as "should be non-empty for OBJECT type".
        # We validate the JSON ourselves after generation.
        response = await gemini_provider.generate(
            prompt=generation_prompt,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=8192,  # Increased to avoid truncation
            response_mime_type="application/json",
            model_override=settings.GEMINI_REASONING_MODEL,  # Use Gemini 3 Flash
        )
        
        if not response.success:
            raise Exception(f"Gemini generation failed: {response.error}")
        
        # Parse response into SceneGraph
        try:
            scene_data = json.loads(response.content)
            
            # Check if Gemini returned an error object
            if "error" in scene_data and "message" in scene_data:
                error_type = scene_data.get("error", "unknown_error")
                error_message = scene_data.get("message", "Unknown error")
                logger.warning(f"Gemini returned error: {error_type} - {error_message}")
                raise Exception(error_message)
            
            scene = self._parse_scene_response(
                scene_data,
                target_devices,
                user_request,
                generated_by_model="gemini_3_flash"
            )
            
            logger.info(f"Gemini scene generation successful, latency: {response.latency_ms}ms")
            return scene
            
        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parsing failed: {e}")
            logger.debug(f"Raw Gemini response: {response.content[:500]}...")
            raise Exception(f"Gemini returned invalid JSON: {e}")
        except Exception as e:
            raise Exception(f"Failed to parse Gemini response: {e}")
    
    # -------------------------------------------------------------------------
    # GEMINI REPAIR (Sprint 5.1.2)
    # -------------------------------------------------------------------------
    
    async def _repair_scene_with_gemini(
        self,
        validation_error: Optional[str],
        invalid_json: Optional[str],
        hints: List[LayoutHint],
        info_type: str,
        user_request: str,
        target_devices: List[str],
        realtime_data: Dict[str, Any],
        conversation_context: Dict[str, Any],
    ) -> Optional[SceneGraph]:
        """
        Repair failed Scene Graph using Gemini 2.5 (diagnosis) + Gemini 3 (repair).
        
        Sprint 5.1.2: This is the intelligent repair path that replaces Claude fallback.
        Uses Gemini 2.5 Flash for fast diagnosis, then Gemini 3 Flash for repair.
        
        Args:
            validation_error: The error from validation or exception
            invalid_json: The invalid JSON that was produced (if any)
            hints: Normalized layout hints
            info_type: Content type
            user_request: Original user request
            target_devices: Target device IDs
            realtime_data: Pre-fetched real-time data
            conversation_context: Conversation history and generated content
            
        Returns:
            Repaired SceneGraph or None if repair fails
        """
        from app.ai.prompts.scene_prompts import (
            build_scene_system_prompt,
            build_scene_generation_prompt,
        )
        from app.core.config import settings
        
        max_retries = getattr(settings, 'JSON_REPAIR_MAX_RETRIES', 1)
        
        for attempt in range(max_retries):
            logger.info(f"Scene repair attempt {attempt + 1}/{max_retries}")
            
            # Step 1: Diagnosis with Gemini 2.5 Flash (fast, cheap)
            diagnosis_prompt = f"""Analyze this Scene Graph error in 1-2 sentences.

ERROR: {validation_error or "Unknown error"}

INVALID JSON:
{(invalid_json or "No JSON produced")[:1500]}

What's wrong? (1-2 sentences):"""
            
            diagnosis_response = await gemini_provider.generate(
                prompt=diagnosis_prompt,
                temperature=0.1,
                max_tokens=150,
            )
            
            if not diagnosis_response.success:
                logger.warning(f"Diagnosis failed: {diagnosis_response.error}")
                continue
            
            diagnosis = diagnosis_response.content.strip()
            logger.info(f"Scene diagnosis: {diagnosis}")
            
            # Step 2: Repair with Gemini 3 Flash - same prompt + diagnosis context
            system_prompt = build_scene_system_prompt(
                components_context=component_registry.to_prompt_context()
            )
            
            generation_prompt = build_scene_generation_prompt(
                user_request=user_request,
                layout_hints=hints,
                info_type=info_type,
                device_count=len(target_devices),
                realtime_data=realtime_data,
                conversation_context=conversation_context,
            )
            
            # Add repair context to prompt
            repair_prompt = f"""{generation_prompt}

## PREVIOUS ATTEMPT FAILED
Diagnosis: {diagnosis}
Fix the issue and generate a valid Scene Graph."""
            
            # NOTE: Use response_mime_type without schema (see _generate_layout_via_gemini)
            repair_response = await gemini_provider.generate(
                prompt=repair_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=8192,  # Increased to avoid truncation
                response_mime_type="application/json",
                model_override=settings.GEMINI_REASONING_MODEL,
            )
            
            if not repair_response.success:
                logger.warning(f"Repair generation failed: {repair_response.error}")
                continue
            
            # Parse and validate
            try:
                scene_data = json.loads(repair_response.content)
                scene = self._parse_scene_response(
                    scene_data, target_devices, user_request, "gemini_3_flash_repaired"
                )
                
                is_valid, error = self._validate_scene(scene)
                if is_valid:
                    logger.info(f"Scene repair successful on attempt {attempt + 1}")
                    return scene
                
                # Update for next iteration
                validation_error = error
                invalid_json = repair_response.content
                logger.warning(f"Repaired scene still invalid: {error}")
                
            except Exception as e:
                validation_error = str(e)
                invalid_json = repair_response.content
                logger.warning(f"Repair parsing failed: {e}")
        
        logger.warning(f"Scene repair failed after {max_retries} attempts")
        return None
    
    # -------------------------------------------------------------------------
    # CLAUDE GENERATION (Legacy - kept for backwards compatibility)
    # -------------------------------------------------------------------------
    
    async def _generate_layout_via_claude(
        self,
        hints: List[LayoutHint],
        info_type: str,
        user_request: str,
        target_devices: List[str],
        realtime_data: Dict[str, Any] = None,
        conversation_context: Dict[str, Any] = None,
    ) -> SceneGraph:
        """
        Generate a creative layout using Gemini.

        Sprint 9: Migrated from Claude to Gemini 3 Flash with thinking mode.

        NOTE: This method is kept for backwards compatibility but is no longer
        used in the main flow. Gemini 3 Flash + repair is now the primary path.

        Builds a prompt with component registry context and calls
        gemini_provider.generate_json() to get the scene structure.

        Sprint 4.1: Now accepts realtime_data to embed in components.
        Sprint 4.2: Now accepts conversation_context for multi-turn awareness.

        Args:
            hints: Normalized layout hints
            info_type: Content type
            user_request: Original user request
            target_devices: Target device IDs
            realtime_data: Pre-fetched real-time data from Gemini
            conversation_context: Previous conversation history and generated content

        Returns:
            SceneGraph from Gemini's response

        Raises:
            Exception: If Gemini fails or returns invalid JSON
        """
        from app.ai.providers import gemini_provider
        from app.ai.prompts.scene_prompts import (
            build_scene_system_prompt,
            build_scene_generation_prompt,
        )

        # Build prompts
        system_prompt = build_scene_system_prompt(
            components_context=component_registry.to_prompt_context()
        )

        # Sprint 4.1: Pass realtime_data to prompt builder
        # Sprint 4.2: Pass conversation_context for multi-turn awareness
        generation_prompt = build_scene_generation_prompt(
            user_request=user_request,
            layout_hints=hints,
            info_type=info_type,
            device_count=len(target_devices),
            realtime_data=realtime_data or {},
            conversation_context=conversation_context or {},
        )

        logger.debug("Calling Gemini for scene generation")

        # Sprint 9: Call Gemini with thinking mode
        response = await gemini_provider.generate_json(
            prompt=generation_prompt,
            system_prompt=system_prompt,
        )

        if not response.success:
            raise Exception(f"Gemini generation failed: {response.error}")
        
        # Parse response into SceneGraph
        try:
            scene_data = json.loads(response.content)

            # Sprint 5.1.1: Check if Gemini returned an error object
            if "error" in scene_data and "message" in scene_data:
                error_type = scene_data.get("error", "unknown_error")
                error_message = scene_data.get("message", "Unknown error")
                logger.warning(f"Gemini returned error: {error_type} - {error_message}")
                raise Exception(error_message)

            scene = self._parse_scene_response(
                scene_data,
                target_devices,
                user_request,
                generated_by_model=response.model  # Pass actual model used
            )
            return scene
        except json.JSONDecodeError as e:
            logger.error(f"Gemini JSON parsing failed: {e}")
            logger.debug(f"Raw Gemini response: {response.content[:500]}...")

            # Try to clean common JSON errors
            try:
                # Remove trailing commas
                cleaned_content = re.sub(r',(\s*[}\]])', r'\1', response.content)
                # Fix unterminated strings (basic attempt)
                cleaned_content = re.sub(r'(["\'])\s*\n\s*}', r'\1}', cleaned_content)

                scene_data = json.loads(cleaned_content)
                logger.info("Recovered from JSON error with cleaning")
                scene = self._parse_scene_response(scene_data, target_devices, user_request, response.model)
                return scene
            except Exception as retry_error:
                logger.error(f"JSON cleanup failed: {retry_error}")
                raise Exception(f"Claude returned invalid JSON: {e}")
        except Exception as e:
            raise Exception(f"Failed to parse Claude response: {e}")
    
    def _parse_scene_response(
        self,
        data: Dict[str, Any],
        target_devices: List[str],
        user_request: str,
        generated_by_model: Optional[str] = None,
    ) -> SceneGraph:
        """
        Parse Claude's JSON response into a SceneGraph.
        
        Handles various formats Claude might return and normalizes
        them into our SceneGraph structure.
        """
        # Extract layout
        layout_data = data.get("layout", {})
        layout = LayoutSpec(
            intent=LayoutIntent(layout_data.get("intent", "fullscreen")),
            engine=LayoutEngine(layout_data.get("engine", "grid")),
            columns=layout_data.get("columns"),
            rows=layout_data.get("rows"),
            gap=layout_data.get("gap", "16px"),
        )
        
        # Extract components
        components = []
        for comp_data in data.get("components", []):
            position_data = comp_data.get("position", {})
            style_data = comp_data.get("style", {})
            
            component = SceneComponent(
                id=comp_data.get("id", f"component_{len(components)}"),
                type=comp_data.get("type", "text_block"),
                priority=ComponentPriority(comp_data.get("priority", "secondary")),
                position=ComponentPosition(
                    grid_column=position_data.get("grid_column"),
                    grid_row=position_data.get("grid_row"),
                    flex=position_data.get("flex"),
                    top=position_data.get("top"),
                    right=position_data.get("right"),
                    bottom=position_data.get("bottom"),
                    left=position_data.get("left"),
                ),
                style=ComponentStyle(
                    background=style_data.get("background", "#1a1a2e"),
                    text_color=style_data.get("text_color", "#ffffff"),
                    accent_color=style_data.get("accent_color"),
                    border_radius=style_data.get("border_radius", "12px"),
                    border=style_data.get("border"),
                    padding=style_data.get("padding", "16px"),
                    shadow=style_data.get("shadow"),
                    opacity=style_data.get("opacity"),
                ),
                props=comp_data.get("props", {}),
                # Sprint 4.1: Preserve real-time data from Claude if provided
                data=comp_data.get("data", {}),
            )
            components.append(component)
        
        # Extract global style
        global_style_data = data.get("global_style", {})
        global_style = GlobalStyle(
            background=global_style_data.get("background", "#0f0f23"),
            font_family=global_style_data.get("font_family", "Inter"),
            text_color=global_style_data.get("text_color", "#ffffff"),
        )
        
        # Build metadata
        metadata = SceneMetadata(
            user_request=user_request,
            generated_by=generated_by_model or "claude",  # Use actual model name
            refresh_seconds=data.get("metadata", {}).get("refresh_seconds", 300),
        )
        
        return SceneGraph(
            scene_id=data.get("scene_id", str(uuid4())),
            version=data.get("version", "1.1"),
            target_devices=target_devices,
            layout=layout,
            components=components,
            global_style=global_style,
            metadata=metadata,
        )
    
    # -------------------------------------------------------------------------
    # FALLBACK SCENE
    # -------------------------------------------------------------------------
    
    async def _get_fallback_scene(
        self,
        info_type: str,
        layout_hints: List[LayoutHint],
        target_devices: List[str],
        user_request: str,
    ) -> SceneGraph:
        """
        Get a fallback scene when Claude generation fails.

        Sprint 4.4.0: If detect_default_scene_type returns None (content generation needed),
        we raise an exception instead of using a default - custom layouts MUST use Claude.

        Uses default scenes from the defaults module.
        """
        from app.ai.scene.defaults import (
            detect_default_scene_type,
            get_default_scene_template,
            DefaultSceneType,
        )

        # Convert hints to strings for detection
        hint_strings = [h.raw_hint or h.component for h in layout_hints]

        # Detect best default scene (Sprint 4.4.0: pass user_request for generation keyword detection)
        scene_type = detect_default_scene_type(
            info_type=info_type,
            layout_hints=hint_strings,
            user_request=user_request,
        )

        # Sprint 4.4.0: If None is returned, content generation is needed - no fallback allowed
        if scene_type is None:
            logger.error(f"Cannot use fallback for custom content generation request: {user_request[:100]}")
            raise Exception(
                "This request requires custom content generation (Claude). "
                "Fallback defaults cannot handle generated content like plans, summaries, etc. "
                "The Claude generation must succeed for this request."
            )

        # Get template
        return get_default_scene_template(
            scene_type=scene_type,
            target_devices=target_devices,
            user_request=user_request,
        )
    
    # -------------------------------------------------------------------------
    # DATA POPULATION
    # -------------------------------------------------------------------------
    
    async def populate_scene_data(
        self,
        scene: SceneGraph,
        user_id: str,
        db: Session,
    ) -> SceneGraph:
        """
        Populate data for all components in a scene.
        
        Fetches actual data (calendar events, weather, etc.) and
        embeds it in each component's data field.
        
        Sprint 4.1: Skips components that already have real-time data from Gemini.
        
        Args:
            scene: SceneGraph with empty component data
            user_id: User ID for OAuth credentials
            db: Database session
            
        Returns:
            SceneGraph with populated data
        """
        for component in scene.components:
            # Sprint 4.1: Skip if component already has real-time data from Gemini
            if component.data and not component.data.get("is_placeholder", True):
                logger.info(
                    f"Component {component.id} ({component.type}) already has real-time data, skipping fetch"
                )
                continue
            
            try:
                data = await self._fetch_component_data(
                    component_type=component.type,
                    props=component.props,
                    user_id=user_id,
                    db=db,
                )
                component.data = data
            except Exception as e:
                logger.warning(
                    f"Failed to fetch data for component {component.id}: {e}",
                    extra={"component_type": component.type}
                )
                # Set error state in data
                component.data = {"error": str(e)}
        
        return scene
    
    async def _fetch_component_data(
        self,
        component_type: str,
        props: Dict[str, Any],
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Fetch actual data for a component.
        
        Routes to the appropriate data fetcher based on component type.
        """
        # Calendar components
        if component_type.startswith("calendar"):
            return await self._fetch_calendar_data(
                component_type=component_type,
                props=props,
                user_id=user_id,
                db=db,
            )
        
        # Meeting detail component (single event with full details)
        if component_type == "meeting_detail":
            return await self._fetch_meeting_detail(
                props=props,
                user_id=user_id,
                db=db,
            )
        
        # Countdown/Timer components
        if component_type in ("countdown_timer", "event_countdown"):
            return await self._fetch_countdown_data(
                component_type=component_type,
                props=props,
                user_id=user_id,
                db=db,
            )
        
        # Document components (Google Docs)
        if component_type in ("doc_summary", "doc_preview"):
            return await self._fetch_doc_data(
                component_type=component_type,
                props=props,
                user_id=user_id,
                db=db,
            )
        
        # Clock components
        if component_type.startswith("clock"):
            return await self._fetch_clock_data(props)
        
        # Weather components
        if component_type.startswith("weather"):
            return await self._fetch_weather_data(props)
        
        # Text block
        if component_type == "text_block":
            return {"content": props.get("content", "")}
        
        # Spacer (no data needed)
        if component_type == "spacer":
            return {}
        
        # Image display
        if component_type == "image_display":
            return {"url": props.get("url", ""), "alt": props.get("alt_text", "")}
        
        # Web embed
        if component_type == "web_embed":
            return {"url": props.get("url", "")}
        
        # Unknown component type
        logger.warning(f"No data fetcher for component type: {component_type}")
        return {}
    
    async def _fetch_calendar_data(
        self,
        component_type: str,
        props: Dict[str, Any],
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Fetch calendar events using GoogleCalendarClient.
        
        Determines date range from component_type and props,
        fetches events, and formats for frontend.
        """
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        
        # Get OAuth credentials
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return {
                "error": "Google Calendar not connected",
                "events": [],
            }
        
        # Create calendar client
        calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
        
        # Determine date range based on component type
        now = datetime.now(timezone.utc)
        
        if component_type == "calendar_day":
            # Single day
            date_str = props.get("date")
            if date_str:
                try:
                    target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except ValueError:
                    target_date = now
            else:
                target_date = now
            
            time_min = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = time_min + timedelta(days=1)
            max_results = 50
            
        elif component_type == "calendar_week":
            # Full week (7 days)
            time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
            time_max = time_min + timedelta(days=7)
            max_results = 100
            
        elif component_type == "calendar_month":
            # Full month (roughly 30 days)
            month = props.get("month", now.month)
            year = props.get("year", now.year)
            time_min = datetime(year, month, 1, tzinfo=timezone.utc)
            if month == 12:
                time_max = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                time_max = datetime(year, month + 1, 1, tzinfo=timezone.utc)
            max_results = 200
            
        elif component_type in ("calendar_widget", "calendar_agenda"):
            # Upcoming events
            time_min = now
            time_max = now + timedelta(days=14)  # Next 2 weeks
            max_results = props.get("max_events", 10)
            
        else:
            # Default: next 7 days
            time_min = now
            time_max = now + timedelta(days=7)
            max_results = 50
        
        # Fetch events
        try:
            events = await calendar_client.list_upcoming_events(
                time_min=time_min,
                time_max=time_max,
                max_results=max_results,
            )
            
            # Format events for frontend
            formatted_events = []
            for event in events:
                formatted_events.append({
                    "id": event.id,
                    "title": event.get_display_title(),
                    "start": event.start.date_time.isoformat() if event.start.date_time else event.start.date,
                    "end": event.end.date_time.isoformat() if event.end.date_time else event.end.date,
                    "is_all_day": event.start.is_all_day(),
                    "location": event.location,
                    "color": event.color_id or "#4285f4",
                })
            
            return {
                "events": formatted_events,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "time_range": {
                    "start": time_min.isoformat(),
                    "end": time_max.isoformat(),
                },
            }
            
        except Exception as e:
            logger.error(f"Failed to fetch calendar events: {e}")
            return {
                "error": str(e),
                "events": [],
            }
    
    async def _fetch_clock_data(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get clock data (timezone, etc.).
        
        Clocks are mostly client-rendered, but we provide timezone info.
        """
        # Default to user's timezone or UTC
        # In a real implementation, this would come from user preferences
        return {
            "timezone": props.get("timezone", "America/New_York"),
            "format": props.get("format", "12h"),
        }
    
    async def _fetch_weather_data(self, props: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get weather data (fallback only).
        
        Sprint 4.1: Weather data should be provided by Gemini BEFORE scene generation
        via the realtime_data parameter. This method now only returns a minimal 
        placeholder if data wasn't pre-fetched.
        
        If you see is_placeholder=True, it means the intent service didn't fetch
        real-time data before calling generate_scene().
        """
        logger.warning(
            f"Weather component created without pre-fetched data for location "
            f"'{props.get('location', 'unknown')}'. "
            "Gemini should fetch weather BEFORE scene generation for real-time accuracy."
        )
        
        return {
            "temperature": None,
            "condition": "unknown",
            "icon": "unknown",
            "location": props.get("location", "Unknown"),
            "humidity": None,
            "wind_speed": None,
            "units": props.get("units", "fahrenheit"),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "is_placeholder": True,
            "error": "No real-time data provided to scene generation",
        }
    
    async def _fetch_meeting_detail(
        self,
        props: Dict[str, Any],
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Fetch details for a single meeting/event.

        Can fetch by event_id, meeting_search, or get the next upcoming event.
        Sprint 4.3.2: Added meeting_search support to find events by title/keywords.
        """
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient

        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()

        if not credentials:
            return {"error": "Google Calendar not connected"}

        calendar_client = GoogleCalendarClient(access_token=credentials.access_token)

        # If specific event_id provided, fetch that event
        event_id = props.get("event_id")
        if event_id:
            try:
                event = await calendar_client.get_event(event_id)
                return self._format_event_detail(event)
            except Exception as e:
                logger.error(f"Failed to fetch event {event_id}: {e}")
                return {"error": str(e)}

        # Sprint 4.3.2: If meeting_search provided, search for event by title/keywords
        meeting_search = props.get("meeting_search")
        if meeting_search:
            try:
                from app.services.calendar_search_service import calendar_search_service
                from uuid import UUID

                # Use smart_search to find the event
                # Sprint 5.1.1: Fix - search in more events, return first match
                search_result = await calendar_search_service.smart_search(
                    user_query=meeting_search,
                    user_id=UUID(user_id),
                    db=db,
                    max_events=50,
                )

                if search_result.events:
                    return self._format_event_detail(search_result.events[0])
                else:
                    logger.warning(f"No event found for meeting_search: {meeting_search}")
                    return {"error": f"No event found matching '{meeting_search}'"}
            except Exception as e:
                logger.error(f"Failed to search for meeting '{meeting_search}': {e}")
                return {"error": str(e)}

        # Otherwise, get next upcoming event
        try:
            now = datetime.now(timezone.utc)
            events = await calendar_client.list_upcoming_events(
                time_min=now,
                time_max=now + timedelta(days=7),
                max_results=1,
            )
            
            if events:
                return self._format_event_detail(events[0])
            else:
                return {
                    "empty": True,
                    "message": "No upcoming events",
                }
        except Exception as e:
            logger.error(f"Failed to fetch next event: {e}")
            return {"error": str(e)}
    
    def _format_event_detail(self, event) -> Dict[str, Any]:
        """Format a calendar event for the meeting_detail component."""
        # Handle attendees - could be list of objects or list of dicts
        attendees = []
        for a in (event.attendees or []):
            if hasattr(a, 'email'):
                attendees.append(a.email)
            elif isinstance(a, dict) and 'email' in a:
                attendees.append(a['email'])
        
        # Handle organizer - could be object or dict
        organizer = None
        if event.organizer:
            if hasattr(event.organizer, 'email'):
                organizer = event.organizer.email
            elif isinstance(event.organizer, dict) and 'email' in event.organizer:
                organizer = event.organizer['email']
        
        # Handle title - could be method or attribute
        if hasattr(event, 'get_display_title'):
            title = event.get_display_title()
        else:
            title = getattr(event, 'summary', None) or getattr(event, 'title', 'Untitled')
        
        # Handle start/end times - could be objects or dicts
        start_time = None
        end_time = None
        is_all_day = False
        
        if hasattr(event.start, 'date_time') and event.start.date_time:
            start_time = event.start.date_time.isoformat()
            is_all_day = False
        elif hasattr(event.start, 'date'):
            start_time = event.start.date
            is_all_day = True
        
        if hasattr(event.end, 'date_time') and event.end.date_time:
            end_time = event.end.date_time.isoformat()
        elif hasattr(event.end, 'date'):
            end_time = event.end.date
        
        # Check is_all_day method if available
        if hasattr(event.start, 'is_all_day'):
            is_all_day = event.start.is_all_day()
        
        return {
            "event_id": event.id,
            "title": title,
            "start_time": start_time,
            "end_time": end_time,
            "is_all_day": is_all_day,
            "location": getattr(event, 'location', None),
            "description": getattr(event, 'description', None),
            "attendees": attendees,
            "organizer": organizer,
            "html_link": getattr(event, 'html_link', None),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    
    async def _fetch_countdown_data(
        self,
        component_type: str,
        props: Dict[str, Any],
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Fetch countdown/timer data.
        
        For event_countdown: fetches next event and calculates time until.
        For countdown_timer: can use custom target_time or next event.
        """
        now = datetime.now(timezone.utc)
        
        # If custom target_time provided
        target_time_str = props.get("target_time")
        if target_time_str:
            try:
                target_time = datetime.fromisoformat(target_time_str.replace("Z", "+00:00"))
                time_until = target_time - now
                return {
                    "target_time": target_time.isoformat(),
                    "target_label": props.get("label", "Countdown"),
                    "seconds_until": max(0, int(time_until.total_seconds())),
                    "is_past": time_until.total_seconds() < 0,
                }
            except ValueError as e:
                return {"error": f"Invalid target_time format: {e}"}
        
        # Auto-fetch next event for countdown
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.calendar.client import GoogleCalendarClient
        
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return {"error": "Google Calendar not connected", "seconds_until": 0}
        
        try:
            calendar_client = GoogleCalendarClient(access_token=credentials.access_token)
            events = await calendar_client.list_upcoming_events(
                time_min=now,
                time_max=now + timedelta(days=7),  # Match meeting_detail window
                max_results=1,
            )
            
            if events:
                event = events[0]
                
                # Handle start time - could be object or dict pattern
                event_start = None
                if hasattr(event.start, 'date_time') and event.start.date_time:
                    event_start = event.start.date_time
                elif hasattr(event.start, 'date') and event.start.date:
                    event_start = datetime.fromisoformat(event.start.date) if isinstance(event.start.date, str) else event.start.date
                
                if event_start and not getattr(event_start, 'tzinfo', None):
                    event_start = event_start.replace(tzinfo=timezone.utc)
                
                # Handle title - could be method or attribute
                if hasattr(event, 'get_display_title'):
                    event_title = event.get_display_title()
                else:
                    event_title = getattr(event, 'summary', None) or getattr(event, 'title', 'Event')
                
                time_until = event_start - now if event_start else timedelta(0)
                return {
                    "target_time": event_start.isoformat() if event_start else None,
                    "target_label": event_title,
                    "seconds_until": max(0, int(time_until.total_seconds())),
                    "is_past": time_until.total_seconds() < 0,
                    "next_event": {
                        "id": event.id,
                        "title": event_title,
                        "location": getattr(event, 'location', None),
                    },
                }
            else:
                return {
                    "empty": True,
                    "message": "No upcoming events",
                    "seconds_until": 0,
                }
        except Exception as e:
            logger.error(f"Failed to fetch next event for countdown: {e}")
            return {"error": str(e), "seconds_until": 0}
    
    async def _extract_doc_from_event(
        self,
        credentials,
        meeting_search: Optional[str] = None,
        event_id: Optional[str] = None,
        user_id: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> Optional[str]:
        """
        Extract a Google Doc URL from a calendar event.
        
        Uses the meeting_link_service which has semantic search capabilities
        to find the meeting and extract linked documents from:
        - Extended properties
        - Attachments  
        - Description links
        
        Args:
            credentials: OAuth credentials (unused - kept for backwards compat)
            meeting_search: Search term to find the meeting
            event_id: Specific event ID to fetch
            user_id: User ID for meeting_link_service
            db: Database session for meeting_link_service
            
        Returns:
            Google Docs URL if found, None otherwise
        """
        from uuid import UUID
        from app.services.meeting_link_service import meeting_link_service
        
        # Need user_id and db for meeting_link_service
        if not user_id or not db:
            logger.warning("_extract_doc_from_event: user_id and db required for meeting search")
            return None
        
        try:
            # Convert user_id to UUID if string
            uid = UUID(user_id) if isinstance(user_id, str) else user_id
            
            if event_id:
                # For specific event_id, we'd need get_linked_doc but it's not fully implemented
                # Fall back to search using the event details
                logger.info(f"Fetching doc for event_id: {event_id}")
                # TODO: Implement event_id lookup when needed
                return None
            
            if meeting_search:
                # Use meeting_link_service which has semantic search
                result = await meeting_link_service.find_meeting_with_doc(
                    query=meeting_search,
                    user_id=uid,
                    db=db,
                )
                
                if result.found and result.doc_id:
                    doc_url = f"https://docs.google.com/document/d/{result.doc_id}/edit"
                    logger.info(f"Found doc for meeting '{meeting_search}': {doc_url[:50]}...")
                    return doc_url
                elif result.found and not result.has_linked_doc:
                    logger.warning(f"Meeting found but no linked doc for '{meeting_search}'")
                    return None
                else:
                    logger.warning(f"No meeting found for '{meeting_search}': {result.error}")
                    return None
            
            logger.warning("_extract_doc_from_event: need meeting_search or event_id")
            return None
            
        except Exception as e:
            logger.error(f"Failed to extract doc from event: {e}")
            return None
    
    async def _generate_custom_content(
        self,
        doc_text: str,
        doc_title: str,
        content_request: str,
        content_type: str = "custom",
    ) -> Dict[str, Any]:
        """
        Generate custom AI content from a document based on user request.
        
        Uses Gemini for speed (most content generation is straightforward).
        Falls back to Claude for complex documents.
        
        Args:
            doc_text: The document's plain text content
            doc_title: Document title for context
            content_request: Natural language description of what to generate
            content_type: Category hint (impact_phrases, script, key_points, etc.)
            
        Returns:
            Dict with generated_content and metadata
        """
        from app.ai.providers.gemini import gemini_provider
        
        # Truncate doc text to fit context (max ~8000 chars for Gemini)
        max_doc_chars = 8000
        truncated_text = doc_text[:max_doc_chars]
        if len(doc_text) > max_doc_chars:
            truncated_text += "\n\n[Document truncated...]"
        
        # Build the generation prompt
        prompt = f"""Based on this document, {content_request}

Document Title: {doc_title}

Document Content:
{truncated_text}

---

Instructions:
- Be concise and actionable
- Format appropriately for display on a TV screen (large text, clear structure)
- Use bullet points or numbered lists when appropriate
- Keep responses under 500 words
- Language: Match the language of the document or user request

Generate the requested content now:"""
        
        try:
            logger.info(f"Generating custom content: {content_request[:50]}...")
            
            response = await gemini_provider.generate(
                prompt=prompt,
                temperature=0.4,  # Slightly creative but controlled
                max_tokens=1024,
            )
            
            if response.success and response.content:
                logger.info(f"Generated {len(response.content)} chars of custom content")
                return {
                    "generated_content": response.content,
                    "content_type": content_type,
                    "content_request": content_request,
                    "model_used": "gemini",
                }
            else:
                logger.warning(f"AI generation failed: {response.error}")
                return {
                    "generated_content": None,
                    "generation_error": response.error or "Generation failed",
                }
                
        except Exception as e:
            logger.error(f"Failed to generate custom content: {e}")
            return {
                "generated_content": None,
                "generation_error": str(e),
            }
    
    async def _fetch_doc_data(
        self,
        component_type: str,
        props: Dict[str, Any],
        user_id: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        Fetch Google Doc data for doc_summary or doc_preview components.
        
        Supports multiple ways to find the document:
        1. Direct doc_id or doc_url in props
        2. meeting_search - search for a meeting and extract doc from description
        3. event_id - fetch specific event and extract doc from description
        
        If content_request prop is specified, uses AI to generate custom content.
        """
        import re
        from app.models.oauth_credential import OAuthCredential
        from app.environments.google.docs.client import GoogleDocsClient
        
        credentials = db.query(OAuthCredential).filter(
            OAuthCredential.user_id == user_id,
            OAuthCredential.provider == "google",
        ).first()
        
        if not credentials:
            return {"error": "Google Docs not connected"}
        
        doc_id = props.get("doc_id")
        doc_url = props.get("doc_url")
        
        # If no direct doc reference, try to find via meeting
        if not doc_id and not doc_url:
            meeting_search = props.get("meeting_search")
            event_id = props.get("event_id")
            
            if meeting_search or event_id:
                doc_url = await self._extract_doc_from_event(
                    credentials=credentials,
                    meeting_search=meeting_search,
                    event_id=event_id,
                    user_id=user_id,
                    db=db,
                )
                if not doc_url:
                    return {"error": f"No document found linked to meeting '{meeting_search or event_id}'"}
        
        # Extract doc_id from URL if provided
        if doc_url and not doc_id:
            # Pattern: /document/d/{doc_id}/
            match = re.search(r'/document/d/([a-zA-Z0-9_-]+)', doc_url)
            if match:
                doc_id = match.group(1)
        
        if not doc_id:
            return {"error": "No document ID or URL provided"}
        
        try:
            docs_client = GoogleDocsClient(access_token=credentials.access_token)
            doc = await docs_client.get_document(doc_id)
            
            # Get the plain text content from the document
            text_content = doc.get_plain_text()
            
            # Check if AI content generation is requested
            content_request = props.get("content_request")
            content_type = props.get("content_type", "custom")
            
            # Base response data (always included)
            base_data = {
                "doc_id": doc_id,
                "title": doc.title,
                "url": f"https://docs.google.com/document/d/{doc_id}",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
            
            # If content_request is specified, use AI to generate custom content
            if content_request:
                logger.info(f"AI content generation requested: {content_request[:50]}...")
                
                ai_result = await self._generate_custom_content(
                    doc_text=text_content,
                    doc_title=doc.title,
                    content_request=content_request,
                    content_type=content_type,
                )
                
                # Merge AI result with base data
                base_data.update(ai_result)
                
                # If AI generation succeeded, also include a fallback summary
                if ai_result.get("generated_content"):
                    # Include minimal fallback data
                    base_data["summary"] = text_content[:500] + "..." if len(text_content) > 500 else text_content
                else:
                    # AI failed - fall back to standard content
                    logger.warning("AI generation failed, falling back to standard content")
                    base_data["summary"] = text_content[:1500] + "..." if len(text_content) > 1500 else text_content
                
                return base_data
            
            # No AI request - build response based on component type
            if component_type == "doc_summary":
                # Create a summary from the document
                # Use max_chars from props, default to 1500 for a good summary length
                max_summary_chars = props.get("max_chars", 1500)
                summary = text_content[:max_summary_chars] + "..." if len(text_content) > max_summary_chars else text_content
                
                # Try to extract key points (simple heuristic: lines starting with -, •, or numbers)
                lines = text_content.split('\n')
                key_points = []
                for line in lines:
                    stripped = line.strip()
                    if stripped and (
                        stripped.startswith('-') or 
                        stripped.startswith('•') or 
                        stripped.startswith('*') or
                        (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)')
                    ):
                        # Clean up the bullet point
                        point = stripped.lstrip('-•* ').lstrip('0123456789.)').strip()
                        if point and len(point) > 5:  # Ignore very short points
                            key_points.append(point)
                        if len(key_points) >= 5:  # Max 5 key points
                            break
                
                base_data.update({
                    "summary": summary,
                    "key_points": key_points,
                    "last_modified": None,  # GoogleDoc doesn't have modified_time
                })
                return base_data
                
            else:  # doc_preview
                max_chars = props.get("max_chars", 1000)
                preview_text = text_content[:max_chars]
                if len(text_content) > max_chars:
                    preview_text += "..."
                    
                base_data.update({
                    "preview_text": preview_text,
                })
                return base_data
                
        except Exception as e:
            logger.error(f"Failed to fetch document {doc_id}: {e}")
            return {"error": str(e)}
    
    # -------------------------------------------------------------------------
    # STYLE DEFAULTS
    # -------------------------------------------------------------------------
    
    def _apply_default_styles(self, scene: SceneGraph) -> SceneGraph:
        """
        Apply default styles to components and global_style when missing.
        
        Claude sometimes returns null for style fields. This ensures all
        components have proper styling for a professional look.
        
        Sprint 4.0.1: Fallback styling for Scene Graph rendering.
        """
        from app.ai.scene.schemas import ComponentStyle, GlobalStyle
        
        # Default styles by priority
        default_styles = {
            "primary": {
                "background": "#1a1a2e",
                "text_color": "#ffffff",
                "border_radius": "16px",
                "padding": "24px",
            },
            "secondary": {
                "background": "#16213e",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "20px",
            },
            "tertiary": {
                "background": "#0f3460",
                "text_color": "#ffffff",
                "border_radius": "12px",
                "padding": "16px",
            },
        }
        
        # Apply defaults to each component
        for component in scene.components:
            priority = component.priority or "secondary"
            defaults = default_styles.get(priority, default_styles["secondary"])
            
            if component.style is None:
                # No style at all - create with defaults
                component.style = ComponentStyle(**defaults)
                logger.debug(f"Applied default style to component {component.id}")
            else:
                # Style exists but may have missing fields - fill in gaps
                if component.style.background is None:
                    component.style.background = defaults["background"]
                if component.style.text_color is None:
                    component.style.text_color = defaults["text_color"]
                if component.style.border_radius is None:
                    component.style.border_radius = defaults["border_radius"]
                if component.style.padding is None:
                    component.style.padding = defaults["padding"]
        
        # Apply defaults to global_style
        if scene.global_style is None:
            scene.global_style = GlobalStyle(
                background="#0f0f23",
                font_family="Inter",
                text_color="#ffffff",
                accent_color="#7b2cbf",
            )
        else:
            if scene.global_style.background is None:
                scene.global_style.background = "#0f0f23"
            if scene.global_style.font_family is None:
                scene.global_style.font_family = "Inter"
            if scene.global_style.text_color is None:
                scene.global_style.text_color = "#ffffff"
            if scene.global_style.accent_color is None:
                scene.global_style.accent_color = "#7b2cbf"
        
        return scene
    
    # -------------------------------------------------------------------------
    # VALIDATION
    # -------------------------------------------------------------------------
    
    def _validate_scene(self, scene: SceneGraph) -> Tuple[bool, Optional[str]]:
        """
        Validate a Scene Graph structure.
        
        Checks that:
        - All component types exist in the registry
        - Required layout fields are present
        - At least one component exists
        
        Returns:
            (is_valid, error_message) tuple
        """
        # Must have at least one component
        if not scene.components:
            return False, "Scene must have at least one component"
        
        # Validate all component types
        for component in scene.components:
            is_valid, error = component_registry.validate_component_type(component.type)
            if not is_valid:
                return False, f"Component '{component.id}': {error}"
        
        # Validate layout
        if not scene.layout.intent:
            return False, "Layout must have an intent"
        
        return True, None


# ---------------------------------------------------------------------------
# SINGLETON INSTANCE
# ---------------------------------------------------------------------------

scene_service = SceneService()
