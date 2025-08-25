import json

import pandas as pd


# Read CSV (change the path to your file)


def npc_relation_map(filepath):
    df = pd.read_csv(filepath)
    npc_map = {}
    for _, row in df.iterrows():
        src = ''.join([c for c in row['SourceNPCID'] if not c.isdigit()])
        tgt = ''.join([c for c in row['TargerNPCID'] if not c.isdigit()])
        relation_data = {
            'Attitude': row['Attitude'],
            'AttitudeScore': row['AttitudeScore'],
            'relation': row['relation']
        }
        if src not in npc_map:
            npc_map[src] = {}
        npc_map[src][tgt] = relation_data
    return npc_map


def _normalize_change_records(messages):
    """
    Merge message fragments into per-(src,tgt) records that may contain:
      newAttitude, newRelation, intermediatorDialogue, RecipientDialogue, Rationale
    Supports both old and new schemas.
    """
    buckets = {}  # (src, tgt) -> merged dict

    for m in messages or []:
        # Source
        src = m.get('intermediatorID') or m.get('IntermediatorID')
        # Target can appear under different keys depending on schema
        tgt = (
            m.get('RecipientID') or
            m.get('AttAndRelRCPT') or
            m.get('starterID')  # old "short" record: target is starterID
        )
        if not src or not tgt:
            continue

        key = (src, tgt)
        rec = buckets.setdefault(key, {
            'source': src, 'target': tgt,
            'newAttitude': None, 'newRelation': None,
            'intermediatorDialogue': None, 'RecipientDialogue': None, 'Rationale': None
        })

        # Map all known variants
        new_att = m.get('ItoR_AttitudeChangeTo') or m.get('AttitudeChange')
        new_rel = m.get('ItoR_RelTypeChangeTo') or m.get('RelationshipTypeChange')

        if new_att is not None:
            rec['newAttitude'] = new_att
        if new_rel is not None:
            rec['newRelation'] = new_rel

        if 'intermediatorDialogue' in m:
            rec['intermediatorDialogue'] = m['intermediatorDialogue']
        if 'RecipientDialogue' in m:
            rec['RecipientDialogue'] = m['RecipientDialogue']
        if 'Rationale' in m:
            rec['Rationale'] = m['Rationale']

    return list(buckets.values())


def update_npc_map_with_messages(event, npc_map, messages, changes):
    """
    Applies merged JSON messages to update NPC relations (schema-agnostic).
    Captures original and new values for each change.
    Returns the updated map and the appended change records.
    """
    npc_map = npc_map or {}
    changes = changes or []

    for rec in _normalize_change_records(messages):
        src = rec['source']
        tgt = rec['target']
        new_att = rec.get('newAttitude')
        new_rel = rec.get('newRelation')
        dialog_i = rec.get('intermediatorDialogue')
        dialog_r = rec.get('RecipientDialogue')
        rationale = rec.get('Rationale')

        npc_map.setdefault(src, {}).setdefault(tgt, {})
        orig_att = npc_map[src][tgt].get('Attitude')
        orig_rel = npc_map[src][tgt].get('relation')

        # Only write fields that are provided (avoid overwriting with None)
        if new_att is not None:
            npc_map[src][tgt]['Attitude'] = new_att
        if new_rel is not None:
            npc_map[src][tgt]['relation'] = new_rel

        # Skip completely empty records
        if any(v is not None for v in (new_att, new_rel, dialog_i, dialog_r, rationale)):
            changes.append({
                'event': event,
                'source': src,
                'target': tgt,
                'originalAttitude': orig_att,
                'newAttitude': new_att,
                'originalRelation': orig_rel,
                'newRelation': new_rel,
                'intermediatorDialogue': dialog_i,
                'RecipientDialogue': dialog_r,
                'Rationale': rationale
            })

    return npc_map, changes


