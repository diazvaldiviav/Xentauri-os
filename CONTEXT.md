# Xentauri Project Context

> **Last Updated:** January 11, 2026
> **Current Sprint:** Sprint 7 - Vision-Enhanced Visual Repair ✅ COMPLETE
> **Previous Sprint:** Sprint 6.5 - CSS Diagnosis for Visual Fixer ✅ COMPLETE
> **Backend Status:** ✅ MVP COMPLETE - Deployed to Production
> **Status:** 🚀 Backend deployed to fly.io, Visual validation pipeline active

Xentauri is an intelligent screen control system that lets users operate multiple display devices (TVs, monitors) via voice or text commands from their phone. The system comprises three main components:

- **Xentauri Remote** (iOS app): User-facing mobile application for voice/text commands and device management.
- **Xentauri Cloud Core** (Backend): Cloud services that process commands, manage devices/sessions, orchestrate agents, and provide APIs.
- **Xentauri Stick** (Raspberry Pi Agents): Edge software running on Raspberry Pi devices connected to screens, executing commands locally.

---

## 📊 Project Progress

### Sprint 1: Backend Foundations ✅ COMPLETE
| Task | Status |
|------|--------|
| FastAPI project structure | ✅ Done |
| PostgreSQL + SQLAlchemy + Alembic | ✅ Done |
| User model | ✅ Done |
| Device model | ✅ Done |
| POST /auth/register | ✅ Done |
| POST /auth/login (JWT) | ✅ Done |
| JWT middleware (get_current_user) | ✅ Done |
| GET /users/me (protected route) | ✅ Done |
| Local development running | ✅ Done |
| Database migrations | ✅ Done |
| Deploy to Fly.io | ✅ Done |

### Sprint 2: WebSocket Hub + Device Management ✅ COMPLETE
| Task | Status |
|------|--------|
| Device CRUD endpoints | ✅ Done |
| Device schemas (Pydantic) | ✅ Done |
| Pairing code service (generate, validate, consume) | ✅ Done |
| WebSocket connection manager | ✅ Done |
| WebSocket endpoint (ws/devices) | ✅ Done |
| Command routing service | ✅ Done |
| Command endpoints (send, power, status) | ✅ Done |
| Pytest test suite | ✅ Done |

### Sprint 3: AI Router + Intent Processing ✅ COMPLETE
| Task | Status |
|------|--------|
| AI provider clients (Gemini, OpenAI, Anthropic) | ✅ Done |
| AI Router/Orchestrator (Gemini Flash) | ✅ Done |
| Intelligent routing (Simple→Gemini, Execution→GPT, Reasoning→Claude) | ✅ Done |
| Intent Parser (NLU) | ✅ Done |
| Prompt engineering templates | ✅ Done |
| Device name fuzzy matching | ✅ Done |
| POST /intent endpoint with full routing | ✅ Done |
| Unified AI Monitor (DRY: logging + metrics) | ✅ Done |
| Test suite for intent parsing | ✅ Done |

### Sprint 3.5: Google OAuth + Calendar Integration ✅ COMPLETE
| Task | Status |
|------|--------|
| Environment module architecture (modular, extensible) | ✅ Done |
| Google OAuth client (auth code flow) | ✅ Done |
| OAuthCredential model (multi-provider token storage) | ✅ Done |
| Google Calendar API client | ✅ Done |
| Calendar HTML renderer (Chromium kiosk optimized) | ✅ Done |
| GET /auth/google/login endpoint | ✅ Done |
| GET /auth/google/callback endpoint | ✅ Done |
| GET /cloud/calendar endpoint (HTML) | ✅ Done |
| Database migration for oauth_credentials | ✅ Done |
| Display Simulator for development testing | ✅ Done |
| Simulator content persistence (localStorage) | ✅ Done |
| Content token service (signed iframe URLs) | ✅ Done |
| SHOW_CONTENT command type | ✅ Done |
| Intent prompts for calendar display | ✅ Done |

### Sprint 3.6: Unified AI Context + Calendar Intelligence ✅ COMPLETE
| Task | Status |
|------|--------|
| UnifiedContext system (single source of truth) | ✅ Done |
| Base prompt templates (DRY for all AI models) | ✅ Done |
| Action response schemas (structured GPT-4o JSON) | ✅ Done |
| Execution prompts for GPT-4o | ✅ Done |
| Update _handle_complex_task with UnifiedContext | ✅ Done |
| Calendar date parameter in /cloud/calendar | ✅ Done |
| Fix schema mismatch (device_type) | ✅ Done |
| GPT-4o JSON response logging & error handling | ✅ Done |
| Calendar date URL parameter passthrough | ✅ Done |

### Sprint 3.9: Google Docs Intelligence ✅ COMPLETE (December 20, 2025)
| Task | Status |
|------|--------|
| GoogleDocsClient with Google Docs API v1 | ✅ Done |
| DOCS_SCOPES in OAuth flow (documents.readonly) | ✅ Done |
| DocQueryIntent schema (doc_url, meeting_search) | ✅ Done |
| ActionTypes: READ_DOC, LINK_DOC, OPEN_DOC, SUMMARIZE_MEETING_DOC | ✅ Done |
| ActionType: CREATE_EVENT_FROM_DOC | ✅ Done |
| DocIntelligenceService with LLM analysis | ✅ Done |
| Meeting extraction from documents (ExtractedMeetingDetails) | ✅ Done |
| Intent prompts for doc commands (English + Spanish) | ✅ Done |
| _handle_doc_query in IntentService | ✅ Done |
| _handle_create_event_from_doc handler | ✅ Done |
| PendingEvent extended with doc_id, doc_url, source fields | ✅ Done |
| ConversationContextService (TTL 300s) | ✅ Done |
| Context storage after confirm_create (event + doc) | ✅ Done |
| Display docs on device (device_name auto-selection) | ✅ Done |
| Duration fix in confirm_create | ✅ Done |
| Device query vs system query distinction | ✅ Done |
| Null handling fix in parser (device_name) | ✅ Done |
| validate_access method for GoogleDocsClient | ✅ Done |

### Sprint 4.0: Scene Graph - Dynamic Display Layouts ✅ COMPLETE (December 22, 2025)
| Task | Status |
|------|--------|
| Scene Graph schemas (LayoutIntent, LayoutEngine, ComponentPriority) | ✅ Done |
| SceneComponent, SceneGraph, LayoutSpec Pydantic models | ✅ Done |
| ComponentRegistry with 17 components (12 MVP + 5 Sprint 4.0.3) | ✅ Done |
| Default scene templates (fullscreen, sidebar, dashboard, agenda, clock) | ✅ Done |
| SceneService with Claude integration | ✅ Done |
| normalize_layout_hints() for natural language parsing | ✅ Done |
| populate_scene_data() for calendar/clock/weather data | ✅ Done |
| Scene prompts for Claude generation | ✅ Done |
| DisplayContentIntent schema | ✅ Done |
| _handle_display_content handler in IntentService | ✅ Done |
| Intent parser integration for display_content | ✅ Done |
| Embedded data pattern (no separate endpoints) | ✅ Done |
| 31 tests for Scene Graph | ✅ Done |

### Sprint 4.0.3: Multi-Action Intent Support ✅ COMPLETE (December 22, 2025)
| Task | Status |
|------|--------|
| SequentialAction model for chained actions | ✅ Done |
| sequential_actions field in DeviceCommand | ✅ Done |
| Multi-action detection rules in intent_prompts.py | ✅ Done |
| _extract_sequential_actions() in parser.py | ✅ Done |
| _execute_sequential_actions() in intent_service.py | ✅ Done |
| Compound doc_query + display (also_display, display_device) | ✅ Done |
| AI Document Intelligence (content_request, content_type) | ✅ Done |
| _generate_custom_content() using Gemini | ✅ Done |
| New components: meeting_detail, countdown_timer, doc_summary, doc_preview | ✅ Done |
| Router fix for DISPLAY_CONTENT classification | ✅ Done |
| Spanish support in Device Mapper | ✅ Done |
| WebSocket reconnection improvements in Simulator | ✅ Done |
| Default styling fallbacks (prompt + service + renderer) | ✅ Done |
| Document fetching from meetings via meeting_link_service | ✅ Done |

### Sprint 4.1.0: Intelligent Conversations & Real-Time Data ✅ COMPLETE (December 27, 2025)
| Task | Status |
|------|--------|
| AI Model Upgrades (GPT-5.2, Claude Opus 4.5) | ✅ Done |
| Multilingual & Context-Aware Responses | ✅ Done |
| Universal Multilingual Rule in all prompts | ✅ Done |
| UnifiedContext with user personalization | ✅ Done |
| Conversation History Tracking (multi-turn) | ✅ Done |
| Pending Content Request handling (follow-up support) | ✅ Done |
| Content Generation vs Document Detection | ✅ Done |
| Dynamic Scene Graph Data via Gemini Web Search | ✅ Done |
| Real-time weather data in scene components | ✅ Done |
| Location extraction from user requests | ✅ Done |
| Calendar Queries with date_range filtering | ✅ Done |
| Smart Search consolidated (DRY refactor) | ✅ Done |
| _generate_calendar_response() for multilingual responses | ✅ Done |
| Intent prompts updated for content generation | ✅ Done |
| Router prompts updated for SIMPLE classification | ✅ Done |
| Scene data preservation in _parse_scene_response | ✅ Done |

### Sprint 4.4.0: Prompt Coordination & Context Harmonization ✅ COMPLETE (December 28, 2025)
| Task | Status |
|------|--------|
| Intent prompts optimization (2191 → 508 lines, 76% reduction) | ✅ Done |
| Examples reduction (137 → 18 examples, 2 per intent type) | ✅ Done |
| Spatial keyword detection in scene_prompts.py | ✅ Done |
| Fixed defaults.py content generation detection | ✅ Done |
| Fixed KeyError with .format() → .replace() in scene_prompts.py | ✅ Done |
| CONVERSATION vs DISPLAY_CONTENT contradiction resolved | ✅ Done |
| JSON syntax improvements for Gemini responses | ✅ Done |
| Content generation keyword detection (returns None for Claude) | ✅ Done |

### Sprint 4.5.0: Intelligent Execution & Context Memory ✅ COMPLETE (December 29, 2025)
| Task | Status |
|------|--------|
| **Problem #1: Search Execution** | |
| Expand search keywords (Spanish: últimas, actualizaciones, novedades) | ✅ Done |
| Add execution enforcement to assistant prompts | ✅ Done |
| Weather detection in _detect_content_type() | ✅ Done |
| **Problem #2: Context Memory** | |
| Content Memory System (GeneratedContent dataclass) | ✅ Done |
| Multi-content retrieval (get_content_by_title, get_recent_contents) | ✅ Done |
| Content memory injection in scene_prompts.py | ✅ Done |
| Multi-content display detection (skip fast path) | ✅ Done |
| Plan/intervention content type detection | ✅ Done |
| **Testing & Validation** | |
| Real-time API tests (5 creative prompts) | ✅ Done |
| Calendar context flow test (Noche Vieja event) | ✅ Done |
| Multi-content display test (calendar + plan) | ✅ Done |

