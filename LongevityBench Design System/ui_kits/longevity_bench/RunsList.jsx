// RunsList — Insilico-style table of recent benchmark runs.

const Sparkline = ({ values, color = 'var(--lb-green-400)' }) => (
  <div className="spark">
    {values.map((v, i) => (
      <span key={i} style={{ height: `${Math.max(2, v * 22)}px`, background: color, opacity: 0.4 + (i / values.length) * 0.6 }} />
    ))}
  </div>
);

const RunRow = ({ run, onClick }) => {
  const statusBadge = {
    running: <Badge kind="info" pulse>Running · {run.completed}/{run.n}</Badge>,
    complete: <Badge kind="pass">Complete</Badge>,
    failed: <Badge kind="err">Failed · {run.errors} err</Badge>,
  }[run.status];

  const score = run.f1 != null
    ? <span className="num">{run.f1.toFixed(2)}</span>
    : run.mae != null
      ? <span className="num">MAE {run.mae.toFixed(1)}</span>
      : <span className="num" style={{ color: 'var(--lb-fg-4)' }}>—</span>;

  const modelColor = run.model === 'longevity-llm' ? 'var(--lb-green-500)' :
                     run.model === 'gpt-4o' ? '#2a6dc8' :
                     run.model === 'majority-baseline' ? '#c98b1c' : '#8c948c';
  const modelLabel = run.model === 'longevity-llm' ? 'L-LLM' :
                     run.model === 'gpt-4o' ? 'GPT-4o' :
                     run.model === 'majority-baseline' ? 'Majority' : run.model;

  // when: just hour:minute today, else date.
  const t = new Date(run.started.replace('Z', ':00Z'));
  const when = t.toUTCString().slice(5, 17);

  return (
    <div className="run-row" onClick={() => onClick(run)}>
      <Icon name={run.status === 'running' ? 'play' : run.status === 'failed' ? 'alert' : 'check'}
            size={14}
            style={{ color: run.status === 'running' ? 'var(--lb-info)' : run.status === 'failed' ? 'var(--lb-error)' : 'var(--lb-green-600)' }} />
      <div>
        <div className="title">{run.taskName.replace(/_/g, ' ')}</div>
        <div className="sub">{run.id}</div>
      </div>
      <div>
        <Pill brand>{run.lbId}</Pill>
        <div className="sub" style={{ marginTop: 4 }}>{run.think ? '— with think mode' : ''}</div>
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

const RunsList = ({ runs, onOpenRun }) => (
  <>
    <div className="page-head">
      <div>
        <h1>Runs</h1>
        <div className="sub">All benchmark evaluations · most recent first</div>
      </div>
      <div className="actions">
        <Button variant="ghost" icon="download" size="small">Export CSV</Button>
        <Button variant="secondary" size="small">Filter</Button>
      </div>
    </div>

    <div className="card" style={{ overflow: 'hidden' }}>
      <div className="head">
        <h3>Recent runs</h3>
        <p className="sub">{runs.length} total</p>
        <div className="right">
          <Badge kind="pass">{runs.filter(r => r.status === 'complete').length} complete</Badge>
          <Badge kind="info" pulse>{runs.filter(r => r.status === 'running').length} running</Badge>
          <Badge kind="err">{runs.filter(r => r.status === 'failed').length} failed</Badge>
        </div>
      </div>
      <div>
        {runs.map(r => <RunRow key={r.id} run={r} onClick={onOpenRun} />)}
      </div>
    </div>
  </>
);

Object.assign(window, { RunsList, Sparkline });
