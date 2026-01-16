# SCRUM FRONTEND: Human Feedback System
## Sprint 4 - React/TypeScript Implementation

---

## Sprint Goal

> **Implementar la interfaz de validación humana en React/TypeScript, permitiendo a los usuarios probar elementos interactivos, dar feedback ✅/❌, y aprobar layouts antes de mostrarlos.**

---

## Problema a Resolver

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    NECESIDAD DE VALIDACIÓN HUMANA                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   El sandbox automático detecta errores técnicos (z-index, pointer-events)  │
│   pero NO puede detectar errores funcionales:                               │
│                                                                             │
│   • "Este botón debería abrir un modal de confirmación"                    │
│   • "Falta un botón de volver"                                             │
│   • "El formulario no valida correctamente"                                │
│   • "El flujo no tiene sentido para el usuario"                            │
│                                                                             │
│   SOLUCIÓN: Interfaz que permite al usuario:                               │
│   1. Ver preview del HTML en un iframe                                     │
│   2. Hacer click en elementos interactivos                                 │
│   3. Marcar cada uno como ✅ Working o ❌ Broken                            │
│   4. Agregar feedback descriptivo                                          │
│   5. Reportar elementos faltantes (Global Feedback)                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Arquitectura del Frontend

```
frontend/
├── src/
│   ├── components/
│   │   └── layout-validator/           # Módulo principal
│   │       ├── index.tsx               # Export barrel
│   │       ├── LayoutValidator.tsx     # F07: Componente principal
│   │       ├── PreviewFrame.tsx        # F03: Iframe con postMessage
│   │       ├── FeedbackPopup.tsx       # F04: Modal ✅/❌
│   │       ├── ControlPanel.tsx        # F05: Barra de progreso y botones
│   │       ├── WarningModal.tsx        # F09: Warning feedback incompleto
│   │       └── GlobalFeedbackModal.tsx # F10: Modal para elementos faltantes
│   │
│   ├── hooks/
│   │   └── useLayoutValidation.ts      # F06: Hook con toda la lógica
│   │
│   ├── types/
│   │   └── validation.ts               # F02: TypeScript types
│   │
│   ├── services/
│   │   └── validationApi.ts            # F08: Llamadas al backend
│   │
│   └── App.tsx                         # Integración
│
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── vite.config.ts
```

---

## Flujo de Interacción

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FLUJO DE VALIDACIÓN HUMANA                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. LOAD                                                                    │
│     ┌────────────────────────────────────────┐                             │
│     │ LayoutValidator recibe HTML            │                             │
│     │ → Llama POST /feedback/prepare         │                             │
│     │ → Recibe HTML + element_map            │                             │
│     └────────────────────┬───────────────────┘                             │
│                          │                                                  │
│  2. PREVIEW              ▼                                                  │
│     ┌────────────────────────────────────────┐                             │
│     │ PreviewFrame muestra HTML en iframe    │                             │
│     │ → Script inyectado captura clicks      │                             │
│     │ → postMessage comunica a React         │                             │
│     └────────────────────┬───────────────────┘                             │
│                          │                                                  │
│  3. CLICK               ▼                                                  │
│     ┌────────────────────────────────────────┐                             │
│     │ Usuario hace click en elemento         │                             │
│     │ → Iframe envía ELEMENT_CLICKED         │                             │
│     │ → React abre FeedbackPopup             │                             │
│     └────────────────────┬───────────────────┘                             │
│                          │                                                  │
│  4. FEEDBACK            ▼                                                  │
│     ┌────────────────────────────────────────┐                             │
│     │ FeedbackPopup muestra opciones         │                             │
│     │ → ✅ Working: Cierra popup             │                             │
│     │ → ❌ Broken: Pide descripción          │                             │
│     └────────────────────┬───────────────────┘                             │
│                          │                                                  │
│  5. PROGRESS            ▼                                                  │
│     ┌────────────────────────────────────────┐                             │
│     │ ControlPanel actualiza progreso        │                             │
│     │ → "5/12 elementos probados"            │                             │
│     │ → Barra de progreso visual             │                             │
│     └────────────────────┬───────────────────┘                             │
│                          │                                                  │
│  6. SUBMIT              ▼                                                  │
│     ┌────────────────────────────────────────┐                             │
│     │ Usuario hace click en "Submit"         │                             │
│     │ → Si <80% probado: WarningModal        │                             │
│     │ → Si OK: POST /feedback/fix            │                             │
│     │ → Recibe HTML arreglado                │                             │
│     └────────────────────┬───────────────────┘                             │
│                          │                                                  │
│  7. APPROVE             ▼                                                  │
│     ┌────────────────────────────────────────┐                             │
│     │ Usuario revisa cambios                 │                             │
│     │ → "Approve": POST /feedback/approve    │                             │
│     │ → "Re-test": Volver al paso 2          │                             │
│     └────────────────────────────────────────┘                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sprint Backlog

| ID | Tarea | Archivo | Est. | Prior. | Deps | Estado |
|----|-------|---------|------|--------|------|--------|
| F01 | Setup proyecto React + TypeScript + Tailwind | `frontend/` | 2h | 🔴 | - | ⬜ |
| F02 | Types TypeScript | `types/validation.ts` | 1h | 🔴 | - | ⬜ |
| F03 | PreviewFrame + postMessage | `components/PreviewFrame.tsx` | 5h | 🔴 | F02 | ⬜ |
| F04 | FeedbackPopup ✅/❌ | `components/FeedbackPopup.tsx` | 3h | 🔴 | F02 | ⬜ |
| F05 | ControlPanel + progress | `components/ControlPanel.tsx` | 3h | 🔴 | F02 | ⬜ |
| F06 | useLayoutValidation hook | `hooks/useLayoutValidation.ts` | 4h | 🔴 | F02,F08 | ⬜ |
| F07 | LayoutValidator main | `components/LayoutValidator.tsx` | 3h | 🔴 | F03-F06 | ⬜ |
| F08 | validationApi | `services/validationApi.ts` | 1h | 🔴 | F02 | ⬜ |
| F09 | WarningModal | `components/WarningModal.tsx` | 1h | 🟡 | F02 | ⬜ |
| F10 | GlobalFeedbackModal | `components/GlobalFeedbackModal.tsx` | 2h | 🟡 | F02 | ⬜ |
| F11 | Estilos y animaciones | CSS/Tailwind | 2h | 🟢 | ALL | ⬜ |
| F12 | Tests de componentes | `__tests__/` | 3h | 🟡 | ALL | ⬜ |