### Sprint 5.1.0: Pi Alexa Authentication ✅ COMPLETE (December 30, 2025)
| Task | Status |
|------|--------|
| `get_user_from_agent()` dependency in deps.py | ✅ Done |
| POST /intent/agent endpoint (agent_id auth) | ✅ Done |
| X-Agent-ID header validation | ✅ Done |
| Agent → Device → User chain lookup | ✅ Done |
| Same IntentService.process() logic as /intent | ✅ Done |
| Documentation (PI_ALEXA_AUTHENTICATION.md) | ✅ Done |

### Sprint 6.0: Visual-based Validation System ✅ COMPLETE (January 2026)
| Task | Status |
|------|--------|
| 7-phase validation pipeline architecture | ✅ Done |
| ValidationContract and SandboxResult dataclasses | ✅ Done |
| Phase 1: Render validation (Playwright) | ✅ Done |
| Phase 2: Visual snapshot with blank page detection | ✅ Done |
| Phase 3: Scene graph extraction from DOM | ✅ Done |
| Phase 4: Input candidate detection | ✅ Done |
| Phase 5: Interaction testing (click + screenshot comparison) | ✅ Done |
| Phase 6: Result aggregation | ✅ Done |
| DirectFixer for HTML repair (Codex-Max) | ✅ Done |
| Visual change threshold (2% = 41,000 pixels) | ✅ Done |
| Playwright sandbox integration | ✅ Done |

### Sprint 6.1: EOR + Enriched Fixer ✅ COMPLETE (January 10, 2026)
| Task | Status |
|------|--------|
| Event Owner Resolution (EOR) for child elements | ✅ Done |
| SVG structural rule (graphic nodes → container) | ✅ Done |
| `findEventOwnerCandidate()` JavaScript function | ✅ Done |
| `EventOwnerCandidate` dataclass in contracts.py | ✅ Done |
| `_resolve_event_owners()` in input_detector.py | ✅ Done |
| Failure classification: `no_change`, `under_threshold`, `error` | ✅ Done |
| `get_failure_type()` method in InteractionResult | ✅ Done |
| `get_repair_context()` with pixel_diff_ratio | ✅ Done |
| Enriched `build_repair_prompt()` with diagnosis | ✅ Done |
| Updated `REPAIR_SYSTEM_PROMPT` for failure types | ✅ Done |
| Thinking mode removed from Opus 4.5 | ✅ Done |
| Deployed to Fly.io production | ✅ Done |
| **Bug Fix:** Validation ignores layout type for 70% check | ✅ Done |
| **Bug Fix:** Dynamic JS content timing (wait for init) | ✅ Done |
| **Bug Fix:** Skip disabled elements in interaction validation | ✅ Done |
| Gunicorn timeout increased to 300s (TD-001) | ✅ Done |

### Sprint 6.3: Adaptive Threshold + Safe Fixer ✅ COMPLETE (January 10, 2026)
| Task | Status |
|------|--------|
| **Root Cause Analysis** | |
| Identified fixer regression (2/8 → 1/8 → 2/8 loop) | ✅ Done |
| Problem: 2% viewport threshold impossible for small buttons | ✅ Done |
| Problem: Destructive strategies affecting sibling elements | ✅ Done |
| **Adaptive Threshold System** | |
| `element_pixels` field in VisualDelta (contracts.py) | ✅ Done |
| `element_diff_ratio` field in VisualDelta | ✅ Done |
| Dual threshold: 2% viewport OR 30% element-relative | ✅ Done |
| `has_visible_change(threshold, element_threshold)` method | ✅ Done |
| Element-relative diff calculation in visual_analyzer.py | ✅ Done |
| Updated interaction_validator.py to use adaptive threshold | ✅ Done |
| **Safe Fixer Strategies** | |
| Removed destructive strategies (parent container changes) | ✅ Done |
| Safe element-specific CSS suggestions only | ✅ Done |
| Complete rewrite of REPAIR_SYSTEM_PROMPT in fixer.py | ✅ Done |
| PROHIBITED CSS SELECTORS section (*, html, body, etc.) | ✅ Done |
| Ultra-specific selector requirements (3+ levels deep) | ✅ Done |
| **Production Testing (6 prompts)** | |
| Roma trivia: 4/4 (100%) - passed first try | ✅ Done |
| Memory game: 4/8 → 5/5 (repair worked, +100%) | ✅ Done |
| Solar system animated: 5/5 (100%) - passed first try | ✅ Done |
| Flash cards solar: 4/4 (100%) - passed first try | ✅ Done |
| Math quiz 10 questions: 5/7 (86%) - passed first try | ✅ Done |
| Dashboard 4 panels: 5/8 → 5/6 (repair worked, +92%) | ✅ Done |
| Deployed to Fly.io production | ✅ Done |

### Sprint 6.5: CSS Diagnosis for Visual Fixer ✅ COMPLETE (January 11, 2026)
| Task | Status |
|------|--------|
| **Root Cause Analysis** | |
| Opus generates .selected CSS without background-color | ✅ Done |
| Fixer received vague "element broken" not exact CSS fix | ✅ Done |
| CSS animations caused false negatives in screenshots | ✅ Done |
| **CSS Diagnosis System (fixer.py)** | |
| `_extract_css_from_html()` - Extract CSS from <style> tags | ✅ Done |
| `_find_css_rules_for_classes()` - Find .selected/.active rules | ✅ Done |
| `analyze_css_for_element()` - Check rules have background-color | ✅ Done |
| `_build_phase_summary()` - Format Phase 1-6 validation results | ✅ Done |
| `_build_css_diagnosis()` - Generate specific CSS fix instructions | ✅ Done |
| `build_repair_prompt()` - Rebuilt with progressive context | ✅ Done |
| **Animation Pausing (interaction_validator.py)** | |
| `_pause_animations()` - Set animationPlayState='paused' | ✅ Done |
| Added pause call in `_test_single_input()` | ✅ Done |
| Added pause call in `_test_interaction_unit()` | ✅ Done |
| **Production Testing (Local)** | |
| Sistema Solar: PASSED first attempt (5/6, confidence 0.92) | ✅ Done |
| Quiz Geografia: PASSED (5/5, confidence 1.00) | ✅ Done |
| Mapa de España: Opus FAILED → Sonnet REPAIRED (1/1) | ✅ Done |
| Flashcards Capitales Europa: PASSED (trivia layout) | ✅ Done |
| Key insight: Sonnet capable if given exact instructions | ✅ Done |
| Deployed to Fly.io production | ⏳ Pending |

### Sprint 7: Vision-Enhanced Visual Repair ✅ COMPLETE (January 11, 2026)
**Commit:** `75f8da1` - Sprint 7: Vision-Enhanced Visual Repair System

| Task | Status |
|------|--------|
| **Problem Identified** | |
| Elements exist in DOM but are INVISIBLE (transforms, opacity) | ✅ Done |
| Validation passes but render shows missing elements (false positive) | ✅ Done |
| Fixer receives text diagnosis but can't SEE the actual problem | ✅ Done |
| **Visibility Detection (Phase 4)** | |
| `contracts.py`: Added visibility_status, visibility_pixels, visibility_ratio | ✅ Done |
| `contracts.py`: Added page_screenshot, screenshot_path to SandboxResult | ✅ Done |
| `input_detector.py`: Added check_elements_visibility() | ✅ Done |
| `input_detector.py`: Added _check_single_element_visibility() with PIL | ✅ Done |
| **Screenshot System** | |
| `visual_analyzer.py`: Added save_screenshot() | ✅ Done |
| `visual_analyzer.py`: Added image_to_base64(), resize_image_for_api() | ✅ Done |
| `validation/__init__.py`: Capture screenshot in Phase 2 | ✅ Done |
| **Vision Repair (Sonnet + Extended Thinking)** | |
| `anthropic_provider.py`: Added generate_with_vision() | ✅ Done |
| `anthropic_provider.py`: Extended thinking with budget_tokens=10000 | ✅ Done |
| `fixer.py`: Added VISION_REPAIR_SYSTEM_PROMPT | ✅ Done |
| `fixer.py`: Added build_vision_repair_prompt() | ✅ Done |
| `fixer.py`: Added repair_with_vision() method | ✅ Done |
| **Integration** | |
| `service.py`: Use vision repair when screenshot available | ✅ Done |
| `config.py`: Added VISION_REPAIR_ENABLED setting | ✅ Done |
| **Test Results** | |
| Quiz Astronomía: 50% → 100% after 1 vision repair | ✅ Done |
| Extended thinking: ~2500 chars used | ✅ Done |
| Vision repair latency: ~90 seconds | ✅ Done |
| Total tokens per repair: ~14000 | ✅ Done |

**Hotfix:** `4a7af8f` - JS Error Detection During Interaction (January 11, 2026)

| Task | Status |
|------|--------|
| **Bug: False positive - validation passed but buttons broken** | |
| Error: `autoAdvance` null reference breaks script before event listeners | ✅ Fixed |
| Gap: JS errors during interaction (setTimeout, click handlers) not detected | ✅ Fixed |
| `interaction_validator.py`: Accept render_ctx parameter | ✅ Done |
| `interaction_validator.py`: Track JS errors before/after clicks | ✅ Done |
| `interaction_validator.py`: Phase 5 fails if JS errors detected | ✅ Done |
| `__init__.py`: Pass render_ctx to interaction_validator.validate() | ✅ Done |
| `fixer.py`: Show JS errors in Phase 5 summary for Sonnet repair | ✅ Done |
| Deployed to Fly.io production | ✅ Done |

### 🎉 BACKEND MVP COMPLETE
All backend features for MVP are complete:
- ✅ User authentication (JWT)
- ✅ Device management (CRUD + pairing)
- ✅ AI Router (Gemini/GPT/Claude)
- ✅ Google Calendar integration (CRUD)
- ✅ Google Docs intelligence
- ✅ Scene Graph (dynamic layouts)
- ✅ Multi-action intents
- ✅ Intelligent conversations
- ✅ Real-time data (weather, search)
- ✅ Content memory system
- ✅ Multilingual support (Spanish/English)
- ✅ Pi Alexa agent_id authentication

### Sprint 5.0: Raspberry Pi Agent (NEXT)
| Task | Status |
|------|--------|
| Agent project structure (Python) | ⏳ Planned |
| WebSocket client to connect to cloud | ⏳ Planned |
| Pairing flow implementation | ⏳ Planned |
| HDMI-CEC command execution (cec-client) | ⏳ Planned |
| Content display (Chromium kiosk) | ⏳ Planned |
| Command acknowledgment and status reporting | ⏳ Planned |
| Local configuration and persistence | ⏳ Planned |
| End-to-end testing with real hardware | ⏳ Planned |

---

## 🏗️ Current Architecture

