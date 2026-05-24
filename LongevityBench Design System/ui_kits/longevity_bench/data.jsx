// Mock data for the dashboard.

const SEED_RUNS = [];

const SEED_RECORDS = [];

function _taskGroupFromLbId(lbId) {
  if (!lbId) return 'Other';
  if (lbId.startsWith('LB-SEN')) return 'Senescence Perturbation';
  if (lbId.startsWith('LB-LIP')) return 'Lipidomics';
  if (lbId.startsWith('LB-MET')) return 'Metabolite Prediction';
  return 'Other';
}

function _normalizeTaskGroup(group) {
  if (!group) return null;
  if (group.startsWith('Lipidomics')) return 'Lipidomics';
  return group;
}

const MODEL_NAMES = {
  longevity_llm:          'L-LLM',
  longevity_llm_thinking: 'L-LLM (think)',
  claude_sonnet:          'Claude S4.5',
  majority_baseline:      'Majority',
  random_baseline:        'Random',
};

const MODEL_COLORS = {
  longevity_llm:          'var(--lb-green-500)',
  longevity_llm_thinking: 'var(--lb-green-700)',
  claude_sonnet:          '#c98b1c',
  majority_baseline:      '#8c948c',
  random_baseline:        '#b3b8b3',
};

async function loadDashboardData() {
  try {
    const resp = await fetch('./public/data.json');
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const d = await resp.json();

    const runs = d.runs.map(r => {
      const scores = r.scores || {};
      return {
        id: r.id,
        lbId: r.lb_id,
        taskName: r.lb_id,
        status: r.status === 'success' ? 'complete' : (r.status || 'complete'),
        model: MODEL_NAMES[r.model] || r.model,
        modelId: r.model,
        n: r.n,
        completed: r.completed,
        errors: r.errors || 0,
        f1: scores.macro_f1 ?? null,
        mae: scores.mae ?? null,
        ci: r.ci_95 || null,
        bal_acc: scores.balanced_accuracy ?? null,
        faithfulness: null,
        started: r.started,
        durationS: r.duration_s || 0,
        think: false,
        spark: Array(7).fill(scores.mean ?? 0).concat([scores.mean ?? 0]),
      };
    });

    const records = d.samples.map((s, i) => {
      const llm = s.cells?.longevity_llm || s.cells?.longevity_llm_thinking || {};
      return {
        row: i,
        lbId: s.lb_id,
        taskGroup: _normalizeTaskGroup(s.metadata?.display_group) || _taskGroupFromLbId(s.lb_id),
        format: s.format || 'regression',
        metric: s.metadata?.metric || 'mae',
        organism: s.metadata?.domain || s.metadata?.organism || '—',
        gene1: s.metadata?.gene_1 || s.metadata?.gene1 || s.metadata?.gene || '—',
        gene2: s.metadata?.gene_2 || s.metadata?.gene2 || '—',
        gold: s.gold,
        pred: llm.pred,
        match: llm.pass,
        latencyS: llm.latency_s,
        tokens: llm.tokens,
        consistent: llm.pass,
        faithfulness: null,
        sourceDb: s.metadata?.source_db || s.metadata?.domain || 'LongeBench',
        sourceId: s.id,
        // real question text from export (falls back to id string)
        question: s.question || null,
        system: s.system || null,
        userMsg: s.question || (s.id + ' · gold: ' + s.gold),
        trace: llm.trace || '',
        cells: s.cells || {},
      };
    });

    return { runs, records, models: d.models, tasks: d.tasks };
  } catch (e) {
    console.warn('data.json load failed, using seed data:', e.message);
    return null;
  }
}

const ENTITY_HIGHLIGHTS = (text) =>
  text
    .replace(/\[GENE\](.+?)\[\/GENE\]/g, '<span class="gene">$1</span>')
    .replace(/\[V\](.+?)\[\/V\]/g, '<span class="verify">$1</span>')
    .replace(/\[F\](.+?)\[\/F\]/g, '<span class="fail">$1</span>');

Object.assign(window, { SEED_RUNS, SEED_RECORDS, ENTITY_HIGHLIGHTS, loadDashboardData, MODEL_NAMES, MODEL_COLORS, _taskGroupFromLbId });
