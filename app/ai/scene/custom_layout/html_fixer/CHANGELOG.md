# HTML Fixer Changelog

All notable changes to the html_fixer module are documented in this file.

## [1.0.0] - 2025-01-16

### Added

#### Core Pipeline (Sprints 0-7)
- **Orchestrator**: Pipeline coordinator with history, rollback, and metrics tracking
- **Error Classification**: 16 error types with deterministic/LLM routing
- **Deterministic Rules**: 6 rules for common CSS/visibility issues
- **LLM Fixer**: Gemini-powered surgical fixes for complex cases
- **Sandbox Validation**: Playwright-based responsive testing
- **Diff Engine**: Screenshot comparison for visual validation

#### Deterministic Rules
- `VisibilityRestoreRule` (priority 5): Fix opacity-0, hidden, invisible
- `ZIndexFixRule` (priority 15): Resolve z-index conflicts and missing z-index
- `PointerEventsFixRule` (priority 25): Fix blocked/intercepted pointer events
- `PassthroughRule` (priority 26): Make decorative overlays pass-through
- `Transform3DFixRule` (priority 30): Fix backface-visibility and offscreen transforms
- `VisualFeedbackAmplifierRule` (priority 50): Amplify subtle click feedback

#### Error Types Supported
- Visibility: `INVISIBLE_OPACITY`, `INVISIBLE_DISPLAY`, `INVISIBLE_VISIBILITY`
- Z-Index: `ZINDEX_CONFLICT`, `ZINDEX_MISSING`
- Pointer Events: `POINTER_BLOCKED`, `POINTER_INTERCEPTED`
- Transforms: `TRANSFORM_3D_HIDDEN`, `TRANSFORM_OFFSCREEN`
- Feedback: `FEEDBACK_TOO_SUBTLE`, `FEEDBACK_MISSING`
- JavaScript: `JS_SYNTAX_ERROR`, `JS_MISSING_FUNCTION`, `JS_MISSING_DOM_ELEMENT`, `JS_UNDEFINED_VARIABLE`
- `UNKNOWN`

#### Sprint 8 Additions
- **Metrics Dashboard**: CLI dashboard for tracking fix rates and performance
- **Golden Set Tests**: 70%+ pass rate regression tests with 20+ fixtures
- **Parametrized Tests**: 57 tests covering all deterministic rules
- **Performance Tests**: 8 smoke tests for core components
- **CI/CD**: GitHub Actions workflow for automated testing
- **API Documentation**: Complete reference for all public APIs
- **Contributing Guide**: Development setup and contribution guidelines

### Metrics
- 257+ tests passing
- 6 deterministic rules
- 16 error types classified
- 20+ HTML fixtures (trivia, dashboard, modals, edge cases)
- 70%+ golden set pass rate

### Architecture
- Module location: `app/ai/scene/custom_layout/html_fixer/`
- Integration: Xentauri Cloud Core Scene Graph system
- Stack: Python 3.12, FastAPI, Playwright, BeautifulSoup

## Sprint History

| Sprint | Focus | Key Deliverables |
|--------|-------|------------------|
| 0 | Foundation | Contracts, fixtures, base architecture |
| 1 | Analysis | TailwindAnalyzer, DOMParser |
| 2 | Validation | Playwright sandbox validator |
| 3 | Deterministic | Core rules (visibility, z-index, pointer) |
| 4 | Enhanced Rules | Transform3D, VisualFeedback rules |
| 5 | Integration | Orchestrator, Diff Engine |
| 6 | LLM | Gemini-powered surgical fixer |
| 7 | Orchestration | History, rollback, cascading validation |
| 8 | Quality | Test suite, documentation, CI/CD, release |

---

## Future Improvements

- [ ] Additional deterministic rules for common patterns
- [ ] Browser-based visual validation
- [ ] Rule priority optimization
- [ ] LLM cost reduction strategies
- [ ] Incremental fixing for large documents