```
Jarvis_Cloud/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── deps.py              # Dependencies (get_current_user)
│   ├── core/
│   │   ├── config.py        # Settings from .env (incl. AI + OAuth keys)
│   │   └── security.py      # Password hashing, JWT creation
│   ├── db/
│   │   ├── base.py          # SQLAlchemy Base class
│   │   └── session.py       # Database engine & session
│   ├── models/
│   │   ├── user.py          # User ORM model
│   │   ├── device.py        # Device ORM model
│   │   └── oauth_credential.py  # OAuth token storage (Sprint 3.5)
│   ├── routers/
│   │   ├── auth.py          # /auth/register, /auth/login
│   │   ├── users.py         # /users/me
│   │   ├── devices.py       # Device CRUD + pairing
│   │   ├── commands.py      # Send commands to devices
│   │   ├── intent.py        # AI intent processing (Sprint 3)
│   │   ├── websocket.py     # WebSocket for Pi agents
│   │   ├── google_auth.py   # Google OAuth endpoints (Sprint 3.5)
│   │   ├── cloud.py         # Cloud content for displays (Sprint 3.5)
│   │   └── simulator.py     # Display simulator for dev testing (Sprint 3.5)
│   ├── services/
│   │   ├── pairing.py           # Pairing code generation/validation
│   │   ├── websocket_manager.py # Connection manager
│   │   ├── commands.py          # Command routing service
│   │   ├── intent_service.py    # Intent processing business logic
│   │   ├── content_token.py     # Signed content tokens for iframes
│   │   ├── calendar_search_service.py # Smart calendar search with LLM (Sprint 3.7)
│   │   ├── pending_event_service.py   # Pending event creation (Sprint 3.8, TTL 120s)
│   │   ├── pending_edit_service.py    # Pending edit/delete operations (Sprint 3.9, TTL 120s)
│   │   ├── doc_intelligence_service.py # Google Docs AI analysis (Sprint 3.9)
│   │   ├── conversation_context_service.py # Conversation context tracking (Sprint 3.9, TTL 300s)
│   │   └── meeting_link_service.py      # Document-meeting linking (Sprint 4.0.3)
│   ├── schemas/
│   │   ├── auth.py          # Request/response schemas for auth
│   │   ├── user.py          # UserOut schema
│   │   └── device.py        # Device schemas
│   ├── ai/                   # AI Module (Sprint 3) - The Brain
│   │   ├── __init__.py      # Module exports
│   │   ├── context.py       # UnifiedContext system (Sprint 3.6)
│   │   ├── actions/         # Action Registry (Tech Debt Cleanup)
│   │   │   ├── __init__.py  # Module exports
│   │   │   └── registry.py  # ActionDefinition, ActionRegistry (11 actions)
│   │   ├── providers/       # LLM Provider Clients
│   │   │   ├── base.py      # Abstract provider interface
│   │   │   ├── gemini.py    # Google Gemini (orchestrator)
│   │   │   ├── openai_provider.py   # OpenAI GPT (execution)
│   │   │   └── anthropic_provider.py # Claude (reasoning)
│   │   ├── router/          # AI Orchestration
│   │   │   └── orchestrator.py  # Routes requests to models
│   │   ├── intent/          # Natural Language Understanding
│   │   │   ├── schemas.py   # Intent data structures (incl. DisplayContentIntent)
│   │   │   ├── parser.py    # LLM-based intent extraction
│   │   │   └── device_mapper.py # Fuzzy device name matching
│   │   ├── scene/           # Scene Graph Module (Sprint 4.0)
│   │   │   ├── __init__.py  # Module exports
│   │   │   ├── schemas.py   # SceneGraph, LayoutSpec, SceneComponent models
│   │   │   ├── registry.py  # ComponentRegistry (17 components)
│   │   │   ├── defaults.py  # Default scene templates (5 presets)
│   │   │   ├── service.py   # SceneService (generation + data population)
│   │   │   └── custom_layout/  # Custom HTML Layout Module (Sprint 5.2+)
│   │   │       ├── __init__.py
│   │   │       ├── service.py       # CustomLayoutService (Opus 4.5 HTML generation)
│   │   │       ├── prompts.py       # HTML generation prompts
│   │   │       ├── html_repair_prompts.py  # Repair prompt templates
│   │   │       ├── validator.py     # Legacy validator (pre-Sprint 6)
│   │   │       └── validation/      # Visual Validation Pipeline (Sprint 6)
│   │   │           ├── __init__.py  # Module exports
│   │   │           ├── contracts.py # ValidationContract, SandboxResult, InteractionResult
│   │   │           ├── aggregator.py    # Phase 6: Result aggregation
│   │   │           ├── fixer.py         # DirectFixer (Codex-Max repair)
│   │   │           ├── input_detector.py # Phase 4: Input candidate detection + EOR
│   │   │           ├── interaction_validator.py # Phase 5: Click + screenshot comparison
│   │   │           ├── scene_graph.py   # Phase 3: DOM inspection + findEventOwnerCandidate()
│   │   │           └── visual_analyzer.py # Phase 2: Visual snapshot + blank detection
│   │   ├── prompts/         # Prompt Templates (Sprint 3.6)
│   │   │   ├── base_prompt.py      # Shared templates for all models
│   │   │   ├── execution_prompts.py # GPT-4o execution prompts
│   │   │   ├── router_prompts.py   # Routing decision prompts
│   │   │   ├── intent_prompts.py   # Intent extraction prompts
│   │   │   ├── doc_prompts.py      # Google Docs analysis prompts (Sprint 3.9)
│   │   │   └── scene_prompts.py    # Scene generation prompts (Sprint 4.0)
│   │   ├── schemas/         # AI Response Schemas (Sprint 3.6)
│   │   │   ├── __init__.py  # Schema exports
│   │   │   └── action_response.py  # Structured GPT-4o responses
│   │   └── monitoring/      # Observability (Unified)
│   │       ├── monitor.py   # AIMonitor: unified logging + metrics (DRY)
│   │       ├── logger.py    # Legacy AILogger (deprecated)
│   │       └── metrics.py   # Legacy AIMetrics (deprecated)
│   └── environments/         # External Service Integrations (Sprint 3.5)
│       ├── __init__.py      # Module exports
│       ├── base.py          # Abstract interfaces for all providers
│       └── google/          # Google Workspace Integration
│           ├── __init__.py  # Google module exports
│           ├── auth/        # Google OAuth 2.0
│           │   ├── __init__.py
│           │   ├── client.py    # OAuth flow implementation
│           │   └── schemas.py   # Auth data structures (CALENDAR_SCOPES, DOCS_SCOPES)
│           ├── calendar/    # Google Calendar API
│           │   ├── __init__.py
│           │   ├── client.py    # Calendar API client
│           │   ├── schemas.py   # Calendar data structures
│           │   └── renderer.py  # HTML rendering for Raspberry Pi
│           └── docs/        # Google Docs API (Sprint 3.9)
│               ├── __init__.py
│               └── client.py    # GoogleDocsClient (get_document, validate_access)
├── tests/
│   ├── conftest.py          # Pytest fixtures
│   ├── test_action_registry.py   # Action registry tests (37 tests)
│   ├── test_action_response.py   # AI response schema tests (47 tests)
│   ├── test_ai_providers.py      # AI provider base tests (23 tests)
│   ├── test_ai_router.py         # AI orchestrator tests (29 tests)
│   ├── test_device_mapper.py     # Device matching tests (42 tests)
│   ├── test_devices.py           # Device CRUD tests
│   ├── test_intent.py            # Intent parsing tests
│   ├── test_intent_parser.py     # Parser edge cases (33 tests)
│   ├── test_intent_service.py    # Service layer tests (32 tests)
│   ├── test_intent_search.py     # Calendar search intent tests
│   ├── test_calendar_query.py    # Calendar query tests
│   ├── test_calendar_search.py   # Calendar search tests
│   ├── test_calendar_smart_search.py # Smart search tests
│   ├── test_calendar_edit_handler.py # Calendar edit/delete tests (21 tests)
│   ├── test_calendar_create_handler.py # Calendar create tests
│   ├── test_calendar_create_intent.py  # Calendar create intent tests
│   ├── test_sprint_391_bugfixes.py  # Sprint 3.9.1 bug fix tests (13 tests)
│   ├── test_context_aware_confirmation.py # Context-aware confirmation tests
│   ├── test_conversation_context.py # Conversation context service tests (Sprint 3.9)
│   ├── test_pending_event_service.py # Pending event tests
│   ├── test_pending_edit_service.py  # Pending edit tests
│   ├── test_pairing.py           # Pairing service tests
│   └── test_websocket_manager.py # WebSocket manager tests
├── alembic/                  # Database migrations
├── venv/                     # Python virtual environment
├── .env                      # Environment variables (not in git)
├── .env.example              # Template for .env
├── requirements.txt          # Python dependencies
├── Dockerfile                # Container build
├── fly.toml                  # Fly.io deployment config
├── RUN_PROJECT.txt           # Instructions to run locally
└── CONTEXT.md                # This file
```

---

## 🔌 API Endpoints (Current)

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /auth/register | No | Create new user account |
| POST | /auth/login | No | Login, returns JWT token |

### Users
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /users/me | Yes | Get current user profile |

### Devices
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /devices | Yes | Create a new device |
| GET | /devices | Yes | List user's devices |
| GET | /devices/{id} | Yes | Get device details |
| PATCH | /devices/{id} | Yes | Update device |
| DELETE | /devices/{id} | Yes | Delete device |
| POST | /devices/{id}/pairing-code | Yes | Generate pairing code |
| POST | /devices/pair | No | Pair agent with device (uses pairing code) |

### Commands
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /commands/{device_id} | Yes | Send custom command |
| POST | /commands/{device_id}/power/on | Yes | Turn device on |
| POST | /commands/{device_id}/power/off | Yes | Turn device off |
| GET | /commands/{device_id}/status | Yes | Check if device is online |

### Intent (AI - Sprint 3 + 5.1)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /intent | JWT | Process natural language command (iOS app) |
| POST | /intent/agent | X-Agent-ID | Process intent from Pi Alexa (agent_id auth) |
| GET | /intent/stats | JWT | Get AI usage statistics |

### Google OAuth (Sprint 3.5)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /auth/google/login | Yes | Initiate Google OAuth flow |
| GET | /auth/google/callback | No | Handle OAuth callback |
| DELETE | /auth/google | Yes | Disconnect Google account |
| GET | /auth/google/status | Yes | Check Google connection status |

### Cloud Content (Sprint 3.5)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /cloud/calendar | Yes | Rendered HTML calendar for Pi |
| GET | /cloud/calendar/preview | No | Demo calendar (no auth) |
| GET | /cloud/calendar/status | Yes | Calendar integration status |

### Display Simulator (Sprint 3.5)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /simulator | No | Device selection page |
| GET | /simulator/{device_id} | No | Simulator for specific device |

### WebSocket
| Endpoint | Auth | Description |
|----------|------|-------------|
| ws://.../ws/devices?agent_id=xxx | No | Agent connection (Pi connects here) |

### System
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /health | No | Health check |

