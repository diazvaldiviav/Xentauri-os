# Generation Prompt - Tailwind CSS Rules

> **Purpose:** This prompt is injected into the LLM that GENERATES HTML layouts.
> Following these rules prevents 50%+ of common interactivity errors.

## Target Environment

- Display: 1920x1080 touchscreen TV
- Theme: Dark mode
- Framework: Tailwind CSS (CDN included)
- No external dependencies

---

## MANDATORY TAILWIND RULES

### 1. Z-Index (ALWAYS explicit on overlays)

Use this z-index scale consistently:

| Layer | Class | Use Case |
|-------|-------|----------|
| Base | `z-0` | Background containers |
| Content | `z-10` | Normal content, buttons |
| Dropdowns | `z-20` | Dropdowns, tooltips |
| Elevated | `z-30` | Elevated cards |
| Modal Backdrop | `z-40` | Semi-transparent overlays |
| Modal Content | `z-50` | Modal dialogs |
| Toast/Alert | `z-[100]` | Notifications |

```html
<!-- CORRECT: Explicit z-index hierarchy -->
<div class="relative z-0">
  <button class="relative z-10">Click me</button>
  <div class="absolute z-40 bg-black/50">Backdrop</div>
  <div class="relative z-50">Modal</div>
</div>

<!-- INCORRECT: No z-index = stacking issues -->
<div class="relative">
  <button>Click me</button>  <!-- May be covered! -->
  <div class="absolute">Backdrop</div>
</div>
```

### 2. Pointer Events (ALWAYS on overlays)

Overlays that should NOT block clicks MUST have `pointer-events-none`:

```html
<!-- CORRECT: Overlay passes clicks through -->
<div class="absolute inset-0 pointer-events-none">
  <button class="pointer-events-auto relative z-10">Click me</button>
</div>

<!-- INCORRECT: Overlay blocks all clicks -->
<div class="absolute inset-0">
  <button>Click me</button>  <!-- BLOCKED! -->
</div>
```

**Rule:** If an element has `absolute inset-0` or `fixed inset-0`, it MUST have either:
- `pointer-events-none` (pass-through overlay), OR
- Explicit z-index for blocking (modal backdrop)

### 3. Interactive Elements (ALWAYS)

All clickable elements MUST have:

```html
<!-- CORRECT: Proper interactive element -->
<button class="relative z-10 bg-blue-600 hover:bg-blue-700
               active:scale-95 active:bg-blue-800
               transition-all duration-150">
  Click me
</button>

<!-- INCORRECT: No positioning, weak feedback -->
<button class="bg-blue-600 hover:bg-blue-700">
  Click me
</button>
```

**Minimum requirements for interactive elements:**
- `relative` - Creates stacking context
- `z-10` - Ensures element is above background
- `active:scale-95` or `active:bg-*` - Visible click feedback
- `transition-all duration-150` - Smooth feedback

### 4. Transforms 3D (ALWAYS with these classes)

Card flips and 3D transforms require specific classes:

```html
<!-- CORRECT: Proper 3D card flip -->
<div class="[perspective:1000px]">
  <div class="relative w-64 h-40 [transform-style:preserve-3d] transition-transform duration-500
              hover:[transform:rotateY(180deg)]">
    <!-- Front face -->
    <div class="absolute inset-0 [backface-visibility:hidden] bg-blue-600 rounded-lg">
      Front
    </div>
    <!-- Back face -->
    <div class="absolute inset-0 [backface-visibility:hidden] [transform:rotateY(180deg)]
                bg-green-600 rounded-lg">
      Back
    </div>
  </div>
</div>

<!-- INCORRECT: Missing 3D properties -->
<div>
  <div class="relative transition-transform hover:rotate-y-180">
    <div class="absolute inset-0">Front</div>
    <div class="absolute inset-0">Back</div>  <!-- Both visible! -->
  </div>
</div>
```

**Required classes for 3D:**
- Parent: `[perspective:1000px]`
- Transform container: `[transform-style:preserve-3d]`
- Each face: `[backface-visibility:hidden]`

### 5. Visual Feedback (ALWAYS visible)

Click feedback MUST be obvious (>30% of element pixels should change):

```html
<!-- CORRECT: Obvious feedback -->
<button class="bg-blue-600
               hover:bg-blue-500
               active:bg-blue-800 active:scale-95
               focus:ring-4 focus:ring-blue-400
               transition-all duration-150">
  Click
</button>

<!-- INCORRECT: Subtle feedback (fails validation) -->
<button class="bg-blue-600 hover:bg-blue-650">
  Click
</button>
```

**Recommended feedback combinations:**
- `active:scale-95` + `active:bg-*` (scale + color)
- `active:brightness-75` + `active:ring-4` (darken + ring)
- Background color change of at least 2 Tailwind steps (e.g., 600 → 800)

---

## PROHIBITED PATTERNS

These patterns WILL cause validation failures:

