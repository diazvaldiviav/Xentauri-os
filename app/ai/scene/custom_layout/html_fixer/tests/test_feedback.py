"""Tests para el módulo Human Feedback."""

import pytest
from ..feedback.element_mapper import ElementMapper, ElementInfo, PreparedHTML
from ..feedback.annotation_injector import AnnotationInjector
from ..feedback.feedback_merger import FeedbackMerger
from ..contracts.feedback import (
    UserFeedback,
    FeedbackStatus,
    MergedError,
)


class TestElementMapper:
    """Tests para ElementMapper."""

    @pytest.fixture
    def mapper(self):
        return ElementMapper()

    def test_maps_buttons(self, mapper):
        """Debe mapear botones correctamente."""
        html = """
        <html>
        <body>
            <button class="btn-1">Click 1</button>
            <button class="btn-2">Click 2</button>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 2
        assert 'data-vid="1"' in result.html
        assert 'data-vid="2"' in result.html
        assert result.element_map[1].tag == "button"
        assert "btn-2" in result.element_map[2].classes

    def test_maps_onclick_elements(self, mapper):
        """Debe mapear elementos con onclick."""
        html = """
        <html>
        <body>
            <div onclick="handleClick()">Clickable div</div>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 1
        assert result.element_map[1].attributes.get('onclick') == "handleClick()"

    def test_no_duplicates(self, mapper):
        """No debe crear duplicados para elementos que matchean múltiples selectores."""
        html = """
        <html>
        <body>
            <button onclick="submit()" role="button">Submit</button>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        # Solo debe contar una vez aunque matchea múltiples selectores
        assert result.total_elements == 1

    def test_injects_validation_script(self, mapper):
        """Debe inyectar el script de validación."""
        html = """
        <html>
        <body>
            <button>Click</button>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert 'data-validation-script="true"' in result.html
        assert 'postMessage' in result.html
        assert 'ELEMENT_CLICKED' in result.html

    def test_maps_inputs(self, mapper):
        """Debe mapear inputs."""
        html = """
        <html>
        <body>
            <input type="text" name="email" />
            <input type="submit" value="Send" />
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 2
        assert result.element_map[1].tag == "input"

    def test_maps_links(self, mapper):
        """Debe mapear links con href."""
        html = """
        <html>
        <body>
            <a href="/about">About</a>
            <a>No href - ignored</a>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        # Solo el link con href debe ser mapeado
        assert result.total_elements == 1
        assert result.element_map[1].tag == "a"

    def test_maps_role_button(self, mapper):
        """Debe mapear elementos con role=button."""
        html = """
        <html>
        <body>
            <div role="button">Custom button</div>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 1
        assert result.element_map[1].attributes.get('role') == "button"

    def test_empty_html(self, mapper):
        """Debe manejar HTML sin elementos interactivos."""
        html = """
        <html>
        <body>
            <div>Just text</div>
        </body>
        </html>
        """
        result = mapper.prepare(html)

        assert result.total_elements == 0
        assert len(result.element_map) == 0


class TestAnnotationInjector:
    """Tests para AnnotationInjector."""

    @pytest.fixture
    def injector(self):
        return AnnotationInjector()

    def test_injects_working_comment(self, injector):
        """Debe inyectar comentario para elementos working."""
        html = '<html><body><button data-vid="1">Click</button></body></html>'
        feedback = [UserFeedback(vid=1, status=FeedbackStatus.WORKING)]

        result = injector.inject(html, feedback)

        assert "[ELEMENT #1] status:working" in result.html
        assert result.working_elements == [1]
        assert result.broken_elements == []

    def test_injects_broken_comment_with_message(self, injector):
        """Debe inyectar comentario broken con mensaje del usuario."""
        html = '<html><body><button data-vid="2">Pay</button></body></html>'
        feedback = [UserFeedback(
            vid=2,
            status=FeedbackStatus.BROKEN,
            message="should open payment modal"
        )]

        result = injector.inject(html, feedback)

        assert 'status:broken' in result.html
        assert 'user_feedback:"should open payment modal"' in result.html
        assert result.broken_elements == [2]

    def test_injects_global_feedback(self, injector):
        """Debe inyectar feedback global."""
        html = '<html><body><div>Content</div></body></html>'

        result = injector.inject(
            html=html,
            element_feedback=[],
            global_feedback=["Missing back button", "Need footer"]
        )

        assert '[GLOBAL FEEDBACK] "Missing back button"' in result.html
        assert '[GLOBAL FEEDBACK] "Need footer"' in result.html
        assert result.global_feedback_count == 2

    def test_remove_annotations(self, injector):
        """Debe remover anotaciones correctamente."""
        html = '''
        <html><body>
        <!-- [ELEMENT #1] status:working -->
        <button data-vid="1">Click</button>
        <script data-validation-script="true">...</script>
        <style data-validation-styles="true">.test{}</style>
        </body></html>
        '''

        clean = injector.remove_annotations(html)

        assert 'data-vid' not in clean
        assert '[ELEMENT #1]' not in clean
        assert 'data-validation-script' not in clean
        assert 'data-validation-styles' not in clean

    def test_ignores_untested_elements(self, injector):
        """No debe inyectar comentarios para elementos untested."""
        html = '<html><body><button data-vid="1">Click</button></body></html>'
        feedback = [UserFeedback(vid=1, status=FeedbackStatus.UNTESTED)]

        result = injector.inject(html, feedback)

        assert "[ELEMENT #1]" not in result.html
        assert result.annotations_count == 0

    def test_handles_missing_element(self, injector):
        """Debe manejar feedback para elementos que no existen."""
        html = '<html><body><button data-vid="1">Click</button></body></html>'
        feedback = [UserFeedback(vid=99, status=FeedbackStatus.BROKEN, message="not found")]

        result = injector.inject(html, feedback)

        # No debe fallar, simplemente ignora el elemento inexistente
        assert result.annotations_count == 0


class TestFeedbackMerger:
    """Tests para FeedbackMerger."""

    @pytest.fixture
    def merger(self):
        return FeedbackMerger()

    @pytest.fixture
    def element_map(self):
        return {
            1: {'vid': 1, 'tag': 'button', 'classes': ['btn-primary'], 'element_id': None},
            2: {'vid': 2, 'tag': 'button', 'classes': ['btn-submit'], 'element_id': 'submit-btn'},
        }

    def test_user_broken_no_sandbox(self, merger, element_map):
        """Caso 3: Usuario dijo broken, sandbox no detectó."""
        user_feedback = [UserFeedback(
            vid=1,
            status=FeedbackStatus.BROKEN,
            message="No abre el modal"
        )]

        result = merger.merge(
            sandbox_errors=[],
            user_feedback=user_feedback,
            element_map=element_map,
        )

        assert len(result) == 1
        assert result[0].vid == 1
        assert result[0].user_status == FeedbackStatus.BROKEN
        assert result[0].user_feedback == "No abre el modal"
        assert result[0].has_technical_cause == False
        assert result[0].confidence == 0.8  # Menor confianza sin causa técnica

    def test_user_working_ignores_sandbox(self, merger, element_map):
        """Caso 2: Usuario dijo working, sandbox detectó error (falso positivo)."""
        # Mock sandbox error
        class MockError:
            selector = "#submit-btn"
            error_type = type('obj', (object,), {'value': 'z_index'})()
            def __str__(self):
                return "Z-index conflict"

        user_feedback = [UserFeedback(vid=2, status=FeedbackStatus.WORKING)]

        result = merger.merge(
            sandbox_errors=[MockError()],
            user_feedback=user_feedback,
            element_map=element_map,
        )

        # No debe incluir el error porque el usuario dijo que funciona
        assert len(result) == 0

    def test_untested_with_sandbox_error(self, merger, element_map):
        """Elemento no testeado pero con error técnico."""
        class MockError:
            selector = ".btn-primary"
            error_type = type('obj', (object,), {'value': 'pointer_blocked'})()
            def __str__(self):
                return "Pointer events blocked"

        user_feedback = [UserFeedback(vid=2, status=FeedbackStatus.WORKING)]  # Otro elemento

        result = merger.merge(
            sandbox_errors=[MockError()],
            user_feedback=user_feedback,
            element_map=element_map,
        )

        # Debe incluir el error del sandbox para el elemento 1 (no testeado)
        assert len(result) == 1
        assert result[0].vid == 1
        assert result[0].user_status == FeedbackStatus.UNTESTED
        assert result[0].has_technical_cause == True
        assert result[0].confidence == 0.6  # Menor confianza sin validación humana

    def test_user_working_no_sandbox(self, merger, element_map):
        """Caso 4: Usuario dijo working, sandbox no detectó nada."""
        user_feedback = [UserFeedback(vid=1, status=FeedbackStatus.WORKING)]

        result = merger.merge(
            sandbox_errors=[],
            user_feedback=user_feedback,
            element_map=element_map,
        )

        # No debe incluir nada - todo funciona
        assert len(result) == 0

    def test_generates_selector_by_id(self, merger, element_map):
        """Debe generar selector por ID si está disponible."""
        user_feedback = [UserFeedback(vid=2, status=FeedbackStatus.BROKEN)]

        result = merger.merge(
            sandbox_errors=[],
            user_feedback=user_feedback,
            element_map=element_map,
        )

        assert result[0].element_selector == "#submit-btn"

    def test_generates_selector_by_class(self, merger, element_map):
        """Debe generar selector por clase si no hay ID."""
        user_feedback = [UserFeedback(vid=1, status=FeedbackStatus.BROKEN)]

        result = merger.merge(
            sandbox_errors=[],
            user_feedback=user_feedback,
            element_map=element_map,
        )

        assert result[0].element_selector == "button.btn-primary"


class TestIntegration:
    """Tests de integración del flujo completo."""

    def test_full_feedback_flow(self):
        """Test del flujo completo: prepare -> feedback -> annotate -> merge."""
        # 1. HTML original
        html = """
        <!DOCTYPE html>
        <html>
        <body>
            <button class="btn-open">Open Modal</button>
            <button class="btn-close">Close</button>
            <input type="text" placeholder="Email" />
        </body>
        </html>
        """

        # 2. Preparar para validación
        mapper = ElementMapper()
        prepared = mapper.prepare(html)

        assert prepared.total_elements == 3
        assert 'data-vid="1"' in prepared.html
        assert 'data-vid="2"' in prepared.html
        assert 'data-vid="3"' in prepared.html

        # 3. Simular feedback del usuario
        user_feedback = [
            UserFeedback(vid=1, status=FeedbackStatus.BROKEN, message="Debería abrir modal"),
            UserFeedback(vid=2, status=FeedbackStatus.WORKING),
            UserFeedback(vid=3, status=FeedbackStatus.UNTESTED),
        ]

        # 4. Inyectar anotaciones
        injector = AnnotationInjector()
        annotated = injector.inject(
            html=prepared.html,
            element_feedback=user_feedback,
            global_feedback=["Falta botón de submit"],
        )

        assert annotated.broken_elements == [1]
        assert annotated.working_elements == [2]
        assert 'status:broken' in annotated.html
        assert '[GLOBAL FEEDBACK]' in annotated.html

        # 5. Merge errores
        element_map_dict = {
            k: {
                'vid': v.vid,
                'tag': v.tag,
                'classes': v.classes,
                'element_id': v.element_id,
            }
            for k, v in prepared.element_map.items()
        }

        merger = FeedbackMerger()
        merged = merger.merge(
            sandbox_errors=[],
            user_feedback=user_feedback,
            element_map=element_map_dict,
        )

        assert len(merged) == 1  # Solo el elemento broken
        assert merged[0].vid == 1
        assert merged[0].user_feedback == "Debería abrir modal"

        # 6. Limpiar HTML
        clean = injector.remove_annotations(annotated.html)

        assert 'data-vid' not in clean
        assert '[ELEMENT' not in clean
        assert 'data-validation-script' not in clean