def store_change_history(changes):
    import json, html

    with open("npc_viewer.html", "w", encoding="utf-8") as f:
        f.write(r'''
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>NPC Relationship Change Viewer</title>
<style>
  :root { --muted:#666; --chip:#eef2f7; --accent:#0d6efd; }
  body { font-family: system-ui, sans-serif; padding: 20px; line-height: 1.35; }
  h2 { margin: 0 0 10px; }
  .sub { color: var(--muted); margin: 0 0 16px; }
  .tag { display:inline-block; background:#eee; padding:6px 10px; margin:5px 8px 5px 0;
         cursor:pointer; border-radius:14px; font-size:14px; user-select:none }
  .tag.selected { background: var(--accent); color:#fff; }
  #pair-select { margin: 14px 0; }
  #events { margin-top: 10px; }
  .event { border:1px solid #ddd; padding:12px; margin:10px 0; border-radius:10px; background:#fff; }
  .row { display:flex; flex-wrap:wrap; gap:10px; align-items:center; }
  .chip { background:var(--chip); padding:4px 8px; border-radius:999px; font-size:12px; }
  .arrow { margin:0 6px; }
  .muted { color: var(--muted); }
  .kv { margin:6px 0 0 0; }
  .kv strong { display:inline-block; width:105px; color:#333; }
  .empty { display:none; }
  select { padding:6px 10px; border-radius:8px; border:1px solid #ccc; }
  code { background:#f6f8fa; padding:2px 6px; border-radius:6px; }
</style>
</head>
<body>
  <h2>NPC Relationship Change Viewer</h2>
  <p class="sub">Pick a <em>source</em> NPC, then a target. Only non-empty fields are shown.</p>
  <div id="tags"></div>
  <div id="pair-select" style="display:none;">
    <label>
      Select Other NPC:&nbsp;
      <select id="target-select"><option value="">--</option></select>
    </label>
  </div>
  <div id="events"></div>
  <script>
    // Injected from Python:
    const changes =
''')
        json.dump(changes, f, ensure_ascii=False, indent=2)
        f.write(';\n')
        f.write(r'''
// ---------- Helpers ----------
function safe(x) { return (x === undefined || x === null) ? "" : String(x); }
function nz(x, alt="—") { const s = safe(x).trim(); return s ? s : alt; }
function hasVal(x){ return x !== undefined && x !== null && String(x).trim() !== ""; }
function arrowRow(label, oldV, newV){
  if (!hasVal(oldV) && !hasVal(newV)) return "";
  const left = nz(oldV), right = nz(newV);
  if (left === "—" && right === "—") return "";
  return `<div class="kv"><strong>${label}:</strong> <span>${left}</span><span class="arrow"> → </span><span>${right}</span></div>`;
}

// Build list of unique NPC names that appeared as a source
const names = Array.from(new Set(changes.map(c => c.source).filter(Boolean))).sort();

let source = null, target = null;
const tagsDiv       = document.getElementById('tags');
const pairSelectDiv = document.getElementById('pair-select');
const targetSelect  = document.getElementById('target-select');
const eventsDiv     = document.getElementById('events');

// Render NPC “tags” (only those who have ever been a source)
names.forEach(n => {
  const btn = document.createElement('span');
  btn.textContent = n;
  btn.className = 'tag';
  btn.onclick = () => {
    document.querySelectorAll('.tag').forEach(t => t.classList.remove('selected'));
    btn.classList.add('selected');
    source = n;

    // targets tied to this source
    const possibleTargets = Array.from(new Set(
      changes.filter(c => c.source === source && hasVal(c.target)).map(c => c.target)
    )).sort();

    targetSelect.innerHTML = '';
    possibleTargets.forEach(x => {
      const opt = document.createElement('option');
      opt.value = x; opt.textContent = x;
      targetSelect.appendChild(opt);
    });

    if (possibleTargets.length > 0) {
      targetSelect.selectedIndex = 0;
      target = possibleTargets[0];
      renderEvents();
    } else {
      eventsDiv.innerHTML = '<em>No targets found for this source.</em>';
    }
    pairSelectDiv.style.display = '';
  };
  tagsDiv.appendChild(btn);
});

targetSelect.onchange = () => {
  target = targetSelect.value;
  renderEvents();
};

function renderEvents() {
  eventsDiv.innerHTML = '';
  if (!source || !target) return;

  // Show all events matching (source, target)
  const pairEvents = changes.filter(c => c.source === source && c.target === target);

  if (pairEvents.length === 0) {
    eventsDiv.textContent = `No changes recorded between ${source} and ${target}.`;
    return;
  }

  pairEvents.forEach((c, i) => {
    const ev = document.createElement('div');
    ev.className = 'event';

    const headline = safe(c.event) ? safe(c.event) : `Event ${i + 1}`;
    const iDia = nz(c.intermediatorDialogue, "");
    const rDia = nz(c.RecipientDialogue, "");
    const rationale = nz(c.Rationale, "");

    // Build rows conditionally (hide when empty)
    const attRow = arrowRow("Attitude", c.originalAttitude, c.newAttitude);
    const relRow = arrowRow("Relation", c.originalRelation, c.newRelation);
    const dialogI = hasVal(iDia) ? `<div class="kv"><strong>I:</strong> ${iDia}</div>` : "";
    const dialogR = hasVal(rDia) ? `<div class="kv"><strong>R:</strong> ${rDia}</div>` : "";
    const reason  = hasVal(rationale) ? `<div class="kv"><strong>Reason:</strong> ${rationale}</div>` : "";

    // Optional chips summarizing what's present
    const chips = [];
    if (attRow) chips.push(`<span class="chip">Attitude</span>`);
    if (relRow) chips.push(`<span class="chip">Relation</span>`);
    if (dialogI || dialogR) chips.push(`<span class="chip">Dialogue</span>`);
    if (reason) chips.push(`<span class="chip">Rationale</span>`);

    ev.innerHTML = `
      <div class="row">
        <div><strong>${headline}</strong></div>
        <div class="chip">${safe(c.source)}</div>
        <div class="chip">→</div>
        <div class="chip">${safe(c.target)}</div>
        ${chips.join('')}
      </div>
      ${attRow}
      ${relRow}
      ${dialogI}
      ${dialogR}
      ${reason}
    `;

    // If literally nothing to show, collapse to a minimal line
    if (!attRow && !relRow && !dialogI && !dialogR && !reason) {
      ev.innerHTML = `
        <div class="row">
          <div><strong>${headline}</strong></div>
          <span class="muted">No change payload (dialog/att/rel/rationale missing).</span>
        </div>`;
    }

    eventsDiv.appendChild(ev);
  });
}
  </script>
</body>
</html>
''')