**API Docs:** http://localhost:8000/docs

---

## 🛠️ Tech Stack

| Layer | Technology | Version |
|-------|------------|---------|
| Framework | FastAPI | 0.115.2 |
| Server | Uvicorn | 0.32.0 |
| Database | PostgreSQL | 16 |
| ORM | SQLAlchemy | 2.0.36 |
| Migrations | Alembic | 1.13.2 |
| Auth | JWT (python-jose) | 3.3.0 |
| Password | bcrypt (passlib) | 1.7.4 |
| Validation | Pydantic | 2.9.2 |
| HTTP Client | httpx | 0.27.2 |
| Testing | Pytest | 8.3.3 |
| Deployment | Fly.io | - |
| AI - Gemini | google-generativeai | 0.8.3 (gemini-2.5-flash, gemini-3-flash-preview) |
| AI - OpenAI | openai | 1.55.3 (GPT-5.2, gpt-5.1-codex-max, Responses API) |
| AI - Claude | anthropic | 0.39.0 (Claude Opus 4.5 for HTML generation) |
| Browser Automation | playwright | 1.40+ (Visual validation sandbox) |

---

## 🚀 How to Run

```bash
# Quick start (one command):
cd /Users/victordiaz/Jarvis/Jarvis_Cloud && source venv/bin/activate && docker start jarvis-postgres && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

See `RUN_PROJECT.txt` for detailed instructions.

---

## 🔐 Environment Variables

```bash
# .env file
DATABASE_URL=postgresql+psycopg://jarvis:jarvis123@localhost:5432/jarvis_db
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=1440  # 24 hours

# AI API Keys (Sprint 3)
GEMINI_API_KEY=your-gemini-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key

# Google OAuth (Sprint 3.5)
# Get these from: https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
```

---

## 🧠 AI Router Architecture (Sprint 3)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     POST /intent - Full Flow                             │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     AI Router (Orchestrator)                             │
│                      [Gemini 2.5 Flash Lite]                             │
│                                                                          │
│         Analyzes request complexity and decides routing                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    SIMPLE     │     │   COMPLEX     │     │   COMPLEX     │
│               │     │  EXECUTION    │     │  REASONING    │
│ Device cmds,  │     │               │     │               │
│ simple Q&A    │     │ Code, tools,  │     │ Analysis,     │
│               │     │ step-by-step  │     │ planning,     │
│ Gemini Flash  │     │   GPT-4o      │     │ Claude Haiku  │
│ Intent Parser │     │               │     │               │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ Device Mapper │     │ Direct AI     │     │ Direct AI     │
│ + Command Svc │     │ Response      │     │ Response      │
└───────────────┘     └───────────────┘     └───────────────┘

Example Flows:

1. Simple Command: "Turn on the living room TV"
   → Router: SIMPLE → Gemini Intent Parser → Device Mapper → WebSocket → TV On

2. Code Request: "Write a Python script to schedule my TV"
   → Router: COMPLEX_EXECUTION → GPT-4o → Returns Python code

3. Analysis Request: "Analyze my device setup for efficiency"
   → Router: COMPLEX_REASONING → Claude → Returns analysis
```

### Intent Processing Architecture (Refactored)

After the technical debt cleanup, the intent processing follows a clean separation:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Clean Architecture                                   │
└─────────────────────────────────────────────────────────────────────────┘

Before (1319 lines):                After (205 + 1056 lines):
┌───────────────────┐               ┌───────────────────┐
│   intent.py       │               │   intent.py       │  ← HTTP only (205 lines)
│   (ROUTER)        │               │   (ROUTER)        │
│                   │               └─────────┬─────────┘
│ - HTTP handling   │                         │
│ - Intent parsing  │                         ▼
│ - Device matching │               ┌───────────────────┐
│ - Command exec    │               │ intent_service.py │  ← Business logic (1056 lines)
│ - Content display │               │   (SERVICE)       │
│ - Complex tasks   │               └─────────┬─────────┘
│ - Message build   │                         │
│ - Error handling  │               ┌─────────┴─────────┐
└───────────────────┘               │                   │
                                    ▼                   ▼
                          ┌──────────────┐    ┌──────────────┐
                          │ ActionRegistry│    │   AI/Cmds    │
                          │ (11 actions) │    │   Providers  │
                          └──────────────┘    └──────────────┘
```

**IntentService** (Single Responsibility):
- `process()` - Main entry point
- `_handle_simple_task()` - Gemini intent parsing
- `_handle_complex_task()` - GPT/Claude routing
- `_handle_device_command()` - Device commands
- `_handle_device_query()` - Status queries
- `_handle_system_query()` - System info
- `_handle_conversation()` - Greetings, thanks
- `_execute_content_action()` - Calendar display
- `_execute_device_command()` - Power, volume, etc.

**ActionRegistry** (Centralized Definitions):
- 11 built-in actions: power_on, power_off, volume_up, volume_down, mute, unmute, set_input, volume_set, show_calendar, show_content, clear_content
- Parameter validation with custom validators
- Action aliases (e.g., "turn_on" → "power_on")
- Category-based queries

### Unified AI Monitoring (DRY Principle)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AIMonitor (Unified)                                  │
│                                                                          │
│  One call = Structured Logs + In-Memory Metrics + Cost Tracking          │
│                                                                          │
│  ai_monitor.track_request()   → Logs request start                       │
│  ai_monitor.track_response()  → Logs response + updates metrics          │
│  ai_monitor.track_routing()   → Logs routing decisions                   │
│  ai_monitor.track_intent()    → Logs parsed intents                      │
│  ai_monitor.track_command()   → Logs device commands                     │
│  ai_monitor.track_error()     → Logs errors                              │
│  ai_monitor.get_stats()       → Returns aggregated metrics               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 🌐 Environment Integrations Architecture (Sprint 3.5 + 3.9)

The environments module provides a modular, extensible architecture for integrating
with external services (Google, Microsoft, Apple, etc.).

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Environment Architecture                             │
└─────────────────────────────────────────────────────────────────────────┘

environments/
├── base.py                    # Abstract interfaces
│   ├── EnvironmentProvider    # OAuth provider contract
│   ├── EnvironmentService     # API service contract
│   └── Custom Exceptions      # AuthError, TokenExpired, etc.
│
├── google/                    # Google Workspace ✅ Implemented
│   ├── auth/                  # Shared OAuth for all Google services
│   │   ├── client.py          # GoogleAuthClient
│   │   └── schemas.py         # CALENDAR_SCOPES, DOCS_SCOPES
│   ├── calendar/              # ✅ Google Calendar API
│   │   ├── client.py          # GoogleCalendarClient
│   │   ├── schemas.py         # CalendarEvent, etc.
│   │   └── renderer.py        # HTML for Raspberry Pi
│   ├── docs/                  # ✅ Google Docs API (Sprint 3.9)
│   │   └── client.py          # GoogleDocsClient (get_document, validate_access)
│   ├── drive/                 # 🔜 Planned
│   └── gmail/                 # 🔜 Planned
│
├── microsoft/                 # 🔜 Microsoft 365 (future)
│   ├── auth/                  # Microsoft OAuth
│   ├── outlook/               # Outlook Calendar
│   └── onedrive/              # OneDrive
│
└── apple/                     # 🔜 Apple Services (future)
    └── calendar/              # iCloud Calendar
```

### Google Docs Intelligence Flow (Sprint 3.9)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Google Docs Intelligence Flow                        │
└─────────────────────────────────────────────────────────────────────────┘

1. READ/ANALYZE DOCUMENT
   ┌─────────┐     ┌─────────────────┐     ┌──────────────┐
   │  User   │────▶│ POST /intent    │────▶│ GoogleDocs   │
   │ "read   │     │ DOC_QUERY       │     │ API v1       │
   │  doc"   │     │ action=read_doc │     │              │
   └─────────┘     └────────┬────────┘     └──────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ DocIntelligence │
                   │ Service (LLM)   │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Analysis/Summary│
                   │ returned to user│
                   └─────────────────┘

2. CREATE EVENT FROM DOCUMENT
   ┌─────────┐     ┌─────────────────┐     ┌──────────────┐
   │  User   │────▶│ POST /intent    │────▶│ GoogleDocs   │
   │"create  │     │ DOC_QUERY       │     │ API v1       │
   │event    │     │action=create_   │     └──────┬───────┘
   │from doc"│     │event_from_doc   │            │
   └─────────┘     └────────┬────────┘            │
                            │                     ▼
                            │            ┌──────────────┐
                            ▼            │ Extract      │
                   ┌─────────────────┐   │ Meeting      │
                   │ PendingEvent    │◀──│ Details (LLM)│
                   │ (missing date?) │   └──────────────┘
                   └────────┬────────┘
                            │
           ┌────────────────┴────────────────┐
           ▼                                 ▼
   ┌─────────────────┐              ┌─────────────────┐
   │ All data found  │              │ Missing date/   │
   │ Create event    │              │ time - ask user │
   │ immediately     │              │ Store pending   │
   └────────┬────────┘              └────────┬────────┘
            │                                │
            ▼                                ▼
   ┌─────────────────┐              ┌─────────────────┐
   │ Google Calendar │              │ User confirms   │
   │ Event Created   │              │ with date/time  │
   │ + Doc link      │              │ → Create event  │
   └─────────────────┘              └─────────────────┘
```

### ActionTypes for Documents (Sprint 3.9)

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| READ_DOC | Read and analyze document content | doc_url |
| LINK_DOC | Link document to calendar event | doc_url, meeting_search |
| OPEN_DOC | Find/open doc linked to meeting | meeting_search |
| SUMMARIZE_MEETING_DOC | Summarize meeting document | meeting_search |
| CREATE_EVENT_FROM_DOC | Create calendar event from doc | doc_url |

### Google Calendar Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Google Calendar Display Flow                         │
└─────────────────────────────────────────────────────────────────────────┘

1. AUTHENTICATION (One-time setup)
   ┌─────────┐     ┌─────────────────┐     ┌──────────────┐
   │   User  │────▶│ /auth/google    │────▶│   Google     │
   │   App   │     │ /login          │     │ OAuth Screen │
   └─────────┘     └─────────────────┘     └──────┬───────┘
                                                   │
                                                   ▼
   ┌─────────────────┐     ┌─────────────────┐     │
   │ OAuthCredential │◀────│ /auth/google    │◀────┘
   │    (DB)         │     │ /callback       │
   └─────────────────┘     └─────────────────┘

2. DISPLAY (Raspberry Pi)
   ┌─────────────┐     ┌─────────────────┐     ┌──────────────┐
   │ Raspberry   │────▶│ GET /cloud      │────▶│ Google       │
   │ Pi Browser  │     │ /calendar       │     │ Calendar API │
   └─────────────┘     └────────┬────────┘     └──────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │ CalendarRenderer│
                       │ (HTML Output)   │
                       └─────────────────┘
```

### Design Principles

