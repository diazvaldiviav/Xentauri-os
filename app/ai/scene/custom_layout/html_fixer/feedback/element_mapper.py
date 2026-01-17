"""
ElementMapper - Inyecta data-vid en elementos interactivos del HTML + script de comunicación.

Este módulo prepara el HTML para validación humana:
1. Encuentra todos los elementos interactivos (buttons, inputs, links, etc.)
2. Asigna un ID único (data-vid) a cada uno
3. Inyecta un script que comunica clicks al frontend via postMessage
"""

from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass
from typing import Dict, List, Optional
import re


@dataclass
class ElementInfo:
    """Información de un elemento interactivo."""
    vid: int                      # Validation ID único
    tag: str                      # "button", "input", etc.
    classes: List[str]            # ["btn-primary", "z-10"]
    element_id: Optional[str]     # ID del elemento si tiene
    text: str                     # Texto contenido (truncado a 50 chars)
    outer_html: str               # HTML completo del elemento
    line_number: Optional[int]    # Línea en el HTML original
    attributes: Dict[str, str]    # Otros atributos relevantes


@dataclass
class PreparedHTML:
    """HTML preparado para validación."""
    html: str                     # HTML con data-vid inyectados + script
    element_map: Dict[int, ElementInfo]
    total_elements: int


class ElementMapper:
    """Mapea y etiqueta elementos interactivos."""

    # Selectores de elementos interactivos
    INTERACTIVE_SELECTORS = [
        'button',
        'input',
        'select',
        'textarea',
        'a[href]',
        '[onclick]',
        '[onchange]',
        '[onsubmit]',
        '[role="button"]',
        '[role="link"]',
        '[role="checkbox"]',
        '[role="radio"]',
        '[role="switch"]',
        '[role="tab"]',
        '[role="menuitem"]',
        '[tabindex]:not([tabindex="-1"])',
    ]

    # Script que se inyecta en el HTML para comunicación con React
    VALIDATION_SCRIPT = """
<script data-validation-script="true">
(function() {
    // Script inyectado por ElementMapper para capturar clicks
    // y comunicarlos al padre (React) via postMessage

    document.body.addEventListener('click', function(e) {
        // 1. Encontrar el elemento interactivo más cercano con data-vid
        var target = e.target.closest('[data-vid]');

        if (target) {
            // Frontend maneja preventDefault si es necesario

            // 2. Obtener información del elemento
            var rect = target.getBoundingClientRect();

            // 3. Enviar mensaje al padre (React)
            window.parent.postMessage({
                type: 'ELEMENT_CLICKED',
                vid: parseInt(target.getAttribute('data-vid')),
                rect: {
                    top: rect.top,
                    left: rect.left,
                    width: rect.width,
                    height: rect.height,
                    bottom: rect.bottom,
                    right: rect.right
                },
                tagName: target.tagName.toLowerCase(),
                text: target.textContent.substring(0, 50).trim()
            }, '*');
        }
    }, true);  // Use capture phase para interceptar antes que otros handlers

    // Escuchar mensajes del padre para actualizar estilos de feedback
    window.addEventListener('message', function(e) {
        if (e.data && e.data.type === 'UPDATE_FEEDBACK_STATUS') {
            var status = e.data.status;

            for (var vid in status) {
                var el = document.querySelector('[data-vid="' + vid + '"]');
                if (el) {
                    // Remover clases previas
                    el.classList.remove('feedback-working', 'feedback-broken', 'feedback-untested');

                    // Agregar nueva clase
                    el.classList.add('feedback-' + status[vid]);
                }
            }
        }
    });

    // Notificar al padre que el iframe está listo
    window.parent.postMessage({ type: 'IFRAME_READY' }, '*');
})();
</script>

<style data-validation-styles="true">
/* Estilos de feedback visual */
[data-vid] {
    transition: outline 0.2s ease, box-shadow 0.2s ease;
}

[data-vid]:hover {
    outline: 2px dashed #3b82f6 !important;
    outline-offset: 2px;
}

[data-vid].feedback-working {
    outline: 3px solid #22c55e !important;
    outline-offset: 2px;
    box-shadow: 0 0 10px rgba(34, 197, 94, 0.3);
}

[data-vid].feedback-broken {
    outline: 3px solid #ef4444 !important;
    outline-offset: 2px;
    box-shadow: 0 0 10px rgba(239, 68, 68, 0.3);
}

[data-vid].feedback-untested {
    outline: 2px dashed #f59e0b !important;
    outline-offset: 2px;
}
</style>
"""

    def prepare(self, html: str) -> PreparedHTML:
        """
        Prepara HTML para validación:
        1. Encuentra elementos interactivos
        2. Inyecta data-vid único en cada uno
        3. Inyecta script de comunicación
        4. Crea mapa de elementos
        """
        soup = BeautifulSoup(html, 'html.parser')
        element_map: Dict[int, ElementInfo] = {}
        vid = 1

        # Encontrar todos los elementos interactivos
        for selector in self.INTERACTIVE_SELECTORS:
            try:
                elements = soup.select(selector)
            except Exception:
                continue

            for el in elements:
                # Evitar duplicados (un elemento puede matchear varios selectores)
                if el.get('data-vid'):
                    continue

                # Inyectar ID de validación
                el['data-vid'] = str(vid)

                # Crear info del elemento
                element_map[vid] = ElementInfo(
                    vid=vid,
                    tag=el.name,
                    classes=el.get('class', []) if isinstance(el.get('class'), list) else [],
                    element_id=el.get('id'),
                    text=self._get_text_content(el)[:50],
                    outer_html=str(el)[:500],  # Limitar tamaño
                    line_number=getattr(el, 'sourceline', None),
                    attributes=self._get_relevant_attrs(el)
                )

                vid += 1

        # Inyectar script de comunicación al final del body
        body = soup.find('body')
        if body:
            script_soup = BeautifulSoup(self.VALIDATION_SCRIPT, 'html.parser')
            body.append(script_soup)

        return PreparedHTML(
            html=str(soup),
            element_map=element_map,
            total_elements=len(element_map)
        )

    def _get_text_content(self, el: Tag) -> str:
        """Obtiene texto contenido, limpio."""
        text = el.get_text(strip=True)
        # Limpiar espacios múltiples
        text = re.sub(r'\s+', ' ', text)
        return text

    def _get_relevant_attrs(self, el: Tag) -> Dict[str, str]:
        """Extrae atributos relevantes para debugging."""
        relevant = ['onclick', 'onchange', 'onsubmit', 'href', 'type', 'name', 'value', 'role']
        return {k: str(el.get(k)) for k in relevant if el.get(k)}
