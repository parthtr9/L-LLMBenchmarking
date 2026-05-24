// RunDetail — dynamic view for a single completed run.
// Shows actual scores, format breakdown, and per-sample log for this model only.

const RunScoreBar = ({ run, records }) => {
  // Per-format accuracy for this specific model from actual records
  const formats = ['mcq', 'binary', 'pairwise', 'regression'];
  const fmtStats = [];
  formats.forEach(fmt => {
    const fmtRecs = records.filter(r => r.format === fmt && r.cells?.[run.modelId]);
    if (fmtRecs.length === 0) return;
    const cells = fmtRecs.map(r => r.cells[run.modelId]);
    const scored = cells.filter(c => c.score != null);
    if (scored.length === 0) return;
    const avg = scored.reduce((s, c) => s + c.score, 0) / scored.length;
    const nPass = cells.filter(c => c.pass).length;
    fmtStats.push({ fmt, avg, n: fmtRecs.length, nPass });
  });

  if (fmtStats.length === 0) return null;

  const labels = { mcq: 'MCQ', binary: 'Binary', pairwise: 'Pairwise', regression: 'Regression' };
  const modelColor = (MODEL_COLORS || {})[run.modelId] || '#8c948c';

  return (
    <div className="card" style={{ marginBottom: 22 }}>
      <div className="head">
        <h3>Score by format</h3>
        <p className="sub">{run.model} · actual results from exported logs</p>
      </div>
      <div className="barchart">
        {fmtStats.map(({ fmt, avg, n, nPass }) => (
          <div className="row" key={fmt}>
            <span className="lbl">{labels[fmt] || fmt} <span style={{ color: 'var(--lb-fg-4)', fontWeight: 400 }}>n={n}</span></span>
            <div className="track">
              <div className="fill" style={{ width: `${avg * 100}%`, background: modelColor }} />
            </div>
            <span className="val">{avg.toFixed(3)}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

const RunDetail = ({ run, records, onOpenRecord }) => {
  // Records for THIS run's model only
  const modelRecords = records.filter(r => r.cells?.[run.modelId]);

  // Format-level summary
  const fmtCounts = {};
  modelRecords.forEach(r => {
    fmtCounts[r.format] = (fmtCounts[r.format] || 0) + 1;
  });
  const fmtSummary = Object.entries(fmtCounts)
    .map(([f, n]) => `${f} (${n})`)
    .join(' · ');

  // Overall pass rate
  const allCells = modelRecords.map(r => r.cells[run.modelId]).filter(Boolean);
  const nPass = allCells.filter(c => c.pass).length;
  const avgLatency = allCells.filter(c => c.latency_s != null).length > 0
    ? allCells.filter(c => c.latency_s != null).reduce((s, c) => s + c.latency_s, 0) /
      allCells.filter(c => c.latency_s != null).length
    : null;

  const primaryScore = run.f1 ?? run.bal_acc ?? run.mae;
  const primaryLabel = run.f1 != null ? 'Macro F1'
    : run.bal_acc != null ? 'Bal. acc'
    : run.mae != null ? 'MAE' : 'Score';
  const primaryVal = run.f1 != null ? run.f1.toFixed(3)
    : run.bal_acc != null ? run.bal_acc.toFixed(3)
    : run.mae != null ? run.mae.toFixed(3) : '—';

  return (
    <>
      <div className="page-head">
        <div>
          <div style={{ marginBottom: 6 }}>
            <Pill brand>{run.lbId || 'unknown'}</Pill>
            <span style={{ marginLeft: 8 }}><Pill>{(run.taskName || '').replace(/_/g, ' ')}</Pill></span>
          </div>
          <h1>{run.id}</h1>
          <div className="sub">
            {run.model} · {modelRecords.length} records · {fmtSummary} ·
            {' '}started {run.started ? new Date(run.started).toLocaleTimeString() : '—'} ·
            {' '}{run.durationS > 0 ? `${Math.round(run.durationS)}s` : '—'}
          </div>
        </div>
        <div className="actions">
          <Button variant="ghost" icon="download" size="small">summary.json</Button>
        </div>
      </div>

      <div className="metric-grid">
        <MetricCard
          label={primaryLabel}
          value={primaryVal}
          sub={run.ci ? `CI [${run.ci[0]?.toFixed(3)}, ${run.ci[1]?.toFixed(3)}]` : `n=${modelRecords.length}`}
        />
        <MetricCard
          label="Correct"
          value={modelRecords.length > 0 ? `${nPass}/${modelRecords.length}` : '—'}
          sub={modelRecords.length > 0 ? `${(nPass / modelRecords.length * 100).toFixed(1)}% pass rate` : '—'}
        />
        <MetricCard
          label="Avg latency"
          value={avgLatency != null ? avgLatency.toFixed(2) + 's' : '—'}
          sub="per sample"
        />
        <MetricCard
          label="Errors"
          value={run.errors != null ? String(run.errors) : '0'}
          sub={run.status === 'complete' ? 'run complete' : run.status || '—'}
        />
      </div>

      <RunScoreBar run={run} records={records} />

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="head">
          <h3>Sample log</h3>
          <p className="sub">{modelRecords.length} records · click row to inspect</p>
        </div>
        <div style={{ maxHeight: 460, overflow: 'auto' }}>
          <table className="lb">
            <thead>
              <tr>
                <th style={{ width: 36 }}>#</th>
                <th>LB-ID</th>
                <th>Fmt</th>
                <th>Gold</th>
                <th>Pred</th>
                <th style={{ textAlign: 'right' }}>Score</th>
                <th style={{ textAlign: 'right' }}>Latency</th>
                <th style={{ textAlign: 'right' }}>Tokens</th>
              </tr>
            </thead>
            <tbody>
              {modelRecords.map(r => {
                const cell = r.cells[run.modelId] || {};
                const pred = cell.pred || '—';
                const predShort = pred.length <= 14 ? pred : pred.slice(0, 14) + '…';
                const passColor = cell.pass === true ? 'var(--lb-green-700)'
                  : cell.pass === false ? 'var(--lb-error)'
                  : 'var(--lb-fg-4)';
                return (
                  <tr key={r.row} onClick={() => onOpenRecord(r)} style={{ cursor: 'pointer' }}>
                    <td className="id">{String(r.row).padStart(3, '0')}</td>
                    <td style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11 }}>{r.lbId || '—'}</td>
                    <td><span className="badge neutral">{r.format}</span></td>
                    <td className="mono" style={{ fontWeight: 600, color: 'var(--lb-green-700)' }}>{r.gold}</td>
                    <td>
                      <span className="mono" style={{ color: passColor, fontWeight: 500 }} title={pred}>
                        {cell.pass === true ? '✓ ' : cell.pass === false ? '✗ ' : ''}{predShort}
                      </span>
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {cell.score != null ? cell.score.toFixed(3) : '—'}
                    </td>
                    <td className="mono" style={{ textAlign: 'right' }}>
                      {cell.latency_s != null ? cell.latency_s.toFixed(2) + 's' : '—'}
                    </td>
                    <td className="mono" style={{ textAlign: 'right', color: 'var(--lb-fg-4)' }}>
                      {cell.tokens != null ? cell.tokens : '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
};

Object.assign(window, { RunDetail });