1. **Provider Isolation**: Google, Microsoft, Apple are completely independent
2. **Service Modularity**: Calendar, Drive, Gmail are separate modules
3. **Shared Authentication**: OAuth tokens reused across services within a provider
4. **Extensibility**: Easy to add new providers or services
5. **Single Responsibility**: Each module has one clear purpose

---

## 🎨 Visual Validation Pipeline (Sprint 6)

The visual validation system uses Playwright to verify that generated HTML layouts are interactive and functional before serving them to display devices.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Visual Validation Pipeline                           │
└─────────────────────────────────────────────────────────────────────────┘

     ValidationContract (HTML + thresholds)
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 1: RENDER                                                          │
│   - Load HTML in Playwright headless browser                             │
│   - Check for JavaScript errors                                          │
│   - Verify page loads without crashes                                    │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 2: VISUAL SNAPSHOT                                                 │
│   - Capture initial screenshot                                           │
│   - Compute histogram (256-bin grayscale)                                │
│   - Calculate variance and non_background_ratio                          │
│   - Detect blank pages (>95% uniform color)                              │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 3: SCENE GRAPH                                                     │
│   - Extract DOM elements with positions (BoundingBox)                    │
│   - Identify node types (button, input, container, text)                 │
│   - Run findEventOwnerCandidate() for EOR                                │
│   - Build ObservedSceneGraph with SceneNode list                         │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 4: INPUT DETECTION                                                 │
│   - Find clickable elements (buttons, links, [onclick])                  │
│   - Resolve Event Owners (EOR) for child elements                        │
│   - SVG rule: graphic nodes → interactive container                      │
│   - Score and prioritize InputCandidates                                 │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 5: INTERACTION TESTING                                             │
│   - For each InputCandidate (up to MAX_INPUTS_TO_TEST):                  │
│     1. Take "before" screenshot                                          │
│     2. Click the element                                                 │
│     3. Wait stabilization_ms for animations                              │
│     4. Take "after" screenshot                                           │
│     5. Compare: pixel_diff_ratio = changed_pixels / total_pixels         │
│     6. responsive = (pixel_diff_ratio > 2%)                              │
└─────────────────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ Phase 6: AGGREGATION                                                     │
│   - Count responsive vs unresponsive inputs                              │
│   - Calculate confidence score                                           │
│   - Generate failure_summary if validation fails                         │
│   - Return SandboxResult                                                 │
└─────────────────────────────────────────────────────────────────────────┘
                    │
          ┌────────┴────────┐
          ▼                 ▼
     ┌─────────┐      ┌─────────────┐
     │  VALID  │      │  INVALID    │
     │ Return  │      │             │
     │  HTML   │      │ DirectFixer │
     └─────────┘      └──────┬──────┘
                             │
                             ▼
               ┌─────────────────────────────────────────┐
               │ Phase 7: REPAIR (DirectFixer)           │
               │   - Build repair prompt with:           │
               │     • pixel_diff_ratio per element      │
               │     • failure_type classification       │
               │     • interpretation for each failure   │
               │   - Send to Codex-Max                   │
               │   - Re-validate repaired HTML           │
               │   - Retry up to VALIDATION_REPAIR_MAX   │
               └─────────────────────────────────────────┘
```

### Failure Classification (Sprint 6.1)

The fixer receives enriched context to understand the REAL problem:

| Failure Type | pixel_diff_ratio | Interpretation | Fix Strategy |
|--------------|------------------|----------------|--------------|
| `no_change` | < 0.1% | Handler broken/missing | Add or fix onclick handler |
| `under_threshold` | 0.1% - 2% | Works but subtle feedback | Amplify visual effect (overlays, larger areas) |
| `error` | N/A | JavaScript error | Fix the error in code |
| `passed` | > 2% | Working correctly | No action needed |

### Event Owner Resolution (EOR)

When child elements inherit cursor:pointer from a parent with onclick:

```
┌────────────────────────────────────────┐
│  <div class="option" onclick="...">    │  ← Event Owner (has onclick)
│    <span class="letter">A</span>       │  ← Child (inherits pointer)
│    <span class="text">Paris</span>     │  ← Child (inherits pointer)
│  </div>                                │
└────────────────────────────────────────┘