**Total Estimado: ~30 horas**

---

## Diagrama de Dependencias

```
F01 (Setup) ────────────────────────────────────────────────────┐
                                                                │
F02 (Types) ──┬──► F03 (PreviewFrame) ──┐                      │
              │                          │                      │
              ├──► F04 (FeedbackPopup) ──┤                      │
              │                          │                      │
              ├──► F05 (ControlPanel) ───┼──► F07 (LayoutValidator)
              │                          │            │
              ├──► F08 (validationApi) ──┤            │
              │         │                │            │
              │         └──► F06 (Hook) ─┘            │
              │                                       │
              ├──► F09 (WarningModal) ────────────────┤
              │                                       │
              └──► F10 (GlobalFeedbackModal) ─────────┘
                                                      │
                                                      ▼
                                              F11 (Estilos)
                                                      │
                                                      ▼
                                              F12 (Tests)
```

---

## ESPECIFICACIONES TÉCNICAS

---

### F01: Setup Proyecto

**Comandos:**

```bash
# Crear proyecto con Vite
npm create vite@latest frontend -- --template react-ts

cd frontend

# Instalar dependencias
npm install
npm install -D tailwindcss postcss autoprefixer
npm install @tanstack/react-query  # Para API calls
npm install clsx  # Utilidad para clases condicionales

# Configurar Tailwind
npx tailwindcss init -p
```

**tailwind.config.js:**

```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'feedback-working': '#22c55e',
        'feedback-broken': '#ef4444',
        'feedback-untested': '#f59e0b',
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-in': 'bounceIn 0.3s ease-out',
      },
      keyframes: {
        bounceIn: {
          '0%': { transform: 'scale(0.9)', opacity: '0' },
          '50%': { transform: 'scale(1.02)' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
```

**vite.config.ts:**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

---

### F02: TypeScript Types

**Archivo:** `src/types/validation.ts`

```typescript
/**
 * Types para el sistema de validación de layouts.
 */

// ============== ELEMENT INFO ==============

export interface ElementInfo {
  vid: number;                    // Validation ID
  tag: string;                    // "button", "input", etc.
  classes: string[];              // ["btn-primary", "z-10"]
  element_id?: string;            // ID del elemento si tiene
  text: string;                   // Texto contenido (truncado)
  outer_html: string;             // HTML completo del elemento
  line_number?: number;           // Línea en el HTML original
  attributes: Record<string, string>;  // onclick, href, etc.
}

export type ElementMap = Record<number, ElementInfo>;

// ============== FEEDBACK ==============

export type FeedbackStatus = 'working' | 'broken' | 'untested';

export interface FeedbackItem {
  vid: number;
  status: FeedbackStatus;
  message?: string;               // Solo si status === 'broken'
  testedAt?: Date;
}

export type FeedbackState = Record<number, FeedbackItem>;

// ============== API TYPES ==============

export interface PrepareValidationRequest {
  html: string;
}

export interface PrepareValidationResponse {
  html: string;                   // HTML con data-vid inyectados
  element_map: ElementMap;
  total_elements: number;
}

export interface FixWithFeedbackRequest {
  html: string;
  feedback: Array<{
    vid: number;
    status: 'working' | 'broken';
    message?: string;
  }>;
  global_feedback: string[];
}

export interface ChangeMade {
  vid?: number;
  description: string;
  fix_type: string;
}

export interface FixWithFeedbackResponse {
  success: boolean;
  fixed_html: string;
  changes_made: ChangeMade[];
  errors_found: number;
  errors_fixed: number;
  sandbox_errors: number;
  user_reported_errors: number;
  global_feedback_applied: number;
}

export interface ApproveLayoutRequest {
  html: string;
  device_id?: string;
}

export interface ApproveLayoutResponse {
  success: boolean;
  message: string;
  display_url?: string;
}

// ============== UI STATE ==============

export interface PopupState {
  isOpen: boolean;
  element: ElementInfo | null;
  position: { x: number; y: number };
}

export interface ValidationStats {
  total: number;
  tested: number;
  working: number;
  broken: number;
  progress: number;  // 0-100
}

// ============== IFRAME MESSAGES ==============

export interface IframeMessage {
  type: 'ELEMENT_CLICKED' | 'IFRAME_READY' | 'UPDATE_FEEDBACK_STATUS';
}

export interface ElementClickedMessage extends IframeMessage {
  type: 'ELEMENT_CLICKED';
  vid: number;
  rect: {
    top: number;
    left: number;
    width: number;
    height: number;
    bottom: number;
    right: number;
  };
  tagName: string;
  text: string;
}

export interface IframeReadyMessage extends IframeMessage {
  type: 'IFRAME_READY';
}

export interface UpdateFeedbackStatusMessage extends IframeMessage {
  type: 'UPDATE_FEEDBACK_STATUS';
  status: Record<number, FeedbackStatus>;
}

// ============== COMPONENT PROPS ==============

export interface LayoutValidatorProps {
  initialHtml: string;
  onApprove?: (html: string) => void;
  onCancel?: () => void;
  deviceId?: string;
}

export interface PreviewFrameProps {
  html: string;
  elementMap: ElementMap;
  feedbackStatus: Record<number, FeedbackStatus>;
  onElementClick: (element: ElementInfo, position: { x: number; y: number }) => void;
  onIframeReady?: () => void;
}

export interface FeedbackPopupProps {
  isOpen: boolean;
  element: ElementInfo | null;
  position: { x: number; y: number };
  onWorking: () => void;
  onBroken: (message: string) => void;
  onClose: () => void;
}

export interface ControlPanelProps {
  stats: ValidationStats;
  globalFeedback: string[];
  isSubmitting: boolean;
  onReset: () => void;
  onOpenGlobalFeedback: () => void;
  onSubmit: () => void;
}

export interface WarningModalProps {
  isOpen: boolean;
  stats: ValidationStats;
  onContinue: () => void;
  onCancel: () => void;
}

export interface GlobalFeedbackModalProps {
  isOpen: boolean;
  existingFeedback: string[];
  onSubmit: (feedback: string) => void;
  onClose: () => void;
}
```

