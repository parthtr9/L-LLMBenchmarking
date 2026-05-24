// CompareView — model comparison driven by real run data.
// Receives `runs` prop from App (populated from public/data.json).

const HorizontalBars = ({ task, models }) => {
  const max = Math.max(...models.map(m => task.scores[m.id] ?? 0), 0.01);
  const llm = task.scores['longevity_llm'];
  const baseline = task.scores['majority_baseline'];
  const delta = llm != null && baseline != null ? llm - baseline : null;

  return (
    <div style={{ padding: '14px 18px 18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <Pill brand>{task.id}</Pill>
          <span style={{ marginLeft: 8, font: '500 14px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>
            {task.name.replace(/_/g, ' ')}
          </span>
        </div>
        {delta != null && (
          <span className="lb-meta" style={{ fontFamily: 'var(--lb-font-mono)' }}>
            L-LLM vs majority:{' '}
            <span style={{ color: delta >= 0 ? 'var(--lb-green-700)' : 'var(--lb-error)', fontWeight: 500 }}>
              {delta >= 0 ? '+' : '−'}{Math.abs(delta).toFixed(3)}
            </span>
          </span>
        )}
      </div>
      {models.map(m => {
        const v = task.scores[m.id];
        if (v == null) return null;
        const ci = task.ci[m.id];
        const pct = (v / max) * 100;
        return (
          <div key={m.id} style={{ display: 'grid', gridTemplateColumns: '110px 1fr 52px', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ font: '500 12px var(--lb-font-sans)', color: 'var(--lb-fg-2)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.name}</span>
            <div style={{ position: 'relative', height: 8, background: 'var(--lb-ink-100)', borderRadius: 4 }}>
              <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${pct}%`, background: m.color, borderRadius: 4 }} />
              {ci && (
                <div style={{
                  position: 'absolute', top: -2,
                  left: `${(ci[0] / max) * 100}%`,
                  width: `${((ci[1] - ci[0]) / max) * 100}%`,
                  height: 12,
                  borderLeft: '1.5px solid ' + m.color,
                  borderRight: '1.5px solid ' + m.color,
                  opacity: 0.7,
                }} />
              )}
            </div>
            <span style={{ font: '500 12px var(--lb-font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--lb-fg-1)', textAlign: 'right' }}>
              {v.toFixed(3)}
            </span>
          </div>
        );
      })}
    </div>
  );
};

const CompareView = ({ runs = [] }) => {
  // ── Derive models from completed runs ──────────────────────────────────────
  const modelMap = {};
  runs.filter(r => r.status === 'complete').forEach(r => {
    if (!modelMap[r.modelId]) {
      modelMap[r.modelId] = {
        id: r.modelId,
        name: r.model,
        color: (MODEL_COLORS || {})[r.modelId] || '#8c948c',
        sub: r.modelId.replace(/_/g, ' '),
      };
    }
  });

  // Order: L-LLM first, then non-baselines, then baselines
  const BASELINE_IDS = ['majority_baseline', 'random_baseline'];
  const models = Object.values(modelMap).sort((a, b) => {
    if (a.id === 'longevity_llm') return -1;
    if (b.id === 'longevity_llm') return 1;
    const aBase = BASELINE_IDS.includes(a.id);
    const bBase = BASELINE_IDS.includes(b.id);
    if (aBase && !bBase) return 1;
    if (!aBase && bBase) return -1;
    return a.name.localeCompare(b.name);
  });

  // ── Derive tasks — best score per model per lbId ──────────────────────────
  const taskMap = {};
  runs.filter(r => r.status === 'complete').forEach(r => {
    if (!taskMap[r.lbId]) {
      taskMap[r.lbId] = { id: r.lbId, name: r.taskName || r.lbId, scores: {}, ci: {} };
    }
    const score = r.spark?.[7] ?? r.f1 ?? r.mae ?? 0;
    const existing = taskMap[r.lbId].scores[r.modelId];
    if (existing == null || score > existing) {
      taskMap[r.lbId].scores[r.modelId] = score;
    }
    if (r.ci) taskMap[r.lbId].ci[r.modelId] = r.ci;
  });
  const tasks = Object.values(taskMap);

  // ── Empty state ────────────────────────────────────────────────────────────
  if (models.length === 0 || tasks.length === 0) {
    return (
      <>
        <div className="page-head">
          <div><h1>Model comparison</h1><div className="sub">No completed runs yet.</div></div>
        </div>
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div className="lb-eyebrow" style={{ marginBottom: 8 }}>No data</div>
          <p className="lb-p" style={{ color: 'var(--lb-fg-3)' }}>
            Run <code>pipeline.py</code> or <code>src.eval.run_inspect</code> then export logs.
          </p>
        </div>
      </>
    );
  }

  // ── Aggregate scores ───────────────────────────────────────────────────────
  const agg = models.map(m => {
    const taskScores = tasks.map(t => t.scores[m.id]).filter(v => v != null);
    const avg = taskScores.length > 0 ? taskScores.reduce((s, v) => s + v, 0) / taskScores.length : null;
    const wins = tasks.filter(t => {
      if (t.scores[m.id] == null) return false;
      const best = Math.max(...Object.values(t.scores).filter(v => v != null));
      return t.scores[m.id] >= best;
    }).length;
    return { ...m, avg, wins, nTasks: taskScores.length };
  });

  // ── Best non-baseline for key-findings callout ─────────────────────────────
  const nonBaselines = agg.filter(m => !BASELINE_IDS.includes(m.id) && m.avg != null);
  const best = nonBaselines.reduce((a, b) => (a.avg ?? 0) >= (b.avg ?? 0) ? a : b, nonBaselines[0]);
  const second = nonBaselines.filter(m => m.id !== best?.id)[0];

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Live results · built from outputs/inspect/</div>
          <h1>Model comparison</h1>
          <div className="sub">
            {models.length} models · {tasks.length} task{tasks.length !== 1 ? 's' : ''} · score = normalised mean (higher is better)
          </div>
        </div>
      </div>

      {/* Aggregate metric cards */}
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${Math.min(models.length, 4)}, 1fr)`, gap: 14, marginBottom: 22 }}>
        {agg.map(m => (
          <div key={m.id} className="metric">
            <div className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, background: m.color, borderRadius: 2, display: 'inline-block' }} />
              {m.name}
            </div>
            <div className="val">{m.avg != null ? m.avg.toFixed(3) : '—'}</div>
            <div className="sub">{m.sub} · {m.wins}/{tasks.length} task wins</div>
          </div>
        ))}
      </div>

      {/* Key findings */}
      {best && second && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="head"><h3>Key findings</h3></div>
          <div style={{ padding: '14px 20px 18px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <div style={{ padding: 14, background: 'var(--lb-success-bg)', borderRadius: 6, border: '1px solid #c1e0b9' }}>
              <div className="lb-eyebrow" style={{ color: 'var(--lb-green-700)', marginBottom: 6 }}>Best model</div>
              <p style={{ margin: 0, font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', lineHeight: 1.55 }}>
                <strong>{best.name}</strong> leads with avg score <strong>{best.avg.toFixed(3)}</strong> across {best.nTasks} task{best.nTasks !== 1 ? 's' : ''}.
              </p>
            </div>
            <div style={{ padding: 14, background: 'var(--lb-info-bg)', borderRadius: 6, border: '1px solid #b8cef0' }}>
              <div className="lb-eyebrow" style={{ color: '#1b4a8c', marginBottom: 6 }}>Gap to next</div>
              <p style={{ margin: 0, font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', lineHeight: 1.55 }}>
                <strong>{best.name}</strong> vs <strong>{second.name}</strong>:{' '}
                <strong>{(best.avg - second.avg >= 0 ? '+' : '')}{(best.avg - second.avg).toFixed(3)}</strong> avg score difference.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Per-task bar charts */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="head">
          <h3>Per-task scores</h3>
          <p className="sub">95% CI shown where available · score normalised to [0,1]</p>
        </div>
        <div style={{
          display: 'grid',
          gridTemplateColumns: tasks.length === 1 ? '1fr' : '1fr 1fr',
          gap: 0,
          borderTop: '1px solid var(--lb-border)',
        }}>
          {tasks.map((t, i) => (
            <div key={t.id} style={{
              borderRight: tasks.length > 1 && i % 2 === 0 ? '1px solid var(--lb-border)' : 'none',
              borderBottom: i < tasks.length - (tasks.length % 2 === 0 ? 2 : 1) ? '1px solid var(--lb-border)' : 'none',
            }}>
              <HorizontalBars task={t} models={models} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

Object.assign(window, { CompareView });
