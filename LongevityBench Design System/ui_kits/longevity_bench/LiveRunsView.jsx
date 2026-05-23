// LiveRunsView — focused on live monitoring. In-flight runs at top with progress,
// then completed runs below. Replaces previous RunsList.

const InFlightCard = ({ run, onOpenRun }) => {
  const pct = (run.completed / run.n) * 100;
  const eta = Math.round((run.durationS / Math.max(1, run.completed)) * (run.n - run.completed));
  const m = run.model === 'longevity-llm' ? 'L-LLM' : run.model === 'gpt-4o' ? 'GPT-4o' : run.model;
  return (
    <div className="card" style={{ borderColor: 'var(--lb-green-300)', background: 'linear-gradient(180deg, var(--lb-green-50) 0%, #fff 60%)' }}>
      <div style={{ padding: '14px 20px 6px', display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div>
          <Badge kind="info" pulse>Running</Badge>
          <span style={{ marginLeft: 10, font: '500 14px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>{run.id}</span>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button variant="secondary" size="small">View live</Button>
          <Button variant="ghost" size="small" icon="stop">Cancel</Button>
        </div>
      </div>
      <div style={{ padding: '6px 20px 16px', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr) 2fr', gap: 16, alignItems: 'end' }}>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Task</div>
          <div><Pill brand>{run.lbId}</Pill></div>
        </div>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Model</div>
          <div style={{ font: '500 14px var(--lb-font-mono)', color: 'var(--lb-fg-1)' }}>{m}</div>
        </div>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>Avg latency</div>
          <div style={{ font: '500 14px var(--lb-font-mono)', color: 'var(--lb-fg-1)', fontVariantNumeric: 'tabular-nums' }}>{(run.durationS / Math.max(1, run.completed)).toFixed(1)}s</div>
        </div>
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 4 }}>ETA</div>
          <div style={{ font: '500 14px var(--lb-font-mono)', color: 'var(--lb-fg-1)', fontVariantNumeric: 'tabular-nums' }}>{Math.floor(eta / 60)}m {eta % 60}s</div>
        </div>
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span className="lb-eyebrow">Progress</span>
            <span style={{ font: '500 12px var(--lb-font-mono)', color: 'var(--lb-fg-1)', fontVariantNumeric: 'tabular-nums' }}>{run.completed} / {run.n} · {pct.toFixed(0)}%</span>
          </div>
          <div style={{ height: 8, background: '#fff', border: '1px solid var(--lb-border)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', background: 'var(--lb-green-500)', borderRadius: 4, transition: 'width 600ms var(--lb-ease)' }} />
          </div>
        </div>
      </div>
      {/* live log strip */}
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ font: '400 11px var(--lb-font-mono)', color: 'var(--lb-fg-3)', borderTop: '1px dashed var(--lb-border)', paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span><span style={{ color: 'var(--lb-fg-4)' }}>06:14:22</span> row 84 ← daf-2 · age-1 · pred <span style={{ color: 'var(--lb-green-700)' }}>synergistic</span> · 4.2s</span>
          <span><span style={{ color: 'var(--lb-fg-4)' }}>06:14:18</span> row 83 ← clk-1 · isp-1 · pred <span style={{ color: 'var(--lb-green-700)' }}>additive</span> · 5.7s</span>
          <span><span style={{ color: 'var(--lb-fg-4)' }}>06:14:11</span> row 82 ← FOXO3 · MTOR · pred <span style={{ color: 'var(--lb-error)' }}>extended</span> · 7.1s · trace inconsistent</span>
        </div>
      </div>
    </div>
  );
};

const CompletedRow = ({ run, onClick }) => {
  const primaryScore = run.f1 ?? run.mae ?? run.spark?.[7];
  const scoreLabel = run.f1 != null ? run.f1.toFixed(2)
                   : run.mae != null ? 'MAE ' + run.mae.toFixed(1)
                   : primaryScore != null ? primaryScore.toFixed(2) : '—';
  const score = primaryScore != null
    ? <span className="num">{scoreLabel}</span>
    : <span className="num" style={{ color: 'var(--lb-fg-4)' }}>—</span>;

  const modelColor = (MODEL_COLORS || {})[run.modelId] || (MODEL_COLORS || {})[run.model] || '#8c948c';
  const modelLabel = run.model;
  const statusBadge = run.status === 'failed'
    ? <Badge kind="err">Failed · {run.errors} err</Badge>
    : <Badge kind="pass">Complete</Badge>;

  return (
    <div className="run-row" onClick={() => onClick(run)}>
      <Icon name={run.status === 'failed' ? 'alert' : 'check'} size={14}
            style={{ color: run.status === 'failed' ? 'var(--lb-error)' : 'var(--lb-green-600)' }} />
      <div>
        <div className="title">{run.taskName.replace(/_/g, ' ')}</div>
        <div className="sub">{run.id}</div>
      </div>
      <div>
        <Pill brand>{run.lbId}</Pill>
        <div className="sub" style={{ marginTop: 4 }}>{run.think ? '— think mode' : ''}</div>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <span className="badge" style={{ background: 'transparent', color: modelColor, padding: 0 }}>
          <i style={{ width: 8, height: 8, borderRadius: 2, background: modelColor, display: 'inline-block', marginRight: 6 }} />
          {modelLabel}
        </span>
      </div>
      <div>{statusBadge}</div>
      {score}
      <Sparkline values={run.spark} color={modelColor} />
    </div>
  );
};

const LiveRunsView = ({ runs, onOpenRun }) => {
  const live = runs.filter(r => r.status === 'running');
  const done = runs.filter(r => r.status !== 'running');
  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Live monitoring</div>
          <h1>Runs</h1>
          <div className="sub">{live.length} in flight · {done.filter(r => r.status === 'complete').length} complete · auto-refresh every 5s</div>
        </div>
        <div className="actions">
          <Button variant="ghost" icon="download" size="small">Export CSV</Button>
          <Button variant="secondary" size="small">Filter</Button>
        </div>
      </div>

      {live.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 22 }}>
          {live.map(r => <InFlightCard key={r.id} run={r} onOpenRun={onOpenRun} />)}
        </div>
      )}

      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="head">
          <h3>Completed</h3>
          <p className="sub">{done.length} runs</p>
          <div className="right">
            <Badge kind="pass">{done.filter(r => r.status === 'complete').length} complete</Badge>
            <Badge kind="err">{done.filter(r => r.status === 'failed').length} failed</Badge>
          </div>
        </div>
        <div>
          {done.map(r => <CompletedRow key={r.id} run={r} onClick={onOpenRun} />)}
        </div>
      </div>
    </>
  );
};

Object.assign(window, { LiveRunsView });