---

### F03: PreviewFrame

**Archivo:** `src/components/layout-validator/PreviewFrame.tsx`

```tsx
/**
 * PreviewFrame - Muestra HTML en iframe y captura clicks via postMessage.
 *
 * IMPORTANTE: La comunicación con el iframe se hace via postMessage porque
 * no podemos capturar eventos directamente desde fuera del iframe.
 * El script de validación se inyecta en el HTML por el backend (ElementMapper).
 */

import React, { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import type {
  ElementInfo,
  ElementMap,
  FeedbackStatus,
  ElementClickedMessage,
  IframeReadyMessage,
} from '../../types/validation';

interface PreviewFrameProps {
  html: string;
  elementMap: ElementMap;
  feedbackStatus: Record<number, FeedbackStatus>;
  onElementClick: (element: ElementInfo, position: { x: number; y: number }) => void;
  onIframeReady?: () => void;
}

export const PreviewFrame = forwardRef<HTMLIFrameElement, PreviewFrameProps>(
  ({ html, elementMap, feedbackStatus, onElementClick, onIframeReady }, ref) => {
    const iframeRef = useRef<HTMLIFrameElement>(null);

    useImperativeHandle(ref, () => iframeRef.current!);

    // Escuchar mensajes del iframe via postMessage
    useEffect(() => {
      const handleMessage = (event: MessageEvent) => {
        // Verificar que el mensaje viene de NUESTRO iframe
        if (event.source !== iframeRef.current?.contentWindow) {
          return;
        }

        const data = event.data as ElementClickedMessage | IframeReadyMessage;

        if (data.type === 'ELEMENT_CLICKED') {
          const clickData = data as ElementClickedMessage;
          const elementInfo = elementMap[clickData.vid];

          if (elementInfo) {
            // Calcular posición ABSOLUTA del popup
            // rect viene relativo al iframe, sumamos offset del iframe
            const iframeRect = iframeRef.current?.getBoundingClientRect();

            if (iframeRect) {
              onElementClick(elementInfo, {
                x: iframeRect.left + clickData.rect.left + clickData.rect.width / 2,
                y: iframeRect.top + clickData.rect.bottom + 10,
              });
            }
          }
        }

        if (data.type === 'IFRAME_READY') {
          onIframeReady?.();
        }
      };

      window.addEventListener('message', handleMessage);
      return () => window.removeEventListener('message', handleMessage);
    }, [elementMap, onElementClick, onIframeReady]);

    // Escribir HTML en iframe
    useEffect(() => {
      const iframe = iframeRef.current;
      if (!iframe) return;

      const doc = iframe.contentDocument;
      if (!doc) return;

      doc.open();
      doc.write(html);
      doc.close();
    }, [html]);

    // Actualizar estilos de feedback via postMessage
    useEffect(() => {
      const iframe = iframeRef.current;
      if (!iframe?.contentWindow) return;

      // Pequeño delay para asegurar que el iframe está listo
      const timeout = setTimeout(() => {
        iframe.contentWindow?.postMessage(
          {
            type: 'UPDATE_FEEDBACK_STATUS',
            status: feedbackStatus,
          },
          '*'
        );
      }, 100);

      return () => clearTimeout(timeout);
    }, [feedbackStatus]);

    return (
      <div className="relative w-full h-full bg-gray-100 rounded-lg overflow-hidden">
        {/* Loading overlay */}
        <div
          className="absolute inset-0 bg-white/80 flex items-center justify-center z-10 transition-opacity duration-300 pointer-events-none"
          style={{ opacity: html ? 0 : 1 }}
        >
          <div className="flex items-center gap-3 text-gray-500">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
              />
            </svg>
            <span>Loading preview...</span>
          </div>
        </div>

        {/* Iframe */}
        <iframe
          ref={iframeRef}
          className="w-full h-full border-0"
          title="Layout Preview"
          sandbox="allow-scripts allow-same-origin"
        />

        {/* Instructions overlay */}
        <div className="absolute bottom-4 left-4 right-4 bg-black/70 text-white text-sm px-4 py-2 rounded-lg pointer-events-none">
          <p className="flex items-center gap-2">
            <span className="inline-block w-3 h-3 bg-blue-500 rounded-full animate-pulse" />
            Click on interactive elements to test them
          </p>
        </div>
      </div>
    );
  }
);

PreviewFrame.displayName = 'PreviewFrame';
```

---

### F04: FeedbackPopup

**Archivo:** `src/components/layout-validator/FeedbackPopup.tsx`

