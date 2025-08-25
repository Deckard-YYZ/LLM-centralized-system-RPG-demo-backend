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


def update_npc_map_with_messages(event, npc_map, messages, changes):
    """
    Applies a sequence of JSON messages to update NPC relations,
    capturing original and new values for each change.
    Returns the updated map and a list of change records.
    """
    for msg in messages:
        if 'intermediatorID' in msg and 'RecipientID' in msg:
            src = msg['intermediatorID']
            tgt = msg['RecipientID']
            new_att = msg.get('ItoR_AttitudeChangeTo')
            new_rel = msg.get('ItoR_RelTypeChangeTo')
            dialog_i = msg.get('intermediatorDialogue')
            dialog_r = msg.get('RecipientDialogue')
            rationale = msg.get('Rationale')

            # Record originals
            if src in npc_map and tgt in npc_map[src]:
                orig_att = npc_map[src][tgt].get('Attitude')
                orig_rel = npc_map[src][tgt].get('relation')
            else:
                orig_att, orig_rel = None, None
                npc_map.setdefault(src, {})[tgt] = {}

            # Update map
            npc_map[src][tgt]['Attitude'] = new_att
            npc_map[src][tgt]['relation'] = new_rel

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
    with open("npc_viewer.html", "w", encoding="utf-8") as f:
        f.write('''
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <title>NPC Relationship Change Viewer</title>
      <style>
        body { font-family: sans-serif; padding: 20px; }
        .tag { display: inline-block; background: #eee; padding: 5px 10px; margin: 5px; cursor: pointer; border-radius: 3px; }
        .tag.selected { background: #007bff; color: #fff; }
        #pair-select { margin: 15px 0; }
        .event { border: 1px solid #ccc; padding: 10px; margin: 10px 0; border-radius: 5px; }
        .arrow { font-size: 18px; margin: 0 5px; }
      </style>
    </head>
    <body>
      <h2>NPC Relationship Change Viewer</h2>
      <div id="tags"></div>
      <div id="pair-select" style="display:none;">
        <label>
          Select Other NPC:
          <select id="target-select"><option value="">--</option></select>
        </label>
      </div>
      <div id="events"></div>
      <script>
        // Injected changes from Python
        const changes = 
    ''')
        # dump actual data
        json.dump(changes, f, indent=2, ensure_ascii=False)
        f.write(';\n')
        # copy rest of HTML/JS
        f.write('''
        // (JS code for rendering, same as before)
        // ... (copy from the previous HTML after "const changes = ...;" )
        // Build list of unique NPC names
        const names = Array.from(new Set(changes.map(c => c.source))).sort();

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
    // highlight
    document.querySelectorAll('.tag').forEach(t => t.classList.remove('selected'));
    btn.classList.add('selected');
    source = n;
    // Only include targets with at least one event involving (source, target)
    const possibleTargets = Array.from(new Set(
      changes
        .filter(c => c.source === source)
        .map(c => c.target)
    ));
    targetSelect.innerHTML = '';  // Remove the "--"
    possibleTargets.forEach((x, i) => {
      const opt = document.createElement('option');
      opt.value = x; opt.textContent = x;
      targetSelect.appendChild(opt);
    });
    // Automatically select the first target if available and display events
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

// When other NPC chosen
targetSelect.onchange = () => {
  target = targetSelect.value;
  renderEvents();
};

function renderEvents() {
  eventsDiv.innerHTML = '';
  if (!source || !target) return;

  // Only show events where selected source initiated a change toward target
  const pairEvents = changes
    .filter(c => c.source === source && c.target === target);

  if (pairEvents.length === 0) {
    eventsDiv.textContent = `No changes recorded between ${source} and ${target}.`;
    return;
  }

  // Render each event
  pairEvents.forEach((c, i) => {
    const div = document.createElement('div');
    div.className = 'event';
    div.innerHTML = `
      <strong>${c.event ? c.event : `Event ${i + 1}`}</strong><br>
      <span>${c.source} → ${c.target}</span>
      <span class="arrow">:</span>
      <em>${c.originalAttitude} → ${c.newAttitude}</em>,
      <em>${c.originalRelation} → ${c.newRelation}</em>
      <p><strong>I:</strong> ${c.intermediatorDialogue}</p>
      <p><strong>R:</strong> ${c.RecipientDialogue}</p>
      <p><strong>Reason:</strong> ${c.Rationale}</p>
    `;
    eventsDiv.appendChild(div);
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