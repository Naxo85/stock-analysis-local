const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const context = {
  Session: { getScriptTimeZone() { return 'Europe/Madrid'; } },
  Utilities: {
    formatDate(value) {
      return new Date(value).toISOString().slice(0, 10);
    },
  },
};

vm.createContext(context);
const source = fs.readFileSync(
  path.join(__dirname, '..', 'apps_script', 'update_targets_and_notes.gs'),
  'utf8'
);
vm.runInContext(source, context);
assert.doesNotMatch(source, /const updateCell = profileName/);
assert.doesNotMatch(source, /setValue\(\$\{updateLabel\}/);

const up = context.targetUpdateScorePresentation_(
  { changes: { previous_score: 6.0 } },
  6.5
);
assert.strictEqual(up.background, '#d9ead3');
assert.match(up.note, /6,0 → 6,5/);
assert.match(up.note, /\+0,5/);

const down = context.targetUpdateScorePresentation_(
  { changes: { previous_score: 7.4 } },
  6.2
);
assert.strictEqual(down.background, '#f4cccc');
assert.match(down.note, /7,4 → 6,2/);
assert.match(down.note, /-1,2/);

const belowThreshold = context.targetUpdateScorePresentation_(
  { changes: { previous_score: 6.0 } },
  6.4
);
assert.strictEqual(belowThreshold.background, null);
assert.strictEqual(belowThreshold.note, '');

const firstScore = context.targetUpdateScorePresentation_({}, 7.0);
assert.strictEqual(firstScore.background, null);
assert.strictEqual(firstScore.note, '');

const retained = context.targetUpdateScorePresentation_(
  {
    generated_at: '2026-09-03T10:00:00Z',
    changes: { previous_score: 7.0 },
    analysis_workflow: {
      status: 'reference_retained_low_confidence',
      followup_generated_at: '2026-09-03T10:00:00Z',
      reference_generated_at: '2026-09-01T10:00:00Z',
      effective_confidence: 50,
    },
  },
  6.0
);
assert.strictEqual(retained.background, '#fff2cc');
assert.match(retained.note, /Se conserva la referencia oficial/);

console.log('Target/note score change presentation tests passed.');
