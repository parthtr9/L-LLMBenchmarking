// AnswersView — per-sample comparison table across all evaluated models.
// Shows gold answer vs each model's prediction for every record.

const AnswersView = ({ records, onOpenRecord }) => {
  const [fmtFilter, setFmtFilter] = React.useState('all');
  const [taskFilter, setTaskFilter] = React.useState('all');

  if (!records || records.length === 0) {
    return (
      <>
        <div className="page-head"><div><h1>Answers</h1><div className="sub">No records loaded.</div></div></div>
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div className="lb-eyebrow" style={{ marginBottom: 8 }}>No data</div>
          <p className="lb-p" style={{ color: 'var(--lb-fg-3)' }}>Run an eval then export logs to see per-sample answers.</p>
        </div>
      </>
    );
  }

  // Derive unique models from cells across all records
  const allModelIds = [...new Set(records.flatMap(r => Object.keys(r.cells || {})))];
  // Order: L-LLM first, baselines last
  const BASELINE_IDS = ['majority_baseline', 'random_baseline'];
  const modelIds = allModelIds.sort((a, b) => {
    if (a === 'longevity_llm') return -1;
    if (b === 'longevity_llm') return 1;
    if (a === 'longevity_llm_thinking') return -1;
    if (b === 'longevity_llm_thinking') return 1;
    const aBase = BASELINE_IDS.includes(a);
    const bBase = BASELINE_IDS.includes(b);
    if (aBase && !bBase) return 1;
    if (!aBase && bBase) return -1;
    return a.localeCompare(b);
  });

  const formats = ['all', ...new Set(records.map(r => r.format).filter(Boolean))];
  const tasks = ['all', ...new Set(records.map(r => {
    // group by task prefix (LB-SEN, LB-0038, etc.)
    const lb = r.lbId || '';
    if (lb.startsWith('LB-SEN')) return 'Senescence';
    if (lb.startsWith('LB-0')) return lb.split('-').slice(0, 2).join('-');
    return lb || 'Unknown';
  }).filter(Boolean))];

  const filtered = records.filter(r => {
    if (fmtFilter !== 'all' && r.format !== fmtFilter) return false;
    if (taskFilter !== 'all') {
      const lb = r.lbId || '';
      const group = lb.startsWith('LB-SEN') ? 'Senescence' : (lb.startsWith('LB-0') ? lb.split('-').slice(0, 2).join('-') : lb);
      if (group !== taskFilter) return false;
    }
    return true;
  });

  // Compute per-model accuracy on filtered set
  const modelStats = {};
  modelIds.forEach(mid => {
    const cells = filtered.map(r => r.cells?.[mid]).filter(Boolean);
    const total = cells.length;
    const correct = cells.filter(c => c.pass).length;
    const avgScore = total > 0 ? cells.reduce((s, c) => s + (c.score ?? 0), 0) / total : null;
    modelStats[mid] = { total, correct, avgScore };
  });

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Per-sample · all models</div>
          <h1>Answers</h1>
          <div className="sub">{filtered.length} records · {modelIds.length} models · click row to inspect</div>
        </div>
        <div className="actions" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className="lb-meta" style={{ marginRight: 4 }}>Task:</span>
          {tasks.map(t => (
            <button key={t} onClick={() => setTaskFilter(t)}
              style={{ padding: '4px 10px', borderRadius: 4, border: '1px solid var(--lb-border)', background: taskFilter === t ? 'var(--lb-green-500)' : 'var(--lb-bg-2)', color: taskFilter === t ? '#fff' : 'var(--lb-fg-2)', font: '500 12px var(--lb-font-sans)', cursor: 'pointer' }}>
              {t}
            </button>
          ))}
          <span className="lb-meta" style={{ marginLeft: 8, marginRight: 4 }}>Format:</span>
          {formats.map(f => (
            <button key={f} onClick={() => setFmtFilter(f)}
              style={{ padding: '4px 10px', borderRadius: 4, border: '1px solid var(--lb-border)', background: fmtFilter === f ? 'var(--lb-green-500)' : 'var(--lb-bg-2)', color: fmtFilter === f ? '#fff' : 'var(--lb-fg-2)', font: '500 12px var(--lb-font-sans)', cursor: 'pointer' }}>
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Per-model accuracy summary cards */}
      {modelIds.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(modelIds.length, 4)}, 1fr)`, gap: 14, marginBottom: 20 }}>
          {modelIds.map(mid => {
            const s = modelStats[mid];
            const color = (MODEL_COLORS || {})[mid] || '#8c948c';
            const name = (MODEL_NAMES || {})[mid] || mid;
            const acc = s.total > 0 ? (s.correct / s.total) : null;
            return (
              <div key={mid} className="metric">
                <div className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 10, height: 10, background: color, borderRadius: 2, display: 'inline-block' }} />
                  {name}
                </div>
                <div className="val">{s.avgScore != null ? s.avgScore.toFixed(3) : '—'}</div>
                <div className="sub">
                  {acc != null ? `${(acc * 100).toFixed(0)}% match` : 'no data'} · {s.total} samples
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Comparison table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="head">
          <h3>Sample answers</h3>
          <p className="sub">✓ correct · ✗ wrong · — not evaluated</p>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table className="lb" style={{ minWidth: 700 }}>
            <thead>
              <tr>
                <th style={{ width: 36 }}>#</th>
                <th>Task ID</th>
                <th>Fmt</th>
                <th>Gold</th>
                {modelIds.map(mid => (
                  <th key={mid} style={{ textAlign: 'center', minWidth: 80 }}>
                    <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4 }}>
                      <span style={{ width: 8, height: 8, borderRadius: 2, background: (MODEL_COLORS || {})[mid] || '#8c948c', flexShrink: 0 }} />
                      {(MODEL_NAMES || {})[mid] || mid}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.row} onClick={() => onOpenRecord(r)} style={{ cursor: 'pointer' }}>
                  <td className="id">{String(r.row).padStart(3, '0')}</td>
                  <td style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11 }}>{r.lbId || '—'}</td>
                  <td><span className="badge neutral">{r.format}</span></td>
                  <td className="mono" style={{ fontWeight: 600, color: 'var(--lb-green-700)' }}>{r.gold}</td>
                  {modelIds.map(mid => {
                    const c = r.cells?.[mid];
                    if (!c) return <td key={mid} style={{ textAlign: 'center', color: 'var(--lb-fg-4)' }}>—</td>;
                    const pred = c.pred || '';
                    // For short answers (A/B/C/yes/no/number) show as-is; truncate verbose ones
                    const predShort = pred.length <= 12 ? pred : pred.slice(0, 12) + '…';
                    const color = c.pass ? 'var(--lb-green-700)' : 'var(--lb-error)';
                    return (
                      <td key={mid} style={{ textAlign: 'center' }}>
                        <span className="mono" style={{ fontSize: 12, color, fontWeight: 500 }} title={pred}>
                          {c.pass != null ? (c.pass ? '✓ ' : '✗ ') : ''}{predShort}
                        </span>
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

Object.assign(window, { AnswersView });