```tsx
/**
 * FeedbackPopup - Modal para dar feedback sobre un elemento.
 *
 * Aparece cuando el usuario hace click en un elemento interactivo.
 * Permite marcar como ✅ Working o ❌ Broken (con descripción).
 */

import React, { useState, useEffect, useRef } from 'react';
import clsx from 'clsx';
import type { FeedbackPopupProps } from '../../types/validation';

export function FeedbackPopup({
  isOpen,
  element,
  position,
  onWorking,
  onBroken,
  onClose,
}: FeedbackPopupProps) {
  const [showBrokenForm, setShowBrokenForm] = useState(false);
  const [brokenMessage, setBrokenMessage] = useState('');
  const popupRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Reset state when element changes
  useEffect(() => {
    setShowBrokenForm(false);
    setBrokenMessage('');
  }, [element?.vid]);

  // Focus input when showing broken form
  useEffect(() => {
    if (showBrokenForm && inputRef.current) {
      inputRef.current.focus();
    }
  }, [showBrokenForm]);

  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
      return () => window.removeEventListener('keydown', handleKeyDown);
    }
  }, [isOpen, onClose]);

  // Adjust position to stay in viewport
  const adjustedPosition = React.useMemo(() => {
    if (!popupRef.current) return position;

    const popupWidth = 320;
    const popupHeight = showBrokenForm ? 250 : 180;
    const padding = 16;

    let x = position.x - popupWidth / 2;
    let y = position.y;

    // Keep within viewport
    if (x < padding) x = padding;
    if (x + popupWidth > window.innerWidth - padding) {
      x = window.innerWidth - popupWidth - padding;
    }
    if (y + popupHeight > window.innerHeight - padding) {
      y = position.y - popupHeight - 20; // Show above instead
    }

    return { x, y };
  }, [position, showBrokenForm]);

  const handleBrokenSubmit = () => {
    if (brokenMessage.trim()) {
      onBroken(brokenMessage.trim());
      setBrokenMessage('');
      setShowBrokenForm(false);
    }
  };

  if (!isOpen || !element) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-[9998]"
        onClick={onClose}
      />

      {/* Popup */}
      <div
        ref={popupRef}
        className={clsx(
          'fixed z-[9999] bg-white rounded-xl shadow-2xl border border-gray-200',
          'w-80 animate-bounce-in'
        )}
        style={{
          left: adjustedPosition.x,
          top: adjustedPosition.y,
        }}
      >
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-xs font-mono bg-gray-100 px-2 py-0.5 rounded">
                #{element.vid}
              </span>
              <span className="text-sm font-medium text-gray-700">
                {`<${element.tag}>`}
              </span>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          {element.text && (
            <p className="text-xs text-gray-500 mt-1 truncate">
              "{element.text}"
            </p>
          )}
        </div>

        {/* Content */}
        <div className="p-4">
          {!showBrokenForm ? (
            <>
              <p className="text-sm text-gray-600 mb-4">
                Does this element work as expected?
              </p>

              <div className="flex gap-3">
                <button
                  onClick={onWorking}
                  className={clsx(
                    'flex-1 py-3 px-4 rounded-lg font-medium text-sm',
                    'bg-green-50 text-green-700 border-2 border-green-200',
                    'hover:bg-green-100 hover:border-green-300',
                    'active:scale-95 transition-all duration-150',
                    'flex items-center justify-center gap-2'
                  )}
                >
                  <span className="text-lg">✓</span>
                  Working
                </button>

                <button
                  onClick={() => setShowBrokenForm(true)}
                  className={clsx(
                    'flex-1 py-3 px-4 rounded-lg font-medium text-sm',
                    'bg-red-50 text-red-700 border-2 border-red-200',
                    'hover:bg-red-100 hover:border-red-300',
                    'active:scale-95 transition-all duration-150',
                    'flex items-center justify-center gap-2'
                  )}
                >
                  <span className="text-lg">✕</span>
                  Broken
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-600 mb-3">
                What should this element do?
              </p>

              <textarea
                ref={inputRef}
                value={brokenMessage}
                onChange={(e) => setBrokenMessage(e.target.value)}
                placeholder="e.g., Should open a confirmation modal..."
                className={clsx(
                  'w-full h-20 p-3 text-sm rounded-lg',
                  'border-2 border-gray-200 focus:border-blue-400',
                  'focus:ring-2 focus:ring-blue-100 focus:outline-none',
                  'resize-none'
                )}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleBrokenSubmit();
                  }
                }}
              />

              <div className="flex gap-2 mt-3">
                <button
                  onClick={() => setShowBrokenForm(false)}
                  className="flex-1 py-2 px-3 rounded-lg text-sm text-gray-600 hover:bg-gray-100"
                >
                  Back
                </button>
                <button
                  onClick={handleBrokenSubmit}
                  disabled={!brokenMessage.trim()}
                  className={clsx(
                    'flex-1 py-2 px-3 rounded-lg text-sm font-medium',
                    'bg-red-500 text-white',
                    'hover:bg-red-600 disabled:bg-gray-300',
                    'disabled:cursor-not-allowed'
                  )}
                >
                  Submit
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </>
  );
}
```

---

### F05: ControlPanel

**Archivo:** `src/components/layout-validator/ControlPanel.tsx`

