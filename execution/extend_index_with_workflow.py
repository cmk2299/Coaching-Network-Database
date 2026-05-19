#!/usr/bin/env python3
"""
extend_index_with_workflow.py — Sprint I

Idempotent post-build patch on output/index.html:

1. Adds <link rel="stylesheet" href="/assets/workflow.css"> in <head>
2. Adds <script src="/assets/workflow.js" defer></script> before </body>
3. Adds <aside class="saved-filters">…</aside> right after the search wrap
4. Adds a stage-badge slot to each `.row-wrap` row using the COACHES JS
   map already embedded in the page. Done via a small client-side IIFE
   appended to the existing <script> block — no DOM rewrite needed.

All inserts wrapped in `<!-- WORKFLOW_INSERT:* -->` markers so re-runs
are no-ops.

Usage:
    python3 execution/extend_index_with_workflow.py
"""

from pathlib import Path
import re
import sys

BASE = Path(__file__).resolve().parent.parent
INDEX = BASE / "output" / "index.html"

CSS_LINK = '<link rel="stylesheet" href="/assets/workflow.css"><!-- WORKFLOW_INSERT:css -->\n'
JS_TAG = '<script src="/assets/workflow.js" defer></script><!-- WORKFLOW_INSERT:js -->\n'

SAVED_FILTERS_HTML = """<!-- WORKFLOW_INSERT:saved-filters -->
<aside class="saved-filters">
  <h4>Meine Filter</h4>
  <ul id="saved-filters-list"></ul>
  <button id="save-current-filter" type="button">Aktuellen Filter speichern</button>
</aside>
<!-- /WORKFLOW_INSERT:saved-filters -->
"""

# Client-side stamping: read COACHES, attach data-tm-id to rows, render badges.
# Also wires the "save current filter" button using the search-input value.
STAMP_SCRIPT = """<script><!-- WORKFLOW_INSERT:stamp -->
(function(){
  function bySlug() {
    const out = {};
    if (typeof COACHES !== 'object') return out;
    for (const cid in COACHES) {
      const c = COACHES[cid];
      if (!c || !c.tm_id) continue;
      const slug = (c.name || '').toLowerCase()
        .replace(/[äöü]/g, m => ({'ä':'a','ö':'o','ü':'u'}[m]))
        .replace(/ß/g, 'ss')
        .replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
      out[slug] = c.tm_id;
    }
    return out;
  }

  function stampRows() {
    const map = bySlug();
    document.querySelectorAll('.row-wrap').forEach(wrap => {
      if (wrap.dataset.tmId) return;
      const a = wrap.querySelector('a.row');
      if (!a) return;
      const m = (a.getAttribute('href') || '').match(/dashboards\\/([^/]+?)_(?:network|sd_network|nlz_network)\\.html/);
      if (!m) return;
      const slug = m[1];
      const tmId = map[slug];
      if (!tmId) return;
      wrap.dataset.tmId = String(tmId);
      // Insert badge slot near the row name
      const nameEl = a.querySelector('.row-name');
      if (nameEl && !nameEl.querySelector('.row-stage')) {
        const span = document.createElement('span');
        span.className = 'row-stage';
        span.dataset.tmId = String(tmId);
        nameEl.appendChild(span);
      }
    });
    if (window.PF_WORKFLOW) window.PF_WORKFLOW.refreshPipelineUI();
  }

  function wireSaveFilter() {
    const btn = document.getElementById('save-current-filter');
    if (!btn) return;
    btn.addEventListener('click', () => {
      const q = (document.getElementById('q') || {}).value || '';
      const name = prompt('Filter benennen:', q || 'Mein Filter');
      if (!name) return;
      window.PF_WORKFLOW && window.PF_WORKFLOW.saveCurrentFilter(name, { q });
    });
    document.addEventListener('filter-changed', (e) => {
      const q = (e.detail && e.detail.q) || '';
      const input = document.getElementById('q');
      if (input) { input.value = q; if (typeof filter === 'function') filter(); }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => { stampRows(); wireSaveFilter(); });
  } else {
    stampRows(); wireSaveFilter();
  }
})();
</script>
"""


def patch(text: str) -> tuple[str, list[str]]:
    changes = []

    # 1. CSS link
    if "WORKFLOW_INSERT:css" not in text:
        anchor = '<link rel="stylesheet" href="/assets/haptik.css">'
        if anchor in text:
            text = text.replace(anchor, anchor + "\n" + CSS_LINK.rstrip("\n"))
            changes.append("css link injected after haptik.css")
        elif "</head>" in text:
            text = text.replace("</head>", CSS_LINK + "</head>", 1)
            changes.append("css link injected before </head>")
    else:
        changes.append("css link already present (skipped)")

    # 2. Saved-filters sidebar — after search-wrap div
    if "WORKFLOW_INSERT:saved-filters" not in text:
        m = re.search(r'(<div class="search-wrap"[^>]*>.*?</div>)', text, re.DOTALL)
        if m:
            insert_at = m.end()
            text = text[:insert_at] + "\n" + SAVED_FILTERS_HTML + text[insert_at:]
            changes.append("saved-filters sidebar injected after search-wrap")
        else:
            changes.append("WARNING: search-wrap anchor not found — saved-filters NOT injected")
    else:
        changes.append("saved-filters already present (skipped)")

    # 3. JS tag + stamping IIFE before </body>
    if "WORKFLOW_INSERT:js" not in text:
        if "</body>" in text:
            text = text.replace("</body>", JS_TAG + STAMP_SCRIPT + "</body>", 1)
            changes.append("workflow.js + stamp script injected before </body>")
        else:
            changes.append("WARNING: </body> not found")
    else:
        changes.append("workflow js already present (skipped)")

    return text, changes


def main() -> int:
    if not INDEX.exists():
        print(f"  ✗ Index not found: {INDEX}")
        return 1
    original = INDEX.read_text(encoding="utf-8")
    patched, changes = patch(original)
    if patched == original:
        print(f"  → No changes (already patched).")
    else:
        INDEX.write_text(patched, encoding="utf-8")
        print(f"  ✓ Patched {INDEX.relative_to(BASE)}")
    for c in changes:
        print(f"    - {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