### ❌ Overlay without pointer-events

```html
<!-- PROHIBITED -->
<div class="absolute inset-0">
  <!-- This blocks everything underneath -->
</div>
```

### ❌ z-auto on positioned elements

```html
<!-- PROHIBITED -->
<button class="relative">  <!-- No z-index = unpredictable stacking -->
  Click
</button>
```

### ❌ Transforms without preserve-3d

```html
<!-- PROHIBITED -->
<div class="rotate-y-180">
  <div class="backface-hidden">  <!-- Won't work without preserve-3d parent -->
</div>
```

### ❌ Cards 3D without backface-visibility

```html
<!-- PROHIBITED -->
<div class="[transform-style:preserve-3d]">
  <div class="absolute">Front</div>
  <div class="absolute [transform:rotateY(180deg)]">Back</div>
  <!-- Both faces visible simultaneously! -->
</div>
```

### ❌ Subtle hover-only feedback

```html
<!-- PROHIBITED: No active state -->
<button class="bg-blue-600 hover:bg-blue-700">
  Click  <!-- No feedback when actually clicked -->
</button>
```

### ❌ CSS variables in critical styles

```html
<!-- PROHIBITED: Variables may not be defined -->
<button class="bg-[var(--primary)]">
  Click
</button>

<!-- CORRECT: Use concrete values -->
<button class="bg-blue-600">
  Click
</button>
```

---

## MODAL/OVERLAY REQUIREMENTS

Modals and overlays MUST follow these rules:

### 1. Auto-dismiss OR close button

```html
<!-- Option A: Auto-dismiss after action -->
<div id="feedback" class="fixed inset-0 z-50 flex items-center justify-center
                          pointer-events-none opacity-0 transition-opacity">
  <div class="bg-green-600 p-4 rounded-lg pointer-events-auto">
    Correct!
  </div>
</div>
<script>
function showFeedback() {
  const el = document.getElementById('feedback');
  el.classList.remove('opacity-0');
  setTimeout(() => el.classList.add('opacity-0'), 1500); // Auto-dismiss
}
</script>

<!-- Option B: Close button -->
<div class="fixed inset-0 z-40 bg-black/50" onclick="closeModal()">
  <div class="relative z-50 bg-gray-800 p-6 rounded-lg" onclick="event.stopPropagation()">
    <button onclick="closeModal()" class="absolute top-2 right-2 text-gray-400 hover:text-white">
      ✕
    </button>
    Content here
  </div>
</div>
```

### 2. Never block other interactive elements permanently

The validator clicks multiple elements sequentially. If a modal blocks other elements:
- Validation fails (e.g., 1/8 responsive)
- Always provide a way to dismiss

---

## DATA ATTRIBUTES FOR VALIDATION

Add these attributes to help the validator identify elements:

### Trivia/Quiz

```html
<div data-trivia="container">
  <div data-question="1">
    <button data-option>Option A</button>
    <button data-option>Option B</button>
  </div>
  <button data-submit>Submit</button>
  <div data-score>Score: 0</div>
  <div data-feedback>Feedback here</div>
</div>
```

### Games

```html
<div data-game="container">
  <button data-start>Start Game</button>
  <div data-score>0</div>
  <div data-lives>❤️❤️❤️</div>
  <button data-restart>Play Again</button>
</div>
```

### Dashboards

```html
<div data-dashboard="container">
  <select data-filter>...</select>
  <div data-metric>$1,234</div>
  <div data-chart>...</div>
</div>
```

---

## TEMPLATE STRUCTURE

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1920, height=1080">
  <title>Layout</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          // Custom theme extensions if needed
        }
      }
    }
  </script>
</head>
<body class="bg-gray-900 text-white min-h-screen">

  <!-- Main content with proper z-index hierarchy -->
  <main class="relative z-0 p-8">

    <!-- Interactive elements with proper classes -->
    <button class="relative z-10 px-6 py-3 bg-blue-600 rounded-lg
                   hover:bg-blue-500 active:bg-blue-800 active:scale-95
                   transition-all duration-150">
      Click me
    </button>

  </main>

  <!-- Modals/overlays at higher z-index -->
  <div id="modal" class="fixed inset-0 z-40 hidden">
    <div class="absolute inset-0 bg-black/50" onclick="closeModal()"></div>
    <div class="relative z-50 ...">
      Modal content
    </div>
  </div>

</body>
</html>
```

---

## CHECKLIST BEFORE GENERATING

- [ ] All buttons have `relative z-10`
- [ ] All overlays have `pointer-events-none` or explicit z-index
- [ ] All interactive elements have `active:*` feedback
- [ ] All transitions have `duration-*`
- [ ] 3D transforms have `[perspective:*]`, `[transform-style:preserve-3d]`, `[backface-visibility:hidden]`
- [ ] Modals can be dismissed
- [ ] No CSS variables (use concrete Tailwind colors)
- [ ] Data attributes added for validation