```tsx
/**
 * ControlPanel - Barra de progreso y controles.
 *
 * Muestra:
 * - Progreso de testing (X/Y elementos)
 * - Barra visual de progreso
 * - Botón de Reset
 * - Botón de Global Feedback
 * - Botón de Submit
 */

import React from 'react';
import clsx from 'clsx';
import type { ControlPanelProps } from '../../types/validation';

export function ControlPanel({
  stats,
  globalFeedback,
  isSubmitting,
  onReset,
  onOpenGlobalFeedback,
  onSubmit,
}: ControlPanelProps) {
  const hasAnyFeedback = stats.tested > 0 || globalFeedback.length > 0;
  const progressColor =
    stats.progress >= 80
      ? 'bg-green-500'
      : stats.progress >= 50
      ? 'bg-yellow-500'
      : 'bg-red-500';

  return (
    <div className="bg-white border-t border-gray-200 px-6 py-4">
      {/* Stats row */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-6">
          {/* Progress */}
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500">Progress:</span>
            <span className="text-lg font-bold text-gray-900">
              {stats.tested}/{stats.total}
            </span>
            <span className="text-sm text-gray-400">tested</span>
          </div>

          {/* Working/Broken counts */}
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-green-500" />
              <span className="text-green-700 font-medium">{stats.working}</span>
              <span className="text-gray-400">working</span>
            </span>
            <span className="flex items-center gap-1">
              <span className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-red-700 font-medium">{stats.broken}</span>
              <span className="text-gray-400">broken</span>
            </span>
          </div>
        </div>

        {/* Percentage */}
        <div className="text-right">
          <span
            className={clsx(
              'text-2xl font-bold',
              stats.progress >= 80 ? 'text-green-600' : 'text-gray-600'
            )}
          >
            {stats.progress}%
          </span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden mb-4">
        <div
          className={clsx('h-full transition-all duration-300', progressColor)}
          style={{ width: `${stats.progress}%` }}
        />
      </div>

      {/* Buttons row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Reset button */}
          <button
            onClick={onReset}
            disabled={!hasAnyFeedback || isSubmitting}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium',
              'bg-gray-100 text-gray-700',
              'hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed',
              'flex items-center gap-2'
            )}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
              />
            </svg>
            Reset
          </button>

          {/* Global Feedback button */}
          <button
            onClick={onOpenGlobalFeedback}
            disabled={isSubmitting}
            className={clsx(
              'px-4 py-2 rounded-lg text-sm font-medium',
              'bg-yellow-100 text-yellow-800',
              'hover:bg-yellow-200 disabled:opacity-50',
              'flex items-center gap-2'
            )}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
              />
            </svg>
            Global Feedback
            {globalFeedback.length > 0 && (
              <span className="bg-yellow-500 text-white text-xs px-2 py-0.5 rounded-full">
                {globalFeedback.length}
              </span>
            )}
          </button>
        </div>

        {/* Submit button */}
        <button
          onClick={onSubmit}
          disabled={isSubmitting || (!hasAnyFeedback && globalFeedback.length === 0)}
          className={clsx(
            'px-6 py-2 rounded-lg text-sm font-medium',
            'bg-blue-500 text-white',
            'hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed',
            'flex items-center gap-2',
            'transition-colors duration-150'
          )}
        >
          {isSubmitting ? (
            <>
              <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Processing...
            </>
          ) : (
            <>
              Submit Feedback
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 7l5 5m0 0l-5 5m5-5H6"
                />
              </svg>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
```

---

### F06: useLayoutValidation Hook

**Archivo:** `src/hooks/useLayoutValidation.ts`

