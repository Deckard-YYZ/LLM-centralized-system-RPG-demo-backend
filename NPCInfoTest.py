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
    Always build (src, tgt) = (intermediatorID, other).
    other := AttAndRelRCPT (new short) | RecipientID (dialog) | starterID (old short)
    Merge fragments per (src,tgt) only (no cross-target merging).
    """
    buckets = {}  # (src, tgt) -> merged record

    for m in messages or []:
        src = m.get('intermediatorID') or m.get('IntermediatorID')
        if not src:
            continue

        # choose target deterministically
        tgt = (m.get('AttAndRelRCPT') or
               m.get('RecipientID') or
               m.get('starterID'))
        if not tgt:
            continue

        key = (src, tgt)
        rec = buckets.setdefault(key, {
            'source': src, 'target': tgt,
            'newAttitude': None, 'newRelation': None,
            'intermediatorDialogue': None, 'RecipientDialogue': None, 'Rationale': None
        })

        # map variants
        new_att = m.get('ItoR_AttitudeChangeTo') or m.get('AttitudeChange')
        new_rel = m.get('ItoR_RelTypeChangeTo') or m.get('RelationshipTypeChange')
        if new_att is not None: rec['newAttitude'] = new_att
        if new_rel is not None: rec['newRelation'] = new_rel

        if 'intermediatorDialogue' in m: rec['intermediatorDialogue'] = m['intermediatorDialogue']
        if 'RecipientDialogue' in m:     rec['RecipientDialogue'] = m['RecipientDialogue']
        if 'Rationale' in m:             rec['Rationale'] = m['Rationale']

    return list(buckets.values())



def update_npc_map_with_messages(event, npc_map, messages, changes):
    npc_map = npc_map or {}
    changes  = changes or []

    for rec in _normalize_change_records(messages):
        src, tgt = rec['source'].capitalize(), rec['target'].capitalize()


        # READ originals using resolved keys
        orig_att = npc_map.get(src, {}).get(tgt, {}).get('Attitude')
        orig_rel = npc_map.get(src, {}).get(tgt, {}).get('relation')

        # ensure path using resolved keys
        npc_map.setdefault(src, {}).setdefault(tgt, {})

        new_att = rec.get('newAttitude')
        new_rel = rec.get('newRelation')
        if new_att is not None: npc_map[src][tgt]['Attitude'] = new_att
        if new_rel is not None: npc_map[src][tgt]['relation'] = new_rel

        if any(v is not None for v in (new_att, new_rel,
                                       rec.get('intermediatorDialogue'),
                                       rec.get('RecipientDialogue'),
                                       rec.get('Rationale'))):
            changes.append({
                'event': event,
                'source': src, 'target': tgt,
                'originalAttitude': orig_att, 'newAttitude': new_att,
                'originalRelation': orig_rel, 'newRelation': new_rel,
                'intermediatorDialogue': rec.get('intermediatorDialogue'),
                'RecipientDialogue': rec.get('RecipientDialogue'),
                'Rationale': rec.get('Rationale')
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
      Select Other Actor:&nbsp;
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

  const pairEvents = changes.filter(c => c.source === source && c.target === target);
  if (pairEvents.length === 0) {
    eventsDiv.textContent = `No changes recorded between ${source} and ${target}.`;
    return;
  }

  pairEvents.forEach((c, i) => {
    const ev = document.createElement('div');
    ev.className = 'event';

    const headline = (c.event && String(c.event)) ? c.event : `Event ${i + 1}`;

    // SHOW ONLY IF A *NEW* VALUE IS PROVIDED
    const hasNewAtt = c.newAttitude !== undefined && c.newAttitude !== null && String(c.newAttitude).trim() !== '';
    const hasNewRel = c.newRelation !== undefined && c.newRelation !== null && String(c.newRelation).trim() !== '';

    // rename label to Relationship
    const attRow = hasNewAtt ? `<div class="kv"><strong>Attitude:</strong> <span>${c.originalAttitude ?? '—'}</span><span class="arrow"> → </span><span>${c.newAttitude}</span></div>` : '';
    const relRow = hasNewRel ? `<div class="kv"><strong>Relationship:</strong> <span>${c.originalRelation ?? '—'}</span><span class="arrow"> → </span><span>${c.newRelation}</span></div>` : '';

    const iDia = (c.intermediatorDialogue ?? '').trim();
    const rDia = (c.RecipientDialogue ?? '').trim();
    const rationale = (c.Rationale ?? '').trim();

    const dialogI = iDia ? `<div class="kv"><strong>I:</strong> ${iDia}</div>` : "";
    const dialogR = rDia ? `<div class="kv"><strong>R:</strong> ${rDia}</div>` : "";
    // show rationale only if present (prevents leaking it to dialogue-only pairs)
    const reason  = rationale ? `<div class="kv"><strong>Reason:</strong> ${rationale}</div>` : "";

    // Chips reflect what’s actually shown
    const chips = [];
    if (hasNewAtt) chips.push(`<span class="chip">Attitude</span>`);
    if (hasNewRel) chips.push(`<span class="chip">Relationship</span>`);
    if (dialogI || dialogR) chips.push(`<span class="chip">Dialogue</span>`);
    if (reason) chips.push(`<span class="chip">Rationale</span>`);

    ev.innerHTML = `
      <div class="row">
        <div><strong>${headline}</strong></div>
        <div class="chip">${c.source}</div>
        <div class="chip">→</div>
        <div class="chip">${c.target}</div>
        ${chips.join('')}
      </div>
      ${attRow}
      ${relRow}
      ${dialogI}
      ${dialogR}
      ${reason}
    `;

    // If nothing to show (e.g., only empty payload), collapse
    if (!attRow && !relRow && !dialogI && !dialogR && !reason) {
      ev.innerHTML = `
        <div class="row">
          <div><strong>${headline}</strong></div>
          <span class="muted">No visible change.</span>
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