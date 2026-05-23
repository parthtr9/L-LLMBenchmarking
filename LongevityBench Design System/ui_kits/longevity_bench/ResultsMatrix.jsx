// ResultsMatrix — Promptfoo-style dense results table.
// Rows = LongeBench samples, columns = models, cells = pass/fail + score.

const MATRIX_MODELS = [
  { id: 'longevity_llm', name: 'L-LLM',        color: 'var(--lb-green-500)' },
  { id: 'gemini_flash',  name: 'Gemini Flash', color: '#1f9bd6' },
  { id: 'deepseek_chat', name: 'DeepSeek',     color: '#6b3fa0' },
  { id: 'claude_sonnet', name: 'Claude S4.5',  color: '#c98b1c' },
  { id: 'majority',      name: 'Majority',     color: '#8c948c' },
];

// Hand-authored sample matrix — kept short and explicit.
// Each row: id, genes, format, gold, cells (one per model).
// Cell: pred, score (0..1), latency_s, tokens.
const MATRIX_ROWS = [
  { id: 'LB-0038_00003', genes: 'daf-2 · age-1',   format: 'ternary',     gold: 'synergistic',
    cells: { longevity_llm: { pred: 'synergistic', score: 0.92, latencyS: 4.2, tokens: 380 },
             gemini_flash:  { pred: 'synergistic', score: 0.88, latencyS: 2.1, tokens: 340 },
             deepseek_chat: { pred: 'additive',    score: 0.35, latencyS: 3.4, tokens: 410 },
             claude_sonnet: { pred: 'synergistic', score: 0.90, latencyS: 3.8, tokens: 360 },
             majority:      { pred: 'synergistic', score: 0.42, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00004', genes: 'clk-1 · isp-1',   format: 'ternary',     gold: 'additive',
    cells: { longevity_llm: { pred: 'synergistic', score: 0.45, latencyS: 6.0, tokens: 510 },
             gemini_flash:  { pred: 'additive',    score: 0.80, latencyS: 2.4, tokens: 290 },
             deepseek_chat: { pred: 'additive',    score: 0.71, latencyS: 3.9, tokens: 380 },
             claude_sonnet: { pred: 'additive',    score: 0.85, latencyS: 4.1, tokens: 320 },
             majority:      { pred: 'synergistic', score: 0.10, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00005', genes: 'FOXO3 · MTOR',    format: 'regression',  gold: '−23.5',
    cells: { longevity_llm: { pred: '−11.2',       score: 0.31, latencyS: 7.9, tokens: 610 },
             gemini_flash:  { pred: '−18.0',       score: 0.62, latencyS: 2.9, tokens: 410 },
             deepseek_chat: { pred: '−9.5',        score: 0.28, latencyS: 4.2, tokens: 480 },
             claude_sonnet: { pred: '−21.4',       score: 0.78, latencyS: 4.6, tokens: 440 },
             majority:      { pred: '0.0',         score: 0.20, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00006', genes: 'Trp53 · Igf1r',   format: 'binary',      gold: 'decreased',
    cells: { longevity_llm: { pred: 'decreased',   score: 0.88, latencyS: 5.1, tokens: 300 },
             gemini_flash:  { pred: 'decreased',   score: 0.84, latencyS: 2.0, tokens: 240 },
             deepseek_chat: { pred: 'decreased',   score: 0.72, latencyS: 3.2, tokens: 310 },
             claude_sonnet: { pred: 'decreased',   score: 0.90, latencyS: 3.5, tokens: 280 },
             majority:      { pred: 'decreased',   score: 0.60, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00007', genes: 'Sirt1 · Atg7',    format: 'ternary',     gold: 'no_change',
    cells: { longevity_llm: { pred: 'no_change',   score: 0.82, latencyS: 5.9, tokens: 410 },
             gemini_flash:  { pred: 'decreased',   score: 0.30, latencyS: 2.3, tokens: 320 },
             deepseek_chat: { pred: 'no_change',   score: 0.66, latencyS: 3.7, tokens: 360 },
             claude_sonnet: { pred: 'no_change',   score: 0.79, latencyS: 4.0, tokens: 340 },
             majority:      { pred: 'decreased',   score: 0.15, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00008', genes: 'eat-2 · rsks-1',  format: 'mcq',         gold: 'B',
    cells: { longevity_llm: { pred: 'B',           score: 0.95, latencyS: 3.8, tokens: 224 },
             gemini_flash:  { pred: 'B',           score: 0.90, latencyS: 1.8, tokens: 190 },
             deepseek_chat: { pred: 'A',           score: 0.25, latencyS: 2.9, tokens: 240 },
             claude_sonnet: { pred: 'B',           score: 0.92, latencyS: 3.2, tokens: 210 },
             majority:      { pred: 'A',           score: 0.25, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00009', genes: 'glp-1 · daf-12',  format: 'ternary',     gold: 'synergistic',
    cells: { longevity_llm: { pred: 'synergistic', score: 0.86, latencyS: 4.6, tokens: 360 },
             gemini_flash:  { pred: 'additive',    score: 0.32, latencyS: 2.1, tokens: 290 },
             deepseek_chat: { pred: 'synergistic', score: 0.74, latencyS: 3.5, tokens: 330 },
             claude_sonnet: { pred: 'synergistic', score: 0.81, latencyS: 3.9, tokens: 300 },
             majority:      { pred: 'synergistic', score: 0.42, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00010', genes: 'hsf-1 · sod-3',   format: 'binary',      gold: 'increased',
    cells: { longevity_llm: { pred: 'increased',   score: 0.88, latencyS: 5.2, tokens: 320 },
             gemini_flash:  { pred: 'increased',   score: 0.83, latencyS: 2.4, tokens: 270 },
             deepseek_chat: { pred: 'increased',   score: 0.71, latencyS: 3.6, tokens: 300 },
             claude_sonnet: { pred: 'increased',   score: 0.87, latencyS: 3.8, tokens: 290 },
             majority:      { pred: 'decreased',   score: 0.40, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00011', genes: 'daf-16 · skn-1',  format: 'ternary',     gold: 'synergistic',
    cells: { longevity_llm: { pred: 'synergistic', score: 0.89, latencyS: 4.4, tokens: 380 },
             gemini_flash:  { pred: 'antagonistic',score: 0.18, latencyS: 2.5, tokens: 310 },
             deepseek_chat: { pred: 'additive',    score: 0.35, latencyS: 3.8, tokens: 350 },
             claude_sonnet: { pred: 'synergistic', score: 0.84, latencyS: 4.2, tokens: 330 },
             majority:      { pred: 'synergistic', score: 0.42, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00012', genes: 'LRRK2 · TP53',    format: 'mcq',         gold: 'C',
    cells: { longevity_llm: { pred: 'D',           score: 0.25, latencyS: 5.0, tokens: 260 },
             gemini_flash:  { pred: 'C',           score: 0.91, latencyS: 1.9, tokens: 220 },
             deepseek_chat: { pred: 'C',           score: 0.80, latencyS: 3.1, tokens: 250 },
             claude_sonnet: { pred: 'C',           score: 0.88, latencyS: 3.4, tokens: 230 },
             majority:      { pred: 'A',           score: 0.25, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00013', genes: 'mTOR · AMPK',     format: 'binary',      gold: 'increased',
    cells: { longevity_llm: { pred: 'increased',   score: 0.86, latencyS: 5.4, tokens: 290 },
             gemini_flash:  { pred: 'increased',   score: 0.79, latencyS: 2.2, tokens: 230 },
             deepseek_chat: { pred: 'decreased',   score: 0.22, latencyS: 3.7, tokens: 260 },
             claude_sonnet: { pred: 'increased',   score: 0.84, latencyS: 3.6, tokens: 240 },
             majority:      { pred: 'decreased',   score: 0.40, latencyS: 0.0, tokens: 0   } } },
  { id: 'LB-0038_00014', genes: 'BRCA1 · ATM',     format: 'ternary',     gold: 'additive',
    cells: { longevity_llm: { pred: 'additive',    score: 0.81, latencyS: 5.7, tokens: 400 },
             gemini_flash:  { pred: 'synergistic', score: 0.28, latencyS: 2.6, tokens: 340 },
             deepseek_chat: { pred: 'additive',    score: 0.69, latencyS: 3.9, tokens: 370 },
             claude_sonnet: { pred: 'additive',    score: 0.85, latencyS: 4.0, tokens: 360 },
             majority:      { pred: 'synergistic', score: 0.10, latencyS: 0.0, tokens: 0   } } },
];

// Tag each cell with pass/partial flags so render-time stays simple.
MATRIX_ROWS.forEach(r => {
  Object.values(r.cells).forEach(c => {
    c.pass = c.score >= 0.6;
    c.partial = !c.pass && c.score >= 0.4;
  });
});

const ResultsMatrix = ({ onOpenRecord }) => {
  const [filter, setFilter] = React.useState('all');
  const [sortBy, setSortBy] = React.useState(null);

  let rows = MATRIX_ROWS;
  if (filter === 'fails') {
    rows = rows.filter(r => Object.values(r.cells).some(c => !c.pass));
  } else if (filter === 'llm-wins') {
    rows = rows.filter(r => r.cells.longevity_llm.pass &&
                           (!r.cells.gemini_flash.pass || !r.cells.claude_sonnet.pass));
  } else if (filter === 'llm-fails') {
    rows = rows.filter(r => !r.cells.longevity_llm.pass);
  }

  if (sortBy) {
    rows = [...rows].sort((a, b) => b.cells[sortBy].score - a.cells[sortBy].score);
  }

  const passCounts = MATRIX_MODELS.map(m => ({
    ...m,
    passes: MATRIX_ROWS.filter(r => r.cells[m.id].pass).length,
    total: MATRIX_ROWS.length,
    avg: MATRIX_ROWS.reduce((s, r) => s + r.cells[m.id].score, 0) / MATRIX_ROWS.length,
  }));

  const handleCellClick = (r, m, c) => {
    if (!onOpenRecord) return;
    onOpenRecord({
      row: parseInt(r.id.split('_')[1], 10),
      lbId: 'LB-0038',
      format: r.format,
      metric: 'macro_f1',
      organism: 'C. elegans',
      gene1: r.genes.split(' · ')[0],
      gene2: r.genes.split(' · ')[1],
      gold: r.gold,
      pred: c.pred,
      match: c.pass,
      latencyS: c.latencyS,
      tokens: c.tokens,
      consistent: c.pass,
      faithfulness: 0.5 + c.score * 0.5,
      sourceDb: 'SynergyAge',
      sourceId: 'SYN-' + r.id.slice(-4),
      userMsg: 'Sample for ' + r.genes + ' — opened from ' + m.name + ' column.',
      trace: '[GENE]' + r.genes.split(' · ')[0] + '[/GENE] interaction with [GENE]' + r.genes.split(' · ')[1] + '[/GENE] · ' + (c.pass ? '[V]direction matches gold[/V]' : '[F]direction conflicts with gold[/F]'),
    });
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Results matrix · per-sample × per-model</div>
          <h1>Eval matrix</h1>
          <div className="sub">{MATRIX_ROWS.length} samples × {MATRIX_MODELS.length} models · click any cell to inspect · reads <code style={{ background: 'transparent', border: 0, padding: 0 }}>outputs/inspect/</code></div>
        </div>
        <div className="actions">
          <Button variant="ghost" size="small" icon="download">Export CSV</Button>
          <Button variant="secondary" size="small" icon="file">Open in Inspect</Button>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 16, padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ font: '500 12px var(--lb-font-sans)', color: 'var(--lb-fg-3)' }}>Filter</div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={() => setFilter('all')} className={'btn small ' + (filter === 'all' ? 'primary' : 'ghost')}>All</button>
          <button onClick={() => setFilter('fails')} className={'btn small ' + (filter === 'fails' ? 'primary' : 'ghost')}>Has failures</button>
          <button onClick={() => setFilter('llm-wins')} className={'btn small ' + (filter === 'llm-wins' ? 'primary' : 'ghost')}>L-LLM wins</button>
          <button onClick={() => setFilter('llm-fails')} className={'btn small ' + (filter === 'llm-fails' ? 'primary' : 'ghost')}>L-LLM fails</button>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 14, font: '400 12px var(--lb-font-mono)', color: 'var(--lb-fg-3)' }}>
          {passCounts.map(p => (
            <span key={p.id}>
              <span style={{ display: 'inline-block', width: 8, height: 8, background: p.color, borderRadius: 2, marginRight: 5 }} />
              {p.name}: <span style={{ color: 'var(--lb-fg-1)', fontWeight: 500 }}>{p.passes}/{p.total}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="lb matrix" style={{ minWidth: 920 }}>
            <thead>
              <tr>
                <th style={{ position: 'sticky', left: 0, zIndex: 2, background: 'var(--lb-ink-50)', minWidth: 220 }}>Sample</th>
                <th style={{ minWidth: 110 }}>Gold</th>
                {MATRIX_MODELS.map(m => {
                  const pc = passCounts.find(p => p.id === m.id);
                  return (
                    <th key={m.id} onClick={() => setSortBy(sortBy === m.id ? null : m.id)}
                        style={{ minWidth: 130, cursor: 'pointer', textAlign: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                        <span style={{ width: 8, height: 8, background: m.color, borderRadius: 2, display: 'inline-block' }} />
                        <span>{m.name}</span>
                        {sortBy === m.id && <span style={{ color: 'var(--lb-green-600)' }}>↓</span>}
                      </div>
                      <div style={{ font: '400 10px var(--lb-font-mono)', color: 'var(--lb-fg-4)', textTransform: 'none', letterSpacing: 'normal', marginTop: 2 }}>
                        {pc.avg.toFixed(2)} avg
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.id}>
                  <td style={{ position: 'sticky', left: 0, zIndex: 1, background: '#fff', borderRight: '1px solid var(--lb-border)' }}>
                    <div style={{ font: '500 12px var(--lb-font-mono)', color: 'var(--lb-fg-3)' }}>{r.id}</div>
                    <div style={{ font: '500 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', marginTop: 2 }}>{r.genes}</div>
                    <div style={{ font: '400 11px var(--lb-font-mono)', color: 'var(--lb-fg-4)', marginTop: 2 }}>{r.format}</div>
                  </td>
                  <td className="mono" style={{ background: '#fff' }}>{r.gold}</td>
                  {MATRIX_MODELS.map(m => {
                    const c = r.cells[m.id];
                    const bg = c.pass ? 'var(--lb-success-bg)' : c.partial ? 'var(--lb-warning-bg)' : 'var(--lb-error-bg)';
                    const fg = c.pass ? 'var(--lb-green-700)' : c.partial ? '#8a5d12' : '#8a2419';
                    return (
                      <td key={m.id}
                          onClick={() => handleCellClick(r, m, c)}
                          style={{ background: bg, padding: 0, cursor: 'pointer', borderRight: '1px solid var(--lb-border)' }}>
                        <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4, minHeight: 44 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                            <span style={{ font: '500 11px var(--lb-font-sans)', color: fg }}>
                              {c.pass ? '✓ pass' : c.partial ? '~ partial' : '✗ fail'}
                            </span>
                            <span style={{ font: '500 12px var(--lb-font-mono)', color: fg, fontVariantNumeric: 'tabular-nums' }}>
                              {c.score.toFixed(2)}
                            </span>
                          </div>
                          <div style={{ font: '400 11px var(--lb-font-mono)', color: 'var(--lb-fg-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {c.pred}
                          </div>
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
};

Object.assign(window, { ResultsMatrix, MATRIX_MODELS, MATRIX_ROWS });