```typescript
/**
 * useLayoutValidation - Hook que maneja toda la lógica de validación.
 *
 * Responsabilidades:
 * - Preparar HTML (llamar API)
 * - Manejar estado de feedback
 * - Calcular estadísticas
 * - Enviar feedback al backend
 */

import { useState, useCallback, useMemo, useEffect } from 'react';
import type {
  ElementInfo,
  ElementMap,
  FeedbackItem,
  FeedbackState,
  FeedbackStatus,
  ValidationStats,
  PopupState,
  PrepareValidationResponse,
  FixWithFeedbackResponse,
} from '../types/validation';
import { prepareValidation, fixWithFeedback, approveLayout } from '../services/validationApi';

interface UseLayoutValidationOptions {
  initialHtml: string;
  onSuccess?: (html: string) => void;
  onError?: (error: Error) => void;
}

interface UseLayoutValidationReturn {
  // State
  isLoading: boolean;
  isSubmitting: boolean;
  error: Error | null;
  preparedHtml: string;
  elementMap: ElementMap;
  feedback: FeedbackState;
  globalFeedback: string[];
  stats: ValidationStats;
  popup: PopupState;
  fixResult: FixWithFeedbackResponse | null;

  // Actions
  handleElementClick: (element: ElementInfo, position: { x: number; y: number }) => void;
  handleWorking: () => void;
  handleBroken: (message: string) => void;
  closePopup: () => void;
  addGlobalFeedback: (message: string) => void;
  removeGlobalFeedback: (index: number) => void;
  reset: () => void;
  submit: () => Promise<void>;
  approve: () => Promise<void>;

  // Computed
  feedbackStatusMap: Record<number, FeedbackStatus>;
}

export function useLayoutValidation({
  initialHtml,
  onSuccess,
  onError,
}: UseLayoutValidationOptions): UseLayoutValidationReturn {
  // Loading states
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  // Prepared data
  const [preparedHtml, setPreparedHtml] = useState('');
  const [elementMap, setElementMap] = useState<ElementMap>({});

  // Feedback state
  const [feedback, setFeedback] = useState<FeedbackState>({});
  const [globalFeedback, setGlobalFeedback] = useState<string[]>([]);

  // Popup state
  const [popup, setPopup] = useState<PopupState>({
    isOpen: false,
    element: null,
    position: { x: 0, y: 0 },
  });

  // Fix result
  const [fixResult, setFixResult] = useState<FixWithFeedbackResponse | null>(null);

  // Initialize: prepare HTML
  useEffect(() => {
    let cancelled = false;

    async function prepare() {
      try {
        setIsLoading(true);
        setError(null);

        const response = await prepareValidation(initialHtml);

        if (!cancelled) {
          setPreparedHtml(response.html);
          setElementMap(response.element_map);

          // Initialize feedback state
          const initialFeedback: FeedbackState = {};
          for (const vid of Object.keys(response.element_map)) {
            initialFeedback[Number(vid)] = {
              vid: Number(vid),
              status: 'untested',
            };
          }
          setFeedback(initialFeedback);
        }
      } catch (err) {
        if (!cancelled) {
          const error = err instanceof Error ? err : new Error(String(err));
          setError(error);
          onError?.(error);
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    prepare();

    return () => {
      cancelled = true;
    };
  }, [initialHtml, onError]);

  // Calculate stats
  const stats = useMemo<ValidationStats>(() => {
    const total = Object.keys(elementMap).length;
    const feedbackItems = Object.values(feedback);
    const tested = feedbackItems.filter((f) => f.status !== 'untested').length;
    const working = feedbackItems.filter((f) => f.status === 'working').length;
    const broken = feedbackItems.filter((f) => f.status === 'broken').length;

    return {
      total,
      tested,
      working,
      broken,
      progress: total > 0 ? Math.round((tested / total) * 100) : 0,
    };
  }, [elementMap, feedback]);

  // Feedback status map for iframe
  const feedbackStatusMap = useMemo<Record<number, FeedbackStatus>>(() => {
    const map: Record<number, FeedbackStatus> = {};
    for (const [vid, item] of Object.entries(feedback)) {
      map[Number(vid)] = item.status;
    }
    return map;
  }, [feedback]);

  // Handlers
  const handleElementClick = useCallback(
    (element: ElementInfo, position: { x: number; y: number }) => {
      setPopup({
        isOpen: true,
        element,
        position,
      });
    },
    []
  );

  const handleWorking = useCallback(() => {
    if (!popup.element) return;

    setFeedback((prev) => ({
      ...prev,
      [popup.element!.vid]: {
        vid: popup.element!.vid,
        status: 'working',
        testedAt: new Date(),
      },
    }));

    setPopup({ isOpen: false, element: null, position: { x: 0, y: 0 } });
  }, [popup.element]);

  const handleBroken = useCallback(
    (message: string) => {
      if (!popup.element) return;

      setFeedback((prev) => ({
        ...prev,
        [popup.element!.vid]: {
          vid: popup.element!.vid,
          status: 'broken',
          message,
          testedAt: new Date(),
        },
      }));

      setPopup({ isOpen: false, element: null, position: { x: 0, y: 0 } });
    },
    [popup.element]
  );

  const closePopup = useCallback(() => {
    setPopup({ isOpen: false, element: null, position: { x: 0, y: 0 } });
  }, []);

  const addGlobalFeedback = useCallback((message: string) => {
    setGlobalFeedback((prev) => [...prev, message]);
  }, []);

  const removeGlobalFeedback = useCallback((index: number) => {
    setGlobalFeedback((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const reset = useCallback(() => {
    const resetFeedback: FeedbackState = {};
    for (const vid of Object.keys(elementMap)) {
      resetFeedback[Number(vid)] = {
        vid: Number(vid),
        status: 'untested',
      };
    }
    setFeedback(resetFeedback);
    setGlobalFeedback([]);
    setFixResult(null);
  }, [elementMap]);

  const submit = useCallback(async () => {
    try {
      setIsSubmitting(true);
      setError(null);

      // Prepare feedback payload
      const feedbackPayload = Object.values(feedback)
        .filter((f) => f.status !== 'untested')
        .map((f) => ({
          vid: f.vid,
          status: f.status as 'working' | 'broken',
          message: f.message,
        }));

      const response = await fixWithFeedback({
        html: preparedHtml,
        feedback: feedbackPayload,
        global_feedback: globalFeedback,
      });

      setFixResult(response);

      if (response.success) {
        // Update prepared HTML with fixed version for potential re-testing
        const newPrepared = await prepareValidation(response.fixed_html);
        setPreparedHtml(newPrepared.html);
        setElementMap(newPrepared.element_map);

        // Reset feedback for re-testing
        const resetFeedback: FeedbackState = {};
        for (const vid of Object.keys(newPrepared.element_map)) {
          resetFeedback[Number(vid)] = {
            vid: Number(vid),
            status: 'untested',
          };
        }
        setFeedback(resetFeedback);
      }
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onError?.(error);
    } finally {
      setIsSubmitting(false);
    }
  }, [feedback, preparedHtml, globalFeedback, onError]);

  const approve = useCallback(async () => {
    if (!fixResult?.fixed_html) return;

    try {
      setIsSubmitting(true);

      await approveLayout({
        html: fixResult.fixed_html,
      });

      onSuccess?.(fixResult.fixed_html);
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      setError(error);
      onError?.(error);
    } finally {
      setIsSubmitting(false);
    }
  }, [fixResult, onSuccess, onError]);

  return {
    // State
    isLoading,
    isSubmitting,
    error,
    preparedHtml,
    elementMap,
    feedback,
    globalFeedback,
    stats,
    popup,
    fixResult,

    // Actions
    handleElementClick,
    handleWorking,
    handleBroken,
    closePopup,
    addGlobalFeedback,
    removeGlobalFeedback,
    reset,
    submit,
    approve,

    // Computed
    feedbackStatusMap,
  };
}
```

---

### F07: LayoutValidator (Main Component)

**Archivo:** `src/components/layout-validator/LayoutValidator.tsx`