if __name__ == "__main__":
    result = npc_relation_map("Z:\\bussiness\\Unreal\\UE_projs\\TheProject\\Content\\System\\initialRelations.csv")
    print(result)

    # Example usage
    messages_json = """
    [
      {
        "intermediatorID": "Celin",
        "RecipientID": "Arthur",
        "intermediatorStatus": "Talking",
        "RecipientStatus": "Listening",
        "intermediatorDialogue": "Why are you speaking ill of Alex? He’s always been kind here.",
        "RecipientDialogue": "I’ve heard things about him that worry me.",
        "ItoR_AttitudeChangeTo": "Wary",
        "ItoR_RelTypeChangeTo": "Distant",
        "Rationale": "Celin values peace and reputation in the village."
      },
      {
        "intermediatorID": "Celin",
        "RecipientID": "Alex",
        "intermediatorStatus": "Talking",
        "RecipientStatus": "Listening",
        "intermediatorDialogue": "Arthur said something troubling about you. Is it true?",
        "RecipientDialogue": "That’s news to me. What exactly did he say?",
        "ItoR_AttitudeChangeTo": "Concerned",
        "ItoR_RelTypeChangeTo": "Wife of",
        "Rationale": "Celin would discreetly inform Alex given their close relationship."
      }
    ]
    """
    messages = json.loads(messages_json)
    updated_map, changes = update_npc_map_with_messages("1",result, messages, [])
    messages_json = """
    [
      {
        "intermediatorID": "Alex",
        "RecipientID": "Arthur",
        "intermediatorStatus": "Talking",
        "RecipientStatus": "Listening",
        "intermediatorDialogue": "Why are you speaking ill of Alex? He’s always been kind here.",
        "RecipientDialogue": "I’ve heard things about him that worry me.",
        "ItoR_AttitudeChangeTo": "Wary",
        "ItoR_RelTypeChangeTo": "Distant",
        "Rationale": "Celin values peace and reputation in the village."
      },
      {
        "intermediatorID": "Alex",
        "RecipientID": "Bob",
        "intermediatorStatus": "Talking",
        "RecipientStatus": "Listening",
        "intermediatorDialogue": "Arthur said something troubling about you. Is it true?",
        "RecipientDialogue": "That’s news to me. What exactly did he say?",
        "ItoR_AttitudeChangeTo": "Concerned",
        "ItoR_RelTypeChangeTo": "Wife of",
        "Rationale": "Celin would discreetly inform Alex given their close relationship."
      }
    ]
    """
    messages = json.loads(messages_json)
    updated_map, changes = update_npc_map_with_messages("2",updated_map, messages, changes)
    messages_json = """
    [
      {
        "intermediatorID": "Alex",
        "RecipientID": "Arthur",
        "intermediatorStatus": "Talking",
        "RecipientStatus": "Listening",
        "intermediatorDialogue": "Why are you speaking ill of Alex? He’s always been kind here.",
        "RecipientDialogue": "I’ve heard things about him that worry me.",
        "ItoR_AttitudeChangeTo": "WTF",
        "ItoR_RelTypeChangeTo": "Distant",
        "Rationale": "Celin values peace and reputation in the village."
      },
      {
        "intermediatorID": "Alex",
        "RecipientID": "Bob",
        "intermediatorStatus": "Talking",
        "RecipientStatus": "Listening",
        "intermediatorDialogue": "Arthur said something troubling about you. Is it true?",
        "RecipientDialogue": "That’s news to me. What exactly did he say?",
        "ItoR_AttitudeChangeTo": "WTF",
        "ItoR_RelTypeChangeTo": "Wife of",
        "Rationale": "Celin would discreetly inform Alex given their close relationship."
      }
    ]
    """
    messages = json.loads(messages_json)
    updated_map, changes = update_npc_map_with_messages("3", updated_map, messages, changes)

    print("Updated NPC Map:", updated_map)
    store_change_history(changes)