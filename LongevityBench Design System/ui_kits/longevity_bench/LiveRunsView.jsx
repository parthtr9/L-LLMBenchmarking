// LiveRunsView — in-flight runs at top, completed runs with actual stats below.

const InFlightCard = ({ run, onOpenRun }) => {
  const pct = run.n > 0 ? (run.completed / run.n) * 100 : 0;
  const avgS = run.durationS / Math.max(1, run.completed);
  const eta = Math.round(avgS * (run.n - run.completed));
  return (
    <div className="card" style={{ borderColor: 'var(--lb-green-300)', background: 'linear-gradient(180deg, var(--lb-green-50) 0%, #fff 60%)' }}>
      <div style={{ padding: '14px 20px 6px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <Badge kind="info" pulse>Running</Badge>
          <span style={{ marginLeft: 10, font: '500 14px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>{run.id}</span>
        </div>
        <Button variant="ghost" size="small" icon="stop">Cancel</Button>
      </div>
      <div style={{ padding: '6px 20px 16px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr) 2fr', gap: 16, alignItems: 'end' }}>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Task</div>
          <Pill brand>{run.lbId}</Pill>
        </div>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Model</div>
          <div style={{ font: '500 14px var(--lb-font-mono)', color: 'var(--lb-fg-1)' }}>{run.model}</div>
        </div>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Avg latency</div>
          <div style={{ font: '500 14px var(--lb-font-mono)', color: 'var(--lb-fg-1)' }}>{avgS.toFixed(1)}s</div>
        </div>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>ETA</div>
          <div style={{ font: '500 14px var(--lb-font-mono)', color: 'var(--lb-fg-1)' }}>
            {Math.floor(eta / 60)}m {eta % 60}s
          </div>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="lb-eyebrow">Progress</span>
            <span style={{ font: '500 12px var(--lb-font-mono)', color: 'var(--lb-fg-1)' }}>
              {run.completed} / {run.n} · {pct.toFixed(0)}%
            </span>
          </div>
          <div style={{ height: 8, background: '#fff', border: '1px solid var(--lb-border)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: 'var(--lb-green-500)', borderRadius: 4, transition: 'width 600ms ease' }} />
          </div>
        </div>
      </div>
    </div>
  );
};

const CompletedRow = ({ run, records, onClick }) => {
  // Derive actual stats from exported records for this model
  const modelCells = records
    .filter(r => r.cells?.[run.modelId])
    .map(r => r.cells[run.modelId]);

  const nSamples = modelCells.length;
  const nPass = modelCells.filter(c => c.pass).length;
  const scored = modelCells.filter(c => c.score != null);
  const avgScore = scored.length > 0
    ? scored.reduce((s, c) => s + c.score, 0) / scored.length
    : null;

  const primaryScore = avgScore ?? run.f1 ?? run.mae;
  const scoreDisplay = primaryScore != null
    ? <span className="num">{primaryScore.toFixed(3)}</span>
    : <span className="num" style={{ color: 'var(--lb-fg-4)' }}>—</span>;

  const modelColor = (MODEL_COLORS || {})[run.modelId] || '#8c948c';
  const passRate = nSamples > 0 ? nPass / nSamples : null;

  return (
    <div className="run-row" onClick={() => onClick(run)} style={{ cursor: 'pointer' }}>
      <Icon
        name={run.status === 'failed' ? 'alert' : 'check'}
        size={14}
        style={{ color: run.status === 'failed' ? 'var(--lb-error)' : 'var(--lb-green-600)' }}
      />
      <div>
        <div className="title">{(run.taskName || '').replace(/_/g, ' ')}</div>
        <div className="sub" style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 10 }}>{run.id}</div>
      </div>
      <div>
        <Pill brand>{run.lbId || '—'}</Pill>
        <div className="sub" style={{ marginTop: 4 }}>
          {nSamples > 0
            ? `${nPass}/${nSamples} correct · ${(passRate * 100).toFixed(0)}%`
            : `n=${run.n || '?'}`}
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <i style={{ width: 8, height: 8, borderRadius: 2, background: modelColor, display: 'inline-block' }} />
        <span style={{ font: '500 13px var(--lb-font-sans)', color: modelColor }}>{run.model}</span>
      </div>
      <div>
        {run.status === 'failed'
          ? <Badge kind="err">Failed · {run.errors} err</Badge>
          : <Badge kind="pass">Complete</Badge>}
      </div>
      {scoreDisplay}
      <Sparkline values={run.spark} color={modelColor} />
    </div>
  );
};

const LiveRunsView = ({ runs, records = [], onOpenRun }) => {
  const live = runs.filter(r => r.status === 'running');
  const done = runs.filter(r => r.status !== 'running');

  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Live monitoring</div>
          <h1>Runs</h1>
          <div className="sub">
            {live.length} in flight · {done.filter(r => r.status === 'complete').length} complete
          </div>
        </div>
        <div className="actions">
          <Button variant="ghost" icon="download" size="small">Export CSV</Button>
        </div>
      </div>

      {live.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 22 }}>
          {live.map(r => <InFlightCard key={r.id} run={r} onOpenRun={onOpenRun} />)}
        </div>
      )}

      {live.length === 0 && (
        <div className="card" style={{ padding: '14px 20px', marginBottom: 18, display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ font: '400 12px var(--lb-font-sans)', color: 'var(--lb-fg-4)' }}>
            No runs in progress. Start one with <strong>+ New Run</strong> or run{' '}
            <code style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11, background: 'var(--lb-bg-2)', padding: '1px 5px', borderRadius: 3 }}>
              pipeline.py
            </code>
            {' '}then re-export logs.
          </span>
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="head">
          <h3>Completed runs</h3>
          <p className="sub">{done.length} runs · click to inspect samples</p>
          <div className="right">
            <Badge kind="pass">{done.filter(r => r.status === 'complete').length} complete</Badge>
            {done.filter(r => r.status === 'failed').length > 0 && (
              <Badge kind="err">{done.filter(r => r.status === 'failed').length} failed</Badge>
            )}
          </div>
        </div>
        <div>
          {done.length === 0 ? (
            <div style={{ padding: '32px 20px', textAlign: 'center', color: 'var(--lb-fg-4)', font: '400 13px var(--lb-font-sans)' }}>
              No completed runs yet.
            </div>
          ) : (
            done.map(r => (
              <CompletedRow key={r.id} run={r} records={records} onClick={onOpenRun} />
            ))
          )}
        </div>
      </div>
    </>
  );
};

Object.assign(window, { LiveRunsView });
