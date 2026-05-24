// ResultsMatrix — data-driven from records prop (populated from data.json).
// Rows = benchmark samples, columns = models from cells, cells = pass/fail + pred.

const MODEL_ORDER = ['longevity_llm', 'claude_sonnet', 'majority_baseline', 'random_baseline'];
const BASELINE_IDS_MAT = new Set(['majority_baseline', 'random_baseline']);

const ResultsMatrix = ({ records = [], onOpenRecord }) => {
  const [filter, setFilter] = React.useState('all');
  const [sortBy, setSortBy] = React.useState(null);

  // Derive model list from all records' cells
  const modelIdSet = new Set();
  records.forEach(r => Object.keys(r.cells || {}).forEach(id => modelIdSet.add(id)));
  const modelIds = MODEL_ORDER.filter(id => modelIdSet.has(id))
    .concat([...modelIdSet].filter(id => !MODEL_ORDER.includes(id)));
  const models = modelIds.map(id => ({
    id,
    name: (MODEL_NAMES || {})[id] || id,
    color: (MODEL_COLORS || {})[id] || '#8c948c',
  }));

  // Filter
  let rows = records;
  if (filter === 'fails') {
    rows = rows.filter(r => models.some(m => {
      const c = r.cells[m.id];
      return c && !(c.pass === true || (c.score != null && c.score >= 0.5));
    }));
  } else if (filter === 'llm-wins') {
    rows = rows.filter(r => {
      const llm = r.cells['longevity_llm'];
      if (!llm || !(llm.pass === true || llm.score >= 0.5)) return false;
      return models.some(m => !BASELINE_IDS_MAT.has(m.id) && m.id !== 'longevity_llm' && r.cells[m.id] && !(r.cells[m.id].pass === true || r.cells[m.id].score >= 0.5));
    });
  } else if (filter === 'llm-fails') {
    rows = rows.filter(r => {
      const llm = r.cells['longevity_llm'];
      return llm && !(llm.pass === true || (llm.score != null && llm.score >= 0.5));
    });
  }

  // Sort
  if (sortBy) {
    rows = [...rows].sort((a, b) => (b.cells[sortBy]?.score ?? 0) - (a.cells[sortBy]?.score ?? 0));
  }

  // Summary stats
  const passCounts = models.map(m => {
    const withModel = records.filter(r => r.cells[m.id] != null);
    const passes = withModel.filter(r => {
      const c = r.cells[m.id];
      return c.pass === true || (c.score != null && c.score >= 0.5);
    }).length;
    const scores = withModel.map(r => r.cells[m.id]?.score).filter(v => v != null);
    const avg = scores.length > 0 ? scores.reduce((s, v) => s + v, 0) / scores.length : 0;
    return { ...m, passes, total: withModel.length, avg };
  });

  const handleCellClick = (r, m, c) => {
    if (!onOpenRecord) return;
    onOpenRecord({
      ...r,
      pred: c.pred,
      match: c.pass === true || (c.score != null && c.score >= 0.5),
      latencyS: c.latency_s,
      tokens: c.tokens,
      trace: c.trace || '',
    });
  };

  if (!records.length) {
    return (
      <>
        <div className="page-head">
          <div>
            <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Results matrix · per-sample × per-model</div>
            <h1>Eval matrix</h1>
            <div className="sub">No data yet.</div>
          </div>
        </div>
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div className="lb-eyebrow" style={{ marginBottom: 8 }}>No data</div>
          <p className="lb-p" style={{ color: 'var(--lb-fg-3)' }}>
            Run <code>pipeline.py</code> then export logs to generate data.json.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Results matrix · per-sample × per-model</div>
          <h1>Eval matrix</h1>
          <div className="sub">
            {rows.length}/{records.length} samples × {models.length} models · click cell to inspect
          </div>
        </div>
        <div className="actions">
          <Button variant="ghost" size="small" icon="download">Export CSV</Button>
        </div>
      </div>

      {/* Filter bar + pass/fail summary */}
      <div className="card" style={{ marginBottom: 16, padding: '12px 18px', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ font: '500 12px var(--lb-font-sans)', color: 'var(--lb-fg-3)' }}>Filter</div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            ['all', 'All'],
            ['fails', 'Has failures'],
            ['llm-wins', 'L-LLM wins'],
            ['llm-fails', 'L-LLM fails'],
          ].map(([f, label]) => (
            <button key={f} onClick={() => setFilter(f)}
                    className={'btn small ' + (filter === f ? 'primary' : 'ghost')}>
              {label}
            </button>
          ))}
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 14, font: '400 12px var(--lb-font-mono)', color: 'var(--lb-fg-3)', flexWrap: 'wrap' }}>
          {passCounts.map(p => (
            <span key={p.id}>
              <span style={{ display: 'inline-block', width: 8, height: 8, background: p.color, borderRadius: 2, marginRight: 5 }} />
              {p.name}: <span style={{ color: 'var(--lb-fg-1)', fontWeight: 500 }}>{p.passes}/{p.total}</span>
            </span>
          ))}
        </div>
      </div>

      {/* Matrix table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ overflowX: 'auto' }}>
          <table className="lb matrix" style={{ minWidth: Math.max(780, 320 + models.length * 140) }}>
            <thead>
              <tr>
                <th style={{ position: 'sticky', left: 0, zIndex: 2, background: 'var(--lb-ink-50)', minWidth: 240 }}>Sample</th>
                <th style={{ minWidth: 80 }}>Format</th>
                <th style={{ minWidth: 80 }}>Gold</th>
                {models.map(m => {
                  const pc = passCounts.find(p => p.id === m.id);
                  return (
                    <th key={m.id}
                        onClick={() => setSortBy(sortBy === m.id ? null : m.id)}
                        style={{ minWidth: 130, cursor: 'pointer', textAlign: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6 }}>
                        <span style={{ width: 8, height: 8, background: m.color, borderRadius: 2, display: 'inline-block' }} />
                        <span>{m.name}</span>
                        {sortBy === m.id && <span style={{ color: 'var(--lb-green-600)' }}>↓</span>}
                      </div>
                      <div style={{ font: '400 10px var(--lb-font-mono)', color: 'var(--lb-fg-4)', textTransform: 'none', letterSpacing: 'normal', marginTop: 2 }}>
                        {pc ? pc.avg.toFixed(2) + ' avg' : '—'}
                      </div>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.sourceId || r.row}>
                  <td style={{ position: 'sticky', left: 0, zIndex: 1, background: '#fff', borderRight: '1px solid var(--lb-border)' }}>
                    <div style={{ font: '500 12px var(--lb-font-mono)', color: 'var(--lb-fg-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 220 }}>
                      {r.sourceId}
                    </div>
                    {r.gene1 && r.gene1 !== '—' && (
                      <div style={{ font: '500 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', marginTop: 2 }}>{r.gene1}</div>
                    )}
                    <div style={{ font: '400 11px var(--lb-font-mono)', color: 'var(--lb-fg-4)', marginTop: 2 }}>{r.metric}</div>
                  </td>
                  <td className="mono" style={{ background: '#fff' }}>{r.format}</td>
                  <td className="mono" style={{ background: '#fff' }}>{r.gold}</td>
                  {models.map(m => {
                    const c = r.cells[m.id];
                    if (!c) {
                      return (
                        <td key={m.id} style={{ background: 'var(--lb-ink-50)', padding: 0, borderRight: '1px solid var(--lb-border)' }}>
                          <div style={{ padding: '8px 10px', minHeight: 44, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                            <span style={{ font: '400 11px var(--lb-font-mono)', color: 'var(--lb-fg-4)' }}>—</span>
                          </div>
                        </td>
                      );
                    }
                    const pass = c.pass === true || (c.score != null && c.score >= 0.5);
                    const bg = pass ? 'var(--lb-success-bg)' : 'var(--lb-error-bg)';
                    const fg = pass ? 'var(--lb-green-700)' : '#8a2419';
                    return (
                      <td key={m.id}
                          onClick={() => handleCellClick(r, m, c)}
                          style={{ background: bg, padding: 0, cursor: 'pointer', borderRight: '1px solid var(--lb-border)' }}>
                        <div style={{ padding: '8px 10px', display: 'flex', flexDirection: 'column', gap: 4, minHeight: 44 }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                            <span style={{ font: '500 11px var(--lb-font-sans)', color: fg }}>
                              {pass ? '✓ pass' : '✗ fail'}
                            </span>
                            {c.score != null && (
                              <span style={{ font: '500 12px var(--lb-font-mono)', color: fg, fontVariantNumeric: 'tabular-nums' }}>
                                {c.score.toFixed(2)}
                              </span>
                            )}
                          </div>
                          <div style={{ font: '400 11px var(--lb-font-mono)', color: 'var(--lb-fg-3)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 110 }}>
                            {c.pred || '—'}
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

Object.assign(window, { ResultsMatrix });