Before EOR: 3 candidates (div, span.letter, span.text)
After EOR:  1 candidate (div) with source_elements: [span.letter, span.text]
```

SVG Structural Rule: SVG graphic nodes (`<path>`, `<rect>`, `<circle>`) can NEVER be self-owned. They always resolve to their `<svg>` container.

---

## Vision & Objectives
- Demonstrate end-to-end technical feasibility of voice/text command control.
- Enable basic screen control from iOS (power, input/source, volume, mute, brightness where applicable; HDMI-CEC and vendor APIs).
- Establish a scalable, secure base architecture for future features.
- Create a functional product suitable for investor demonstrations.

---

## Core User Story (MVP)
“As a user, I can open the Jarvis iOS app, select a screen, and send a voice or text command (e.g., ‘Turn on Living Room TV’ or ‘Switch to HDMI 2’). The command is processed in the cloud and executed by the Raspberry Pi attached to that screen, with status and feedback returned to my app.”

## High-Level Architecture (MVP)
- Client (iOS):
  - Auth: Sign-in, session management.
  - Command UI: Voice capture (speech-to-text), text entry.
  - Device list: Discover, link, and select screens.
  - Feedback: Show command status and errors.
- Cloud Core:
  - API Gateway: HTTPS REST endpoints for auth, devices, commands.
  - Command Processor: Validates, routes, and persists command requests.
  - Device Registry: Maps users to devices/agents; stores capabilities.
  - Messaging Layer: Secure channel to agents (e.g., MQTT/WebSocket).
  - Observability: Logs, metrics, traces for demo reliability.
- Raspberry Pi Agent:
  - Secure Connect: Auth to cloud and subscribe to device-specific topics.
  - Command Executor: HDMI-CEC control, IR blaster fallback, vendor APIs.
  - Status Reporter: Ack/complete with result codes and optional telemetry.

## MVP Feature Scope
- Accounts & Auth: Single-user or simple email-based login, basic token auth.
- Device Onboarding: Pair Pi agent with a user and assign a friendly name.
- Basic Commands: Power on/off; input/source change; volume/mute; possibly brightness (monitor-dependent).
- Feedback: Command accepted, executing, success/failure.
- Reliability: Retries, timeouts, and clear error messages.

## Non-Goals (MVP)
- Complex multi-user orgs, roles, or granular RBAC.
- Rich scheduling/automation, scenes, or macros.
- Deep vendor integrations beyond simple HDMI-CEC + limited APIs.
- Offline-first mobile experience.

## Assumptions & Constraints
- Platforms: iOS (Swift/SwiftUI), Raspberry Pi OS (Linux), Cloud (AWS/Azure/GCP TBD).
- Connectivity: Pi agents have internet access; devices support HDMI-CEC or IR.
- Security: Basic authentication and encrypted messaging; device claims verified.
- Scalability: MVP supports small demo scale but designed to grow.
- Observability: Minimal but sufficient logging/metrics for demos.

## Interfaces (Initial)
- Mobile ↔ Cloud: REST/JSON; authentication via tokens.
- Cloud ↔ Agent: MQTT or WebSocket with per-device topics; payloads as JSON.
- Agent ↔ Screen: HDMI-CEC (via `cec-client`/libCEC), IR (via LIRC), vendor SDKs when available.

## Data Model (MVP, conceptual)
- User: id, email, display name.
- Device: id, userId, name, capabilities (power, input, volume), agentId.
- Command: id, deviceId, type (power_on, input_hdmi2, volume_set), parameters, status, timestamps.
- Agent: id, deviceId, status, lastSeen, version.

## Reliability & Safety
- Command lifecycle: received → dispatched → executing → completed/failed.
- Timeouts & retries: bounded; idempotent handling where feasible.
- Error taxonomy: network, auth, capability unsupported, device offline.

## Demo Scenario
- Onboard 2–3 devices with Pi sticks.
- Voice commands from iOS to turn on/off and switch inputs.
- Real-time status and simple analytics (e.g., command success rate).

## Future Extensions (Post-MVP)
- Scenes/macros (e.g., “Movie Night”) and scheduling.
- Multi-user sharing, roles, and orgs.
- Rich vendor integrations and device discovery.
- Cross-platform mobile and web console.
- Advanced telemetry, anomaly detection, and health scoring.

## Open Questions
- Cloud choice and managed services (API Gateway, MQTT broker, DB).
- Preferred auth (OAuth/Sign in with Apple) for iOS.
- Final messaging protocol (MQTT vs WebSocket) and QoS.
- Device onboarding UX (QR code, shared secret, or claim tokens).

## Success Criteria (MVP)
- End-to-end demo with at least two screens controlled via iOS.
- Stable commands for power and input switching under normal network conditions.
- Clear architecture foundation enabling quick iteration on new features.

---

## 📝 Session Notes

### January 10, 2026 - Sprint 6.1 Complete (EOR + Enriched Fixer)
- **Event Owner Resolution (EOR) System:**
  - Child elements (spans, SVG paths) now correctly resolve to interactive ancestors
  - `findEventOwnerCandidate()` JavaScript function in scene_graph.py
  - SVG structural rule: "En SVG no se clickea la geometría; se interactúa con el contenedor"
  - `EventOwnerCandidate` dataclass with selector and reason fields
  - `_resolve_event_owners()` deduplicates candidates pointing to same owner
- **Enriched Fixer Context:**
  - `get_failure_type()` classifies failures: `no_change`, `under_threshold`, `error`
  - `get_repair_context()` includes pixel_diff_ratio, threshold, interpretation
  - Fixer now knows "button works but visual feedback too subtle" vs "handler broken"
  - `REPAIR_SYSTEM_PROMPT` updated with specific instructions per failure type
  - Tested with GPT-5 Nano: fixer successfully repaired 0/3 → 2/2 responsive
- **Configuration Changes:**
  - `CUSTOM_LAYOUT_THINKING_BUDGET: 0` - Extended thinking disabled for latency
  - Using Opus 4.5 (`claude-opus-4-5-20251101`) for HTML generation
  - DirectFixer uses Codex-Max for repairs
- **Files Modified:**
  - `app/ai/scene/custom_layout/validation/contracts.py` - Added failure classification
  - `app/ai/scene/custom_layout/validation/fixer.py` - Enriched repair prompts
  - `app/ai/scene/custom_layout/validation/scene_graph.py` - EOR JavaScript
  - `app/ai/scene/custom_layout/validation/input_detector.py` - Owner resolution
  - `app/ai/scene/custom_layout/service.py` - Opus 4.5 integration
  - `app/ai/providers/openai_provider.py` - NO_TEMPERATURE_MODELS fix
  - `app/core/config.py` - Thinking budget disabled
- **Deployed to Fly.io:** https://xentauri-cloud-core.fly.dev/

### January 10, 2026 - Critical Bug Fixes (Validation Bypass + Dynamic Content)
- **Bug #1: Validation Passing with 33% Responsive Inputs**
  - **Root cause:** `is_interactive_layout` check skipped 70% threshold for layouts not in hardcoded list
  - **Example:** "visualization" layout type not in INTERACTIVE_LAYOUT_TYPES → bypassed check
  - **Fix:** Removed layout type dependency - if inputs are detected, they must respond
  - **Philosophy:** "Si el sistema vio un botón, ese botón debe responder. Ningún nombre lo exime de funcionar."
  - **File:** `app/ai/scene/custom_layout/validation/aggregator.py`
- **Bug #2: Dynamic JavaScript Content Not Detected**
  - **Root cause:** Scene graph extraction ran before JS `init()` functions created elements
  - **Example:** Trivia `loadQuestion()` creates 4 option divs dynamically → only static button detected
  - **Symptom:** Phase 4 found only 1 input when there should be 5 (4 options + 1 submit)
  - **Analysis:** `wait_until="networkidle"` only waits for network, not JS execution
  - **Fix:** Added `wait_for_load_state("domcontentloaded")` + 150ms buffer in sandbox.py
  - **File:** `app/ai/scene/custom_layout/validation/sandbox.py`
- **Bug #3: Disabled Buttons Passing Validation**
  - **Root cause:** Playwright can physically click disabled buttons, but JS handlers don't execute
  - **Example:** Trivia submit button has `disabled` until user selects an option
  - **Symptom:** Button showed cursor:not-allowed but passed as "responsive" due to visual change
  - **Fix:** Added `locator.is_disabled()` check before clicking in interaction_validator
  - **File:** `app/ai/scene/custom_layout/validation/interaction_validator.py`
- **Technical Debt TD-001:** Worker timeout during repair flow
  - Increased Gunicorn timeout from 120s to 300s as workaround
  - Proper fix: async/background job processing (future sprint)

### January 2026 - Sprint 6.0 Complete (Visual-based Validation System)
- **7-Phase Visual Validation Pipeline:**
  - Phase 1: Render validation (Playwright headless browser)
  - Phase 2: Visual snapshot with histogram analysis + blank page detection
  - Phase 3: Scene graph extraction from DOM (element positions, attributes)
  - Phase 4: Input candidate detection (buttons, links, interactive elements)
  - Phase 5: Interaction testing (click + before/after screenshot comparison)
  - Phase 6: Result aggregation (confidence score, failure summary)
  - Phase 7: DirectFixer repair (Codex-Max)
- **Key Concepts:**
  - 2% viewport threshold = 41,000 pixels must change for "responsive" classification
  - `VisualSnapshot` with histogram, mean_pixel, variance, non_background_ratio
  - `VisualDelta` compares before/after screenshots
  - `InputCandidate` with confidence score and priority for testing order
  - `InteractionResult` tracks visual_delta, scene changes, responsiveness
- **Contracts Module (`contracts.py`):**
  - `ValidationContract` - Input with thresholds and settings
  - `SandboxResult` - Final result with phases, interaction_results, confidence
  - `SceneNode`, `ObservedSceneGraph` for DOM representation
  - `BoundingBox` with area(), center(), in_viewport() methods
- **DirectFixer:**
  - Skips Gemini diagnosis, sends full context to Codex-Max
  - `build_repair_prompt()` includes all phase failures
  - Supports both regular and reasoning-enhanced repair
- **Configuration Settings:**
  - `VISUAL_VALIDATION_ENABLED: True`
  - `VISUAL_CHANGE_THRESHOLD: 0.05` (5% default, 2% in code)
  - `BLANK_PAGE_THRESHOLD: 0.95`
  - `MAX_INPUTS_TO_TEST: 10`
  - `INTERACTION_STABILIZATION_MS: 300`

### December 30, 2025 - Sprint 5.1.0 Complete (Pi Alexa Authentication)
- **New Endpoint: POST /intent/agent**
  - Authenticates via X-Agent-ID header instead of JWT
  - Same business logic as /intent (calls IntentService.process())
  - Designed for Pi Alexa voice input device
- **New Dependency: get_user_from_agent()**
  - Located in `app/deps.py`
  - Chain: agent_id → Device → User
  - Returns 401 if agent not paired or user not found
- **Documentation:**
  - Created `docs/PI_ALEXA_AUTHENTICATION.md` with full implementation plan
  - Updated API endpoints section in CONTEXT.md
  - Updated README.md with new endpoint
- **Security:**
  - UUID v4 agent IDs (2^122 possibilities)
  - HTTPS transport only
  - Same rate limiting as /intent
- **Deployment:**
  - Deployed to Fly.io production

### December 12, 2025 - Technical Debt Cleanup Complete
- **Phase 1: Tests First** (89 tests)
  - `test_action_response.py` - 47 tests for AI response schemas
  - `test_device_mapper.py` - 42 tests for device fuzzy matching
  - Established baseline before refactoring
- **Phase 2: Extract Service Layer** (69 tests added → 158 total)
  - Created `app/ai/actions/registry.py` with ActionRegistry
    - ActionDefinition dataclass for action metadata
    - 11 built-in actions with parameter validation
    - Custom validators (e.g., volume range 0-100)
    - Aliases ("turn_on" → "power_on")
  - Created `app/services/intent_service.py` with IntentService
    - IntentResult dataclass for standardized responses
    - IntentResultType enum for classification
    - All business logic extracted from router
  - `test_action_registry.py` - 37 tests
  - `test_intent_service.py` - 32 tests
- **Phase 3: Slim Down Router** (refactoring, no new tests)
  - Refactored `intent.py` from 1319 lines to 205 lines (84% reduction)
  - Router now delegates all business logic to IntentService
  - Clean separation: HTTP handling vs business logic
- **Phase 4: AI Module Tests** (85 tests added → 301 total)
  - `test_ai_providers.py` - 23 tests for base classes, mock patterns
  - `test_ai_router.py` - 29 tests for orchestrator, routing logic
  - `test_intent_parser.py` - 33 tests for parsing edge cases
  - All LLM calls mocked for fast, reliable tests
- **Phase 5: Documentation**
  - Updated CONTEXT.md with new architecture
  - Added Intent Processing Architecture diagram
  - Documented IntentService and ActionRegistry
  - Updated test file inventory

**Final Stats:**
- 301 tests passing ✅
- Router reduced 84% (1319 → 205 lines)
- Service layer: 1056 lines of business logic
- Action registry: 11 built-in actions with validation

### December 10, 2025 - Sprint 3.6 Complete
- **All Bugs Fixed:**
  - Schema mismatch (device_type) - resolved with getattr() fallback
  - GPT-4o JSON parsing - improved error handling and logging
  - Calendar date parameter - now passes through to simulator iframe URL
- **UnifiedContext System:** Single source of truth for all AI models
  - `UnifiedContext` dataclass with user, devices, OAuth status
  - `DeviceCapability` with can_power_control, can_show_content flags
  - `OAuthStatus` tracking Google Calendar, Drive availability
  - `build_unified_context()` fetches and assembles request-scoped context
- **Base Prompt Templates:** DRY principle for AI prompts
  - `build_router_prompt()` - Gemini orchestrator prompt
  - `build_executor_prompt()` - GPT-4o execution prompt
  - `build_reasoner_prompt()` - Claude reasoning prompt
  - `build_intent_prompt()` - Gemini intent parser prompt
  - All accept UnifiedContext and inject capabilities dynamically
- **Structured Action Responses:** Pydantic schemas for GPT-4o JSON
  - `ActionResponse` - Single action with device, parameters, confidence
  - `ClarificationResponse` - Missing information request
  - `ActionSequenceResponse` - Multi-step actions
  - `parse_action_response()` - Validates and parses GPT-4o output
- **Execution Prompts:** GPT-4o specific prompt engineering
  - System prompt with JSON schema and examples
  - 7 detailed examples: clear requests, ambiguity, sequences, errors
  - Few-shot learning for consistent JSON output
- **Intent Router Updates:**
  - `_handle_complex_task()` now uses UnifiedContext
  - `_execute_gpt_action()` helper for action execution
  - Calendar date parameter passthrough to display URL
- **Calendar Date Support:**
  - Added `date` query parameter to `GET /cloud/calendar`
  - Endpoint accepts YYYY-MM-DD format
  - Date now properly passed to simulator iframe

### December 4, 2025 - Sprint 3.5 Complete
- **Environment Module Architecture:** Modular structure for external integrations
  - Base interfaces: `EnvironmentProvider`, `EnvironmentService`
  - Provider isolation: Google, Microsoft, Apple independent
  - Service modularity: Calendar, Drive, Gmail as separate modules
- **Google OAuth Integration:**
  - Full OAuth 2.0 authorization code flow
  - Token storage in `OAuthCredential` model
  - Automatic token refresh when expired
  - Endpoints: `/auth/google/login`, `/auth/google/callback`, `/auth/google/status`
- **Google Calendar Client:**
  - Fetch upcoming events from user's calendar
  - Support for today, week, and custom date ranges
  - List available calendars
- **Calendar HTML Renderer:**
  - Optimized for Chromium kiosk mode on Raspberry Pi
  - Dark/light theme support
  - Auto-refresh meta tag
  - Clean, readable typography for TV display
- **Cloud Content Endpoints:**
  - `GET /cloud/calendar` - Rendered HTML calendar
  - `GET /cloud/calendar/preview` - Demo without auth
  - `GET /cloud/calendar/status` - Integration status
- **Display Simulator:**
  - Browser-based display that acts as virtual Raspberry Pi
  - WebSocket connection (same as real Pi)
  - Content persistence via localStorage (survives page refresh)
  - Signed content tokens for iframe authentication
  - Keyboard shortcuts: L=logs, ESC=clear, F=fullscreen
- **Content Token Service:**
  - Short-lived JWT tokens (5 min) for iframe URLs
  - Solves iframe authentication problem (can't use headers)
  - Automatic token validation in cloud endpoints
- **Database Migration:** New `oauth_credentials` table
- All code thoroughly documented with learning comments

### December 4, 2025 - Sprint 3 Complete
- **AI Provider Clients:** Unified interface for Gemini, OpenAI, and Anthropic
  - Gemini 2.5 Flash Lite (orchestrator + simple tasks)
  - GPT-4o (complex execution: code, tools)
  - Claude 3 Haiku (complex reasoning: analysis, planning)
- **AI Router (Orchestrator):** Full intelligent routing implemented
  - Analyzes request complexity before processing
  - Routes SIMPLE → Gemini Intent Parser
  - Routes COMPLEX_EXECUTION → GPT-4o direct response
  - Routes COMPLEX_REASONING → Claude direct response
- **Intent Parser:** LLM-powered NLU extracts structured intents
  - Supports: device_command, device_query, system_query, conversation
  - Actions: power_on/off, set_input, volume, mute, status
- **Device Mapper:** Fuzzy matching for device names
  - Handles variations: "living room tv" → "Living Room TV"
  - Token matching and Levenshtein similarity
- **POST /intent Endpoint:** Full natural language command processing with routing
- **Unified AIMonitor (DRY):** Single class for logging + metrics
  - Replaced separate AILogger and AIMetrics
  - One call tracks both logs and metrics
  - Cost estimation per provider
- **Prompt Engineering:** Separate templates for routing and intent extraction
- All code thoroughly documented

### December 2, 2025 - Sprint 2 Complete
- **Device CRUD:** Full REST endpoints for managing devices
- **Pairing Service:** 6-character codes, 15-min TTL, one-time use
- **WebSocket Hub:** Connection manager for Pi agents (device_id → connection)
- **Command Routing:** Send commands through WebSocket to connected devices
- **Test Suite:** Pytest tests for devices, pairing, and WebSocket manager
- All code has detailed comments for learning

### December 2, 2025 - Sprint 1 Complete
- Created project structure with FastAPI
- Implemented User and Device models with SQLAlchemy
- Added auth endpoints: register and login with JWT
- Added protected /users/me endpoint
- Configured PostgreSQL with Docker
- All code files have detailed comments for learning
- API running locally on port 8000

### December 22, 2025 - Sprint 4.0 Complete (Scene Graph - Dynamic Display Layouts)
- **Scene Graph Architecture:**
  - New `app/ai/scene/` module for dynamic display layouts
  - Semantic vs Technical layers: LayoutIntent (fullscreen, sidebar, dashboard) vs LayoutEngine (grid, flex, absolute)
  - Embedded Data Pattern: Backend fetches all data, Pi just renders
  - ComponentPriority system for responsive behavior (primary/secondary/tertiary)
- **Scene Graph Schemas (`app/ai/scene/schemas.py`):**
  - `SceneGraph` - Main output model with layout, components, global_style, metadata
  - `SceneComponent` - Individual UI widget with type, position, props, data
  - `LayoutSpec` - Combines semantic intent with technical engine config
  - `ComponentPosition` - Grid/Flex/Absolute positioning properties
  - `ComponentStyle` - Visual styling (background, text_color, border_radius)
  - `LayoutHint` - Parsed hints from natural language ("calendar left")
  - Helper methods: `get_primary_component()`, `filter_by_priority()`, `get_component_by_id()`
- **Component Registry (`app/ai/scene/registry.py`):**
  - `ComponentRegistry` singleton with 17 components (12 MVP + 5 Sprint 4.0.3)
  - Calendar: calendar_day, calendar_week, calendar_month, calendar_widget, calendar_agenda
  - Time: clock_digital, clock_analog
  - Weather: weather_current
  - Utility: text_block, spacer, image_display, web_embed
  - `to_prompt_context()` generates Claude-friendly component documentation
  - `validate_component()` and `get_required_data_keys()` for validation
- **Default Scene Templates (`app/ai/scene/defaults.py`):**
  - `CALENDAR_FULLSCREEN` - Single component fills screen
  - `CALENDAR_SIDEBAR` - Calendar left (70%) + clock right (30%)
  - `CALENDAR_AGENDA` - Agenda list with clock overlay
  - `DASHBOARD` - 2x2 grid with calendar, clock, weather, text
  - `CLOCK_FULLSCREEN` - Large digital clock
  - `get_default_scene()` factory function
- **Scene Service (`app/ai/scene/service.py`):**
  - `SceneService` main service class
  - `generate_scene()` - Creates SceneGraph from layout_hints
  - `normalize_layout_hints()` - Parses natural language to LayoutHint objects
  - `populate_scene_data()` - Fetches calendar/weather data and embeds in components
  - Uses `anthropic_provider.generate_json()` for Claude generation (DRY)
  - Supports both default templates and custom Claude-generated layouts
- **Scene Prompts (`app/ai/prompts/scene_prompts.py`):**
  - System prompt with Scene Graph schema and examples
  - Component registry documentation injection
  - User prompt builder with layout hints and preferences
- **Intent Integration:**
  - `DisplayContentIntent` schema in `app/ai/intent/schemas.py`
  - Fields: info_type, layout_type, layout_hints, device_name
  - `_handle_display_content()` handler in IntentService
  - Intent parser updated for DISPLAY_CONTENT type
- **DRY Compliance:**
  - SceneService reuses `anthropic_provider.generate_json()`
  - No duplicate Claude API implementation
  - Follows existing ActionRegistry pattern for ComponentRegistry
- **Tests:**
  - `test_scene_graph.py` - 31 tests for Scene Graph functionality
  - Schema validation, registry operations, default templates
  - Service methods and data population

### December 27, 2025 - Sprint 4.1.0 Complete (Intelligent Conversations & Real-Time Data)
- **AI Model Upgrades:**
  - OpenAI: Migrated from GPT-4o to GPT-5.2 (Responses API)
  - Anthropic: Migrated from Claude Sonnet 4.5 to Claude Opus 4.5
  - Updated `app/ai/providers/openai_provider.py` for new Responses API
- **Multilingual & Context-Aware System:**
  - `UNIVERSAL_MULTILINGUAL_RULE` in all AI prompts
  - Responses match user's language automatically (Spanish, English, etc.)
  - `UnifiedContext` includes user name, device count, connected services
  - `build_assistant_system_prompt(context)` for personalized prompts
- **Conversation History Tracking:**
  - `ConversationContextService` extended with `conversation_history` list
  - `add_conversation_turn()` saves user/assistant exchanges
  - `get_conversation_history()` retrieves full conversation
  - `ConversationContext` dataclass includes history field
  - Multi-turn conversations work across all AI models
- **Follow-up Intent Support:**
  - `set_pending_content_request()` stores pending generation requests
  - `get_pending_content_request()` retrieves for follow-ups
  - Detects "sí", "hazlo", "do it", "adelante" as confirmations
  - No more stuck confirmation loops!
- **Content Generation vs Document Detection:**
  - Updated `intent_prompts.py` with explicit rules and 8 new examples
  - "Necesito un template" → CONVERSATION (generates content)
  - "Resume el documento de..." → DOC_QUERY (references document)
  - Updated `router_prompts.py` for SIMPLE classification of content requests
- **Dynamic Scene Graph Data via Gemini:**
  - `_fetch_realtime_data_for_scene()` uses Gemini web search
  - Real-time weather data embedded in scene components
  - `_extract_location_from_request()` parses locations from text
  - `is_placeholder: false` when real data is available
  - Fixed `_parse_scene_response()` to preserve Claude's data field
- **Calendar Queries Improvements:**
  - `_generate_calendar_response()` for context-aware, multilingual responses
  - `smart_search()` consolidated with `date_range` parameter (DRY)
  - Removed `smart_search_with_date()` duplication
  - All calendar responses now respect user's language
- **Bug Fixes:**
  - Fixed indentation error in `_handle_doc_query()`
  - Fixed `SceneMetadata.refresh_seconds` validation error
  - Fixed scene component data being overwritten with `{}`
  - Fixed location extraction regex for multi-word places

### December 28, 2025 - Sprint 4.4.0 Complete (Prompt Coordination & Context Harmonization)
- **Intent Prompts Optimization:**
  - Reduced `intent_prompts.py` from 2191 lines to 508 lines (76% reduction)
  - Reduced examples from 137 to 18 (2 per intent type: 9 intent types)
  - Added CRITICAL JSON RULES at the beginning
  - Fixed CONVERSATION vs DISPLAY_CONTENT contradiction
  - Cleaner, more maintainable prompt structure
- **Scene Prompts Improvements:**
  - Fixed KeyError with `.format()` → changed to `.replace()` for placeholders
  - Changed from `{components}` to `__COMPONENTS__` to avoid JSON conflicts
  - Added SPATIAL KEYWORD DETECTION section (lines 112-128)
  - Improved requirement 11 for multi-part requests
- **Default Scene Detection:**
  - Added `user_request` parameter to `detect_default_scene_type()`
  - Added content generation keyword detection in `defaults.py`
  - Returns `None` when generation needed (forces Claude generation)
  - Keywords: crea, genera, create, plan, ideas, summary, etc.
- **Service Updates:**
  - Updated `service.py` to pass `user_request` to fallback detection
  - Added exception when `scene_type is None` (requires Claude)
  - Prevents incorrect default scene selection for generated content
- **Bug Fixes:**
  - Fixed KeyError '"type"' in scene_prompts.py
  - Fixed SyntaxError in intent_prompts.py rebuild
  - Fixed Gemini JSON malformation from prompt overload
  - Fixed spatial keyword detection ("left", "right", "top", "bottom")

### December 28, 2025 - Sprint 4.5.0 Planned (Intelligent Execution & Context Memory)
- **Problem Analysis:**
  - **Problem #1:** Gemini doesn't execute searches for general queries (ABA updates)
    - Root cause: Missing Spanish keywords ("últimas", "actualizaciones")
    - Root cause: Prompts suggest web search but don't enforce execution
    - Root cause: Keyword-based logic instead of intent-based
  - **Problem #2:** Weather searches work but context not remembered for display
    - Root cause: Weather responses NOT saved as generated_content
    - Root cause: Scene prompts lack anaphoric resolution instructions
    - Root cause: Intent parser doesn't resolve "muéstramelo" references
- **Evidence-Based Plan Created:**
  - `SPRINT_4.5.0_UNIFIED_PLAN.md` - Comprehensive plan for both problems
  - 9 GAPs identified with exact file locations and line numbers
  - Critical fixes: ~37 minutes implementation time
  - Success metrics defined: 0% → 95% for both problems
- **Files Analyzed:**
  - `app/services/intent_service.py:1606-1615` - Search keyword detection
  - `app/services/intent_service.py:1665-1676` - Content detection
  - `app/services/intent_service.py:2335-2388` - _detect_content_type()
  - `app/ai/prompts/assistant_prompts.py:102` - Web search instruction
  - `app/ai/prompts/scene_prompts.py` - Missing anaphoric resolution
  - `app/ai/intent/parser.py:130-131` - Context usage
- **Implementation NOT started yet** - awaiting user approval

### December 22, 2025 - Sprint 4.0.3 Complete (Multi-Action Intent Support)
- **Multi-Action Intent Support:**
  - `SequentialAction` model in `app/ai/intent/schemas.py`
  - `sequential_actions: List[SequentialAction]` field in `DeviceCommand`
  - Allows chaining actions: "clear screen AND show calendar"
  - Detection rules for Spanish/English connectors (y, and, then, después)
  - `_extract_sequential_actions()` in parser.py
  - `_execute_sequential_actions()` in intent_service.py
  - Response includes `actions_executed[]` and `commands_sent` count
- **Compound Intent Handling (doc_query + display):**
  - `also_display: bool` field in `DocQueryIntent`
  - `display_device: Optional[str]` for target device
  - "Dame un resumen y ábreme el documento en pantalla" → summarize + display
  - Handler in `_handle_doc_query()` sends show_content command
- **AI Document Intelligence for Scene Graph:**
  - `content_request` prop for custom AI-generated content
  - `content_type` prop: impact_phrases, script, key_points, action_items, summary, agenda
  - `_generate_custom_content()` method using Gemini
  - `formatGeneratedContent()` JavaScript renderer with markdown support
- **New Scene Graph Components:**
  - `meeting_detail` - Meeting info with attendees, location, links
  - `countdown_timer` - Countdown to target time
  - `doc_summary` - Document summary with AI-generated content
  - `doc_preview` - Document preview with key points
  - `event_countdown` - Countdown to next calendar event
- **Bug Fixes & Improvements:**
  - Router fix: DISPLAY_CONTENT classified as SIMPLE (not complex_execution)
  - Spanish support in Device Mapper (translations + stop words)
  - Default styling fallbacks in prompts, service, and renderer
  - Document fetching via `meeting_link_service.find_meeting_with_doc()`
  - WebSocket reconnection with exponential backoff
  - Manual reconnect button in simulator (press 'R')
  - Fixed JavaScript regex escaping in formatGeneratedContent()

### December 20, 2025 - Sprint 3.9 Complete (Google Docs Intelligence)
- **Google Docs Client:**
  - `GoogleDocsClient` with Google Docs API v1 integration
  - `get_document()` - Fetch document content and metadata
  - `validate_access()` - Abstract method implementation for EnvironmentService
  - URL validation and doc_id extraction utilities
- **OAuth Scopes Update:**
  - Added `DOCS_SCOPES` (documents.readonly) to OAuth flow
  - Combined with `CALENDAR_SCOPES` in `/auth/google/login`
- **DocQueryIntent Schema:**
  - New intent type for document operations
  - Fields: doc_url, meeting_search, device_name
  - ActionTypes: READ_DOC, LINK_DOC, OPEN_DOC, SUMMARIZE_MEETING_DOC, CREATE_EVENT_FROM_DOC
- **DocIntelligenceService:**
  - LLM-powered document analysis (summarize, extract key points)
  - `extract_meeting_details()` - Parse meeting info from documents
  - `ExtractedMeetingDetails` dataclass with needs_clarification flag
- **Create Event from Doc Flow:**
  - `_handle_create_event_from_doc()` handler in IntentService
  - Extracts title, date, time, duration from document content
  - Stores pending with doc_id, doc_url, source fields
  - Links document to created calendar event in description
- **ConversationContextService (TTL 300s):**
  - Tracks last_event, last_doc, last_search per user
  - Enables "this event", "that doc" references
  - `set_last_event()`, `set_last_doc()`, `get_last_event()`, etc.
- **Bug Fixes:**
  - Duration extraction: Changed condition to update when intent differs from pending
  - Context storage: `_handle_confirm_create()` now stores event and doc context
  - Null handling: `device_name = data.get("device_name") or "unknown device"`
  - Intent parser: Added `create_event_from_doc` to action mapping
- **New Tests:**
  - `test_conversation_context.py` - Context service tests
  - `test_doc_intelligence.py` - Document analysis tests
- **4,827 lines added across 25 files**

### December 17, 2025 - Sprint 3.9.1 Complete (AI Layer Bug Fixes)
- **Bug #1: Timezone Missing in EDIT Flow** ✅
  - Root cause: `_handle_confirm_edit()` didn't call `get_user_timezone()`
  - Symptom: Events edited to 4pm would display as 11am (UTC interpretation)
  - Fix: Added `get_user_timezone()` call and pass to `processed_changes`
  - Passes timezone to EventUpdateRequest for proper API handling
- **Bug #2: Parser Ignoring Pending Context** ✅
  - Root cause: Parser only extracted "devices" from context, ignored pending_operation
  - Symptom: "Yes" after event creation might not route to CONFIRM_CREATE
  - Fix: Added pending_operation context extraction in `intent/parser.py`
  - Now includes: has_pending_create/edit/delete, pending_op_type, age, hints
- **Bug #3: TTL Too Short** ✅
  - Root cause: TTL_SECONDS = 60 was too aggressive for confirmation flows
  - Symptom: Users saying "yes" after 1 minute got "no pending event" errors
  - Fix: Changed TTL from 60s to 120s in both pending services
  - Updated docstrings and tests to reflect new timeout
- **New Tests:**
  - `tests/test_sprint_391_bugfixes.py` - 13 new tests covering all bug fixes
  - Timezone extraction and pass-through tests
  - Parser pending context extraction tests
  - TTL constant verification tests
- **648 tests passing** ✅

### December 16, 2025 - Sprint 3.9 Complete (Calendar Edit & Delete)
- **Calendar Edit Handler:**
  - `_handle_edit_existing_event()` - Find events by semantic search
  - Uses `calendar_search_service.smart_search()` for LLM matching (typos, synonyms, translations)
  - Stores pending edit in `pending_edit_service` for confirmation
  - `_handle_confirm_edit()` - Context-aware confirmation (checks pending_event first)
  - `_process_time_changes()` - Combines original event date with new time values
  - Validation for time-only changes (e.g., "change to 7am")
- **Calendar Delete Handler:**
  - `_handle_delete_existing_event()` - Find events by semantic search
  - Stores pending delete in `pending_edit_service` for confirmation
  - `_handle_confirm_delete()` - Context-aware confirmation
- **PendingEditService:**
  - `store_pending_edit()` - Handles both CalendarEvent objects and dicts
  - `get_pending()` - Retrieve pending operation (edit/delete)
  - `select_event()` - User selects from multiple matches
  - `confirm_pending()` - Execute the edit or delete
  - Converts CalendarEvent to MatchingEvent format
- **Context-Aware Confirmation:**
  - `_handle_confirm_create()` now checks pending_edit first
  - `_handle_confirm_edit()` checks pending_event first
  - `_handle_confirm_delete()` checks all pending services
  - Prevents "yes confirm" routing to wrong handler
- **Bug Fixes:**
  - Removed invalid `refresh_token` from GoogleCalendarClient (4 locations)
  - Fixed `search_result.get()` to direct list assignment
  - Fixed ValidationError for time-only datetime strings
- **622 tests passing** ✅

### December 15, 2025 - Sprint 3.8 Complete (Calendar Event Creation)
- **Calendar Create Handler:**
  - `_handle_create_event()` - Parse user intent for event creation
  - Extracts title, date, time, duration, description from natural language
  - Uses LLM to parse complex date expressions ("next Friday", "tomorrow at 3pm")
  - Stores pending event in `pending_event_service` for confirmation
  - `_handle_confirm_create()` - Confirms and creates the event
- **PendingEventService:**
  - `store_pending()` - Store event details awaiting confirmation
  - `get_pending()` - Retrieve pending event for user
  - `confirm_pending()` - Create event via Google Calendar API
  - `cancel_pending()` - User cancels creation
- **Natural Language Parsing:**
  - Relative dates: "tomorrow", "next week", "in 3 days"
  - Time expressions: "at 3pm", "from 2-4pm", "for 2 hours"
  - Combined: "meeting with John tomorrow at 10am for 1 hour"

### December 14, 2025 - Sprint 3.7 Complete (Smart Calendar Search)
- **CalendarSearchService:**
  - `smart_search()` - LLM-powered semantic calendar search
  - Handles typos, synonyms, translations, abbreviations
  - Returns `SmartSearchResult` with events, corrected_query, no_match_found
  - Separates search logic from intent handler (Single Responsibility)
- **SmartSearchResult Dataclass:**
  - `events: List[CalendarEvent]` - Matching events
  - `corrected_query: Optional[str]` - LLM-corrected search term
  - `no_match_found: bool` - True if no events match
  - `error: Optional[str]` - Error message if any
- **Query Correction:**
  - "dentist appt" → "Dentist Appointment"
  - "mtg w/ john" → "Meeting with John"
  - "cita médico" → "Doctor Appointment" (translation)
- **Integration:**
  - Used by `_handle_edit_existing_event()`
  - Used by `_handle_delete_existing_event()`
  - Replaces direct Google Calendar API search

### Next Session Tasks (Sprint 4 - Raspberry Pi Agent)
1. Create Jarvis_Stick project structure (Python)
2. Implement WebSocket client to connect to cloud
3. Pairing flow implementation
4. HDMI-CEC command execution (cec-client)
5. Command acknowledgment and status reporting
6. Local configuration and persistence
7. Test end-to-end with real Raspberry Pi hardware

---

## 🚀 Sprint 4.0 Plan: Raspberry Pi Agent

**Goal:** Create the edge agent software that runs on Raspberry Pi devices connected to screens, enabling real hardware control.

### Sprint 4.0.1: Project Structure
- Create `Jarvis_Stick/` project directory (Python)
- Set up virtual environment and dependencies
- Configuration management (device ID, cloud URL, auth)
- Logging and error handling framework

### Sprint 4.0.2: WebSocket Client
- Implement WebSocket client to connect to Jarvis Cloud
- Automatic reconnection with exponential backoff
- Message queue for offline operation
- Heartbeat/ping-pong for connection health

### Sprint 4.0.3: Pairing Flow
- Display pairing code on connected screen
- HTTP callback to cloud with pairing code
- Receive and store device credentials
- Transition to paired state

### Sprint 4.0.4: HDMI-CEC Command Execution
- Integrate with `cec-client` (libCEC)
- Commands: power_on, power_off, set_input, volume_up/down, mute
- Parse CEC responses for device state
- Error handling for unsupported devices

### Sprint 4.0.5: Content Display
- Chromium kiosk mode for content display
- Handle SHOW_CONTENT commands (calendar, docs)
- URL navigation and refresh
- CLEAR_CONTENT to return to idle screen

### Sprint 4.0.6: Command Acknowledgment
- Send ACK/NACK for received commands
- Report command execution status
- Periodic status updates to cloud
- Device capability reporting

### Sprint 4.0.7: Local Persistence
- SQLite for local state and queue
- Survive reboots and network outages
- Sync pending commands when reconnected
- Configuration persistence

### Sprint 4.0.8: End-to-End Testing
- Test with real Raspberry Pi 4 hardware
- Test all command types through full stack
- Latency and reliability measurements
- Demo scenario: voice command → TV control

---

## ⚠️ Technical Debt

### TD-001: Synchronous Validation Pipeline (Sprint 6.1)
**Status:** OPEN
**Severity:** Medium
**Added:** January 10, 2026

**Problem:**
The visual validation pipeline (Opus generation + validation + repair + re-validation) can take 3-5 minutes, which exceeds typical HTTP timeouts.

**Current Workaround:**
Increased Gunicorn worker timeout from 120s to 300s in `start.sh`.

**Proper Solution:**
Implement async/background job processing:
1. Return immediately with `{"status": "processing", "job_id": "xxx"}`
2. Process validation in background worker (Celery/RQ)
3. Send result via WebSocket when complete
4. Client polls or receives push notification

**Files Affected:**
- `start.sh` - timeout=300 workaround
- `app/ai/scene/custom_layout/service.py` - sync pipeline
- `app/services/intent_service.py` - calls sync pipeline

**Impact:**
- Long HTTP requests block the single Gunicorn worker
- Poor UX (user waits 3-5 minutes with no feedback)
- Risk of timeout on slower generations

---

This context file is the foundation for AI-assisted coding. It provides scope, architecture, and assumptions so future tasks can scaffold the repo (API, agent, and iOS stubs), implement minimal features, and prepare a reliable investor demo.