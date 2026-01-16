"""
AnnotationInjector - Inyecta comentarios de feedback en el HTML.

Los comentarios se usan para que el LLM entienda qué elementos
funcionan, cuáles no, y qué espera el usuario de cada uno.
"""

from bs4 import BeautifulSoup, Comment
from typing import List, Optional

from ..contracts.feedback import (
    UserFeedback,
    FeedbackStatus,
    AnnotatedHTML,
)


class AnnotationInjector:
    """Inyecta comentarios con feedback del usuario en el HTML."""

    def inject(
        self,
        html: str,
        element_feedback: List[UserFeedback],
        global_feedback: Optional[List[str]] = None,
    ) -> AnnotatedHTML:
        """
        Inyecta comentarios antes de cada elemento con feedback.

        Ejemplo de output:
        <!-- [ELEMENT #2] status:broken user_feedback:"debería abrir modal de pago" -->
        <button data-vid="2" class="btn-pay">Pagar</button>

        Args:
            html: HTML con data-vid inyectados
            element_feedback: Lista de feedback por elemento
            global_feedback: Lista de feedback global (opcional)

        Returns:
            AnnotatedHTML con HTML anotado y estadísticas
        """
        soup = BeautifulSoup(html, 'html.parser')

        working_elements = []
        broken_elements = []
        annotations_count = 0

        # Procesar feedback de elementos
        for feedback in element_feedback:
            # Solo procesar elementos con feedback (no untested)
            if feedback.status == FeedbackStatus.UNTESTED:
                continue

            # Buscar elemento por data-vid
            element = soup.find(attrs={"data-vid": str(feedback.vid)})

            if not element:
                continue

            # Construir texto del comentario
            if feedback.status == FeedbackStatus.WORKING:
                comment_text = f"[ELEMENT #{feedback.vid}] status:working"
                working_elements.append(feedback.vid)
            else:
                # Escapar comillas en el mensaje
                safe_message = (feedback.message or "").replace('"', '\\"')
                comment_text = (
                    f'[ELEMENT #{feedback.vid}] status:broken '
                    f'user_feedback:"{safe_message}"'
                )
                broken_elements.append(feedback.vid)

            # Inyectar comentario ANTES del elemento
            comment = Comment(f" {comment_text} ")
            element.insert_before(comment)
            element.insert_before("\n")  # Newline para legibilidad

            annotations_count += 1

        # Inyectar feedback global al inicio del body
        global_count = 0
        if global_feedback:
            body = soup.find('body')
            if body:
                for gf in reversed(global_feedback):  # Reversed para mantener orden
                    safe_message = gf.replace('"', '\\"')
                    comment = Comment(f' [GLOBAL FEEDBACK] "{safe_message}" ')
                    # Insertar al inicio del body
                    if body.contents:
                        body.contents[0].insert_before(comment)
                        body.contents[0].insert_before("\n")
                    else:
                        body.append(comment)
                    global_count += 1

        return AnnotatedHTML(
            html=str(soup),
            annotations_count=annotations_count,
            working_elements=working_elements,
            broken_elements=broken_elements,
            global_feedback_count=global_count,
        )

    def remove_annotations(self, html: str) -> str:
        """
        Remueve los atributos data-vid y comentarios de feedback del HTML final.
        Llamar después de que el fixer haya terminado.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Remover data-vid
        for el in soup.find_all(attrs={"data-vid": True}):
            del el['data-vid']

        # Remover comentarios de feedback
        for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
            if '[ELEMENT #' in comment or '[GLOBAL FEEDBACK]' in comment:
                comment.extract()

        # Remover script y estilos de validación
        for script in soup.find_all('script', {'data-validation-script': True}):
            script.decompose()
        for style in soup.find_all('style', {'data-validation-styles': True}):
            style.decompose()

        return str(soup)
