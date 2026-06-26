#!/usr/bin/env python3
"""
extend_dashboard_template_with_workflow.py — Sprint I

Idempotent injection of the Berater-CRM-Workflow surfaces into the
dashboard template (blessin_network_v3.html). All inserts are wrapped
in `<!-- WORKFLOW_INSERT -->` markers so this script can be re-run
without duplicating content.

What it injects
---------------
1. <link rel="stylesheet" href="/assets/workflow.css"> in <head>
2. <script src="/assets/workflow.js" defer></script> just before </body>
3. Workflow widgets inside the right-hand detail panel
   (<aside class="sidebar-right" id="detail-panel">), placed AFTER the
   meta/agent/avail/contract/gs detail rows so they sit above the
   summary section. Widgets read the active contact's tm_id from the
   detail-panel via a `data-active-tm-id` attribute that the existing
   `openDetail()` flow can stamp on the panel — until then the widgets
   stay hidden via the `data-tm-id=""` no-op render.

Smoke test after run:
    grep -c "WORKFLOW_INSERT" blessin_network_v3.html   # >= 3
    grep "workflow.js" blessin_network_v3.html
"""

from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
TEMPLATE = BASE / "blessin_network_v3.html"

CSS_LINK = '  <link rel="stylesheet" href="/assets/workflow.css"><!-- WORKFLOW_INSERT:css -->\n'
JS_TAG = '<script src="/assets/workflow.js" defer></script><!-- WORKFLOW_INSERT:js -->\n'

WIDGETS = """    <!-- WORKFLOW_INSERT:widgets — Sprint I Berater-CRM (idempotent) -->
    <div class="workflow-pipeline" data-active-tm-id="">
      <label>Pipeline-Status</label>
      <select class="pipeline-stage" data-tm-id="">
        <option value="">— nicht in Pipeline —</option>
        <option value="watching">Beobachtung</option>
        <option value="contacted">Kontaktiert</option>
        <option value="in_talks">Im Gespräch</option>
        <option value="mandate">Mandat</option>
        <option value="placed">Vermittelt</option>
        <option value="passed">Abgeschlossen</option>
      </select>
      <label class="pin-toggle">
        <input type="checkbox" class="pipeline-pin" data-tm-id="">
        Anpinnen — Daily-Digest
      </label>
    </div>
    <div class="workflow-notes" data-tm-id="">
      <label>Notizen</label>
      <ul class="notes-list" data-tm-id=""></ul>
      <textarea class="note-input" placeholder="Neue Notiz (Markdown ok). Tags via #call #2027"></textarea>
      <button type="button" class="note-save">Speichern</button>
    </div>
    <div class="workflow-reminder" data-tm-id="">
      <label>Reminder</label>
      <input type="date" class="reminder-date" />
      <input type="text" class="reminder-text" placeholder="z.B. Anruf zur Vertragsverlängerung" />
      <button type="button" class="reminder-add">+</button>
      <ul class="reminders-list" data-tm-id=""></ul>
    </div>
    <!-- /WORKFLOW_INSERT:widgets -->
"""

WIDGET_BIND_SCRIPT = """<script><!-- WORKFLOW_INSERT:bind -->
// Bind detail-panel openDetail to workflow widgets:
// each time a contact panel opens, copy the active tm_id onto the workflow
// containers so PF_WORKFLOW.refreshPipelineUI / renderNotes / renderReminders
// pick the right entry. Hooks the existing global `openDetail` if present.
(function(){
  function syncTmId(tmId) {
    const id = tmId == null ? '' : String(tmId);
    document.querySelectorAll('.workflow-pipeline [data-tm-id], .workflow-notes, .workflow-notes [data-tm-id], .workflow-reminder, .workflow-reminder [data-tm-id]').forEach(el => {
      el.dataset.tmId = id;
    });
    if (window.PF_WORKFLOW) {
      window.PF_WORKFLOW.refreshPipelineUI();
      if (id) {
        window.PF_WORKFLOW.renderNotes(id);
        window.PF_WORKFLOW.renderReminders(id);
      }
    }
  }
  // Wrap existing openDetail if defined later — poll once on idle
  function tryWrap() {
    if (typeof window.openDetail === 'function' && !window.openDetail.__wfWrapped) {
      const orig = window.openDetail;
      window.openDetail = function(c, ...rest) {
        const r = orig.apply(this, [c, ...rest]);
        try { syncTmId(c && (c.tm_id || c.tmId)); } catch (_) {}
        return r;
      };
      window.openDetail.__wfWrapped = true;
    }
  }
  if (document.readyState === 'complete') tryWrap();
  else window.addEventListener('load', tryWrap);
  // Also expose for templates that fire a custom event
  document.addEventListener('contact-opened', (e) => syncTmId(e.detail && e.detail.tm_id));
})();
</script>
"""


def patch(text: str) -> tuple[str, list[str]]:
    changes = []

    # 1. CSS link in <head>
    if "WORKFLOW_INSERT:css" not in text:
        anchor = '<link rel="stylesheet" href="/assets/haptik.css">'
        if anchor in text:
            text = text.replace(anchor, anchor + "\n" + CSS_LINK.rstrip("\n"))
            changes.append("css link injected after haptik.css")
        else:
            text = text.replace("</head>", CSS_LINK + "</head>", 1)
            changes.append("css link injected before </head> (fallback)")
    else:
        changes.append("css link already present (skipped)")

    # 2. Detail-panel widgets — insert before closing </aside> of #detail-panel
    if "WORKFLOW_INSERT:widgets" not in text:
        marker = '<aside class="sidebar-right" id="detail-panel">'
        if marker in text:
            close_idx = text.index("</aside>", text.index(marker))
            text = text[:close_idx] + WIDGETS + "  " + text[close_idx:]
            changes.append("widgets injected into #detail-panel (before </aside>)")
        else:
            changes.append("WARNING: detail-panel anchor not found — widgets NOT injected")
    else:
        changes.append("widgets already present (skipped)")

    # 3. JS tag + bind script before </body>
    if "WORKFLOW_INSERT:js" not in text:
        # Insert bind-script first so PF_WORKFLOW exists before wrap fires
        body_close = "</body>"
        if body_close in text:
            text = text.replace(body_close, JS_TAG + WIDGET_BIND_SCRIPT + body_close, 1)
            changes.append("workflow.js + bind script injected before </body>")
        else:
            changes.append("WARNING: </body> not found — js NOT injected")
    else:
        changes.append("workflow js already present (skipped)")

    return text, changes


def main() -> int:
    if not TEMPLATE.exists():
        print(f"  ✗ Template not found: {TEMPLATE}")
        return 1
    original = TEMPLATE.read_text(encoding="utf-8")
    patched, changes = patch(original)
    if patched == original:
        print("  → No changes (already patched).")
        for c in changes:
            print(f"    - {c}")
        return 0
    TEMPLATE.write_text(patched, encoding="utf-8")
    print(f"  ✓ Patched {TEMPLATE.relative_to(BASE)}")
    for c in changes:
        print(f"    - {c}")
    print("")
    print("  → Run regenerate_dashboards.py to bake the new template into all output/dashboards/*.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