```tsx
/**
 * LayoutValidator - Componente principal de validación.
 *
 * Orquesta todos los sub-componentes y el hook de lógica.
 */

import React, { useState } from 'react';
import clsx from 'clsx';
import { useLayoutValidation } from '../../hooks/useLayoutValidation';
import { PreviewFrame } from './PreviewFrame';
import { FeedbackPopup } from './FeedbackPopup';
import { ControlPanel } from './ControlPanel';
import { WarningModal } from './WarningModal';
import { GlobalFeedbackModal } from './GlobalFeedbackModal';
import type { LayoutValidatorProps } from '../../types/validation';

export function LayoutValidator({
  initialHtml,
  onApprove,
  onCancel,
  deviceId,
}: LayoutValidatorProps) {
  const [showWarning, setShowWarning] = useState(false);
  const [showGlobalFeedback, setShowGlobalFeedback] = useState(false);

  const {
    isLoading,
    isSubmitting,
    error,
    preparedHtml,
    elementMap,
    feedback,
    globalFeedback,
    stats,
    popup,
    fixResult,
    handleElementClick,
    handleWorking,
    handleBroken,
    closePopup,
    addGlobalFeedback,
    reset,
    submit,
    approve,
    feedbackStatusMap,
  } = useLayoutValidation({
    initialHtml,
    onSuccess: onApprove,
    onError: (err) => console.error('Validation error:', err),
  });

  // Handle submit with warning check
  const handleSubmit = () => {
    if (stats.progress < 80 && stats.total > 5) {
      setShowWarning(true);
    } else {
      submit();
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4" />
          <p className="text-gray-600">Preparing layout for validation...</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-screen bg-gray-50">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">Error</h2>
          <p className="text-gray-600 mb-4">{error.message}</p>
          <button
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Layout Validator</h1>
            <p className="text-sm text-gray-500">
              Click on elements to test them and provide feedback
            </p>
          </div>

          <div className="flex items-center gap-4">
            {fixResult && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-green-600 font-medium">
                  ✓ {fixResult.errors_fixed} fixes applied
                </span>
              </div>
            )}

            {onCancel && (
              <button
                onClick={onCancel}
                className="px-4 py-2 text-gray-600 hover:text-gray-900"
              >
                Cancel
              </button>
            )}

            {fixResult && (
              <button
                onClick={approve}
                disabled={isSubmitting}
                className={clsx(
                  'px-6 py-2 rounded-lg font-medium',
                  'bg-green-500 text-white',
                  'hover:bg-green-600 disabled:bg-gray-300'
                )}
              >
                Approve & Display
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden p-6">
        <div className="h-full bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <PreviewFrame
            html={preparedHtml}
            elementMap={elementMap}
            feedbackStatus={feedbackStatusMap}
            onElementClick={handleElementClick}
          />
        </div>
      </main>

      {/* Control panel */}
      <ControlPanel
        stats={stats}
        globalFeedback={globalFeedback}
        isSubmitting={isSubmitting}
        onReset={reset}
        onOpenGlobalFeedback={() => setShowGlobalFeedback(true)}
        onSubmit={handleSubmit}
      />

      {/* Feedback popup */}
      <FeedbackPopup
        isOpen={popup.isOpen}
        element={popup.element}
        position={popup.position}
        onWorking={handleWorking}
        onBroken={handleBroken}
        onClose={closePopup}
      />

      {/* Warning modal */}
      <WarningModal
        isOpen={showWarning}
        stats={stats}
        onContinue={() => {
          setShowWarning(false);
          submit();
        }}
        onCancel={() => setShowWarning(false)}
      />

      {/* Global feedback modal */}
      <GlobalFeedbackModal
        isOpen={showGlobalFeedback}
        existingFeedback={globalFeedback}
        onSubmit={(msg) => {
          addGlobalFeedback(msg);
        }}
        onClose={() => setShowGlobalFeedback(false)}
      />
    </div>
  );
}
```

---

### F08: validationApi

**Archivo:** `src/services/validationApi.ts`

```typescript
/**
 * API client para el sistema de validación.
 */

import type {
  PrepareValidationRequest,
  PrepareValidationResponse,
  FixWithFeedbackRequest,
  FixWithFeedbackResponse,
  ApproveLayoutRequest,
  ApproveLayoutResponse,
} from '../types/validation';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP error ${response.status}`);
  }
  return response.json();
}

function getAuthHeaders(): HeadersInit {
  const token = localStorage.getItem('auth_token');
  return {
    'Content-Type': 'application/json',
    ...(token && { Authorization: `Bearer ${token}` }),
  };
}

export async function prepareValidation(
  html: string
): Promise<PrepareValidationResponse> {
  const response = await fetch(`${API_BASE}/feedback/prepare-validation`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify({ html } as PrepareValidationRequest),
  });

  return handleResponse<PrepareValidationResponse>(response);
}

export async function fixWithFeedback(
  request: FixWithFeedbackRequest
): Promise<FixWithFeedbackResponse> {
  const response = await fetch(`${API_BASE}/feedback/fix-with-feedback`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(request),
  });

  return handleResponse<FixWithFeedbackResponse>(response);
}

export async function approveLayout(
  request: ApproveLayoutRequest
): Promise<ApproveLayoutResponse> {
  const response = await fetch(`${API_BASE}/feedback/approve`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(request),
  });

  return handleResponse<ApproveLayoutResponse>(response);
}
```

---

### F09: WarningModal

**Archivo:** `src/components/layout-validator/WarningModal.tsx`

```tsx
/**
 * WarningModal - Advertencia cuando el feedback está incompleto.
 */

import React from 'react';
import clsx from 'clsx';
import type { WarningModalProps } from '../../types/validation';

