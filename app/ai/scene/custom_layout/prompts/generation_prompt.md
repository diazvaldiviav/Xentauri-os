# HTML Generation Rules

## 🚨 RULE #1: HTML-FIRST (CRITICAL)

**ALL interactive elements MUST exist in the initial HTML. The validator CANNOT see elements created by JavaScript.**

### Forbidden JavaScript:
```javascript
document.createElement()     // ❌ FORBIDDEN
el.innerHTML = '<button>'    // ❌ FORBIDDEN
el.appendChild(node)         // ❌ FORBIDDEN
el.insertAdjacentHTML()      // ❌ FORBIDDEN
```

### Allowed JavaScript:
```javascript
el.classList.add('hidden')           // ✅ Toggle visibility
el.classList.remove('active')        // ✅ Toggle state
el.textContent = 'New text'          // ✅ Update text
el.style.display = 'none'            // ✅ Hide element
el.querySelector('.x').textContent   // ✅ Update nested text
```

### Pattern:
```html
<!-- Pre-render ALL elements, use hidden class -->
<button id="btn1" class="...">Option 1</button>
<button id="btn2" class="...">Option 2</button>
<div id="modal" class="hidden">...</div>

<script>
// JS only toggles classes and updates text
function show() { modal.classList.remove('hidden'); }
function updateText(id, text) { document.getElementById(id).textContent = text; }
</script>
```

---

## RULE #2: Z-INDEX HIERARCHY

| Layer | Class | Use |
|-------|-------|-----|
| Base | `z-0` | Backgrounds |
| Content | `z-10` | Buttons, inputs |
| Dropdown | `z-20` | Menus |
| Modal BG | `z-40` | Backdrop |
| Modal | `z-50` | Dialog |

**All buttons MUST have `relative z-10`**

---

## RULE #3: POINTER-EVENTS

Overlays with `absolute inset-0` or `fixed inset-0` MUST have:
- `pointer-events-none` (decorative overlay), OR
- Explicit click handler (modal backdrop)

```html
<!-- Decorative: passes clicks through -->
<div class="absolute inset-0 bg-gradient-... pointer-events-none"></div>

<!-- Modal backdrop: blocks but is dismissable -->
<div class="fixed inset-0 bg-black/50 z-40" onclick="close()"></div>
```

---

## RULE #4: CLICK FEEDBACK

All interactive elements MUST have visible active state:

```html
<button class="relative z-10 bg-blue-600
               hover:bg-blue-500
               active:scale-95 active:bg-blue-800
               transition-all duration-150">
```

**Minimum:** `active:scale-95` OR `active:bg-*` (2+ steps darker)

---

## RULE #5: MODALS

- Must be dismissable (close button OR backdrop click OR auto-dismiss)
- Use `hidden` class, toggle with JS
- Backdrop: `z-40`, Content: `z-50`

---

## RULE #6: 3D TRANSFORMS

```html
<div class="[perspective:1000px]">
  <div class="[transform-style:preserve-3d]">
    <div class="[backface-visibility:hidden]">Front</div>
    <div class="[backface-visibility:hidden] [transform:rotateY(180deg)]">Back</div>
  </div>
</div>
```

---

## RULE #7: DATA ATTRIBUTES

Add `data-*` attributes for validator identification:
- `data-start` - Start/play buttons
- `data-restart` - Restart buttons
- `data-option` - Selectable options
- `data-score` - Score displays
- `data-feedback` - Feedback containers

---

## TEMPLATE

```html
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=1920, height=1080">
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white h-screen overflow-hidden">

  <!-- All interactive elements pre-rendered -->
  <main class="relative z-0">
    <button class="relative z-10 ... active:scale-95">Click</button>
  </main>

  <!-- Modals pre-rendered with hidden -->
  <div id="modal" class="fixed inset-0 z-50 hidden">
    <div class="absolute inset-0 bg-black/50" onclick="closeModal()"></div>
    <div class="relative z-50 ...">Content</div>
  </div>

  <script>
    // JS only toggles classes and updates text
  </script>
</body>
</html>
```

---

## CHECKLIST

- [ ] All interactive elements in HTML (not created by JS)
- [ ] JS only toggles classes / updates text
- [ ] All buttons: `relative z-10`
- [ ] All overlays: `pointer-events-none` or dismissable
- [ ] All buttons: `active:scale-95` or `active:bg-*`
- [ ] All transitions: `duration-150`
- [ ] Modals dismissable
- [ ] No CSS variables (use concrete colors)