export function WarningModal({
  isOpen,
  stats,
  onContinue,
  onCancel,
}: WarningModalProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-[9998]" onClick={onCancel} />

      {/* Modal */}
      <div
        className={clsx(
          'fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999]',
          'bg-white rounded-xl shadow-2xl p-6 w-[420px]',
          'animate-bounce-in'
        )}
      >
        <div className="text-center">
          <div className="text-5xl mb-4">⚠️</div>
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            Incomplete Testing
          </h2>
          <p className="text-gray-600 mb-4">
            You've only tested <strong>{stats.progress}%</strong> of the
            interactive elements ({stats.tested} of {stats.total}).
          </p>
          <p className="text-sm text-gray-500 mb-6">
            For better results, we recommend testing at least 80% of elements
            before submitting feedback.
          </p>

          <div className="flex gap-3">
            <button
              onClick={onCancel}
              className={clsx(
                'flex-1 py-3 px-4 rounded-lg font-medium',
                'bg-gray-100 text-gray-700 hover:bg-gray-200'
              )}
            >
              Keep Testing
            </button>
            <button
              onClick={onContinue}
              className={clsx(
                'flex-1 py-3 px-4 rounded-lg font-medium',
                'bg-yellow-500 text-white hover:bg-yellow-600'
              )}
            >
              Submit Anyway
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
```

---

### F10: GlobalFeedbackModal

**Archivo:** `src/components/layout-validator/GlobalFeedbackModal.tsx`

```tsx
/**
 * GlobalFeedbackModal - Modal para reportar elementos faltantes.
 */

import React, { useState } from 'react';
import clsx from 'clsx';
import type { GlobalFeedbackModalProps } from '../../types/validation';

export function GlobalFeedbackModal({
  isOpen,
  existingFeedback,
  onSubmit,
  onClose,
}: GlobalFeedbackModalProps) {
  const [message, setMessage] = useState('');

  if (!isOpen) return null;

  const handleSubmit = () => {
    if (message.trim()) {
      onSubmit(message.trim());
      setMessage('');
    }
  };

  const suggestions = [
    'Missing a back button',
    'Needs footer with links',
    'Form needs validation',
    'Missing loading state',
  ];

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 z-[9998]" onClick={onClose} />

      {/* Modal */}
      <div
        className={clsx(
          'fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[9999]',
          'bg-white rounded-xl shadow-2xl p-6 w-[500px] max-h-[80vh] overflow-y-auto',
          'animate-bounce-in'
        )}
      >
        <h2 className="text-xl font-bold text-gray-900 mb-2">
          Global Feedback
        </h2>
        <p className="text-gray-600 mb-4">
          Report missing elements or features that aren't related to a specific
          interactive element.
        </p>

        {/* Existing feedback */}
        {existingFeedback.length > 0 && (
          <div className="mb-4">
            <p className="text-sm font-medium text-gray-700 mb-2">
              Already reported:
            </p>
            <ul className="space-y-1">
              {existingFeedback.map((fb, i) => (
                <li
                  key={i}
                  className="text-sm bg-yellow-50 text-yellow-800 px-3 py-2 rounded flex items-center gap-2"
                >
                  <span className="text-yellow-500">•</span>
                  {fb}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Input */}
        <div className="mb-4">
          <label className="text-sm font-medium text-gray-700 mb-1 block">
            What's missing or should change?
          </label>
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="e.g., Missing a back button at the top, needs contact section..."
            className={clsx(
              'w-full h-24 p-3 border-2 border-gray-200 rounded-lg',
              'focus:border-blue-400 focus:ring-2 focus:ring-blue-100 focus:outline-none',
              'resize-none text-sm'
            )}
            autoFocus
          />
        </div>

        {/* Suggestions */}
        <div className="mb-4 bg-gray-50 p-3 rounded-lg">
          <p className="text-xs font-medium text-gray-500 mb-2">SUGGESTIONS:</p>
          <div className="flex flex-wrap gap-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                onClick={() => setMessage(suggestion)}
                className={clsx(
                  'text-xs px-2 py-1 rounded',
                  'bg-white border border-gray-200',
                  'hover:bg-gray-100'
                )}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        {/* Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 px-4 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium"
          >
            Close
          </button>
          <button
            onClick={handleSubmit}
            disabled={!message.trim()}
            className={clsx(
              'flex-1 py-2 px-4 rounded-lg font-medium',
              'bg-blue-500 text-white',
              'hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed'
            )}
          >
            Add Feedback
          </button>
        </div>
      </div>
    </>
  );
}
```

---

### F11: Index (Barrel Export)

**Archivo:** `src/components/layout-validator/index.tsx`

```typescript
export { LayoutValidator } from './LayoutValidator';
export { PreviewFrame } from './PreviewFrame';
export { FeedbackPopup } from './FeedbackPopup';
export { ControlPanel } from './ControlPanel';
export { WarningModal } from './WarningModal';
export { GlobalFeedbackModal } from './GlobalFeedbackModal';
```

---

## Definition of Done

### Checklist Frontend

- [ ] **F01**: Proyecto React + TypeScript + Tailwind configurado
- [ ] **F02**: Types TypeScript definidos para todo el sistema
- [ ] **F03**: PreviewFrame muestra HTML en iframe
- [ ] **F03**: PreviewFrame captura clicks via postMessage
- [ ] **F03**: PreviewFrame actualiza estilos de feedback
- [ ] **F04**: FeedbackPopup permite marcar ✅/❌
- [ ] **F04**: FeedbackPopup permite agregar mensaje para broken
- [ ] **F05**: ControlPanel muestra progreso correctamente
- [ ] **F05**: ControlPanel incluye botón Global Feedback
- [ ] **F06**: useLayoutValidation maneja todo el estado
- [ ] **F06**: useLayoutValidation llama APIs correctamente
- [ ] **F07**: LayoutValidator integra todos los componentes
- [ ] **F08**: validationApi funciona con el backend
- [ ] **F09**: WarningModal aparece cuando feedback < 80%
- [ ] **F10**: GlobalFeedbackModal permite agregar feedback
- [ ] **F11**: Estilos y animaciones funcionan
- [ ] **F12**: Tests de componentes pasan

---

## Verificación

```bash
# Instalar y correr
cd frontend
npm install
npm run dev

# Build para producción
npm run build

# Correr tests
npm run test

# Type check
npm run typecheck
```

---

## Métricas de Éxito

| Métrica | Target |
|---------|--------|
| Feedback capturado | 100% de clicks |
| Popup latency | <100ms |
| Time to first paint | <2s |
| Bundle size | <200KB gzip |
| Test coverage | >70% |
| TypeScript errors | 0 |
