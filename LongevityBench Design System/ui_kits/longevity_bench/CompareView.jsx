// CompareView — model comparison. Side-by-side per-task breakdown +
// big aggregate bar chart, with delta callouts.

const MODELS = [
  { id: 'longevity-llm', name: 'L-LLM',       sub: 'Insilico · Qwen3.5-9B', color: 'var(--lb-green-500)' },
  { id: 'gpt-4o',        name: 'GPT-4o',      sub: 'OpenAI',                 color: '#2a6dc8' },
  { id: 'majority',      name: 'Majority',    sub: 'baseline',               color: '#c98b1c' },
  { id: 'random',        name: 'Random',      sub: '1000-seed avg',          color: '#8c948c' },
];

const TASK_RESULTS = [
  { id: 'LB-0038', name: 'epistasis_ternary',  scores: { 'longevity-llm': 0.62, 'gpt-4o': 0.58, majority: 0.42, random: 0.33 }, ci: { 'longevity-llm': [0.58, 0.66] } },
  { id: 'LB-0042', name: 'lifespan_mae',        scores: { 'longevity-llm': 0.71, 'gpt-4o': 0.64, majority: 0.50, random: 0.50 }, ci: { 'longevity-llm': [0.67, 0.75] } },
  { id: 'LB-0051', name: 'gene_pathway_mcq',    scores: { 'longevity-llm': 0.54, 'gpt-4o': 0.69, majority: 0.25, random: 0.25 }, ci: { 'longevity-llm': [0.49, 0.59] } },
  { id: 'LB-0067', name: 'organism_pairwise',   scores: { 'longevity-llm': 0.71, 'gpt-4o': 0.66, majority: 0.50, random: 0.50 }, ci: { 'longevity-llm': [0.66, 0.76] } },
  { id: 'LB-0072', name: 'negation_binary',     scores: { 'longevity-llm': 0.48, 'gpt-4o': 0.71, majority: 0.50, random: 0.50 }, ci: { 'longevity-llm': [0.43, 0.53] } },
  { id: 'LB-0090', name: 'set_generation',      scores: { 'longevity-llm': 0.59, 'gpt-4o': 0.55, majority: 0.20, random: 0.18 }, ci: { 'longevity-llm': [0.52, 0.66] } },
];

const HorizontalBars = ({ task }) => {
  const max = 1.0;
  return (
    <div style={{ padding: '14px 18px 18px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <Pill brand>{task.id}</Pill>
          <span style={{ marginLeft: 8, font: '500 14px var(--lb-font-sans)', color: 'var(--lb-fg-1)' }}>{task.name.replace(/_/g, ' ')}</span>
        </div>
        <span className="lb-meta" style={{ fontFamily: 'var(--lb-font-mono)' }}>
          Δ vs GPT-4o:{' '}
          {(() => {
            const d = task.scores['longevity-llm'] - task.scores['gpt-4o'];
            return <span style={{ color: d >= 0 ? 'var(--lb-green-700)' : 'var(--lb-error)', fontWeight: 500 }}>{d >= 0 ? '+' : '−'}{Math.abs(d).toFixed(2)}</span>;
          })()}
        </span>
      </div>
      {MODELS.map(m => {
        const v = task.scores[m.id];
        const ci = task.ci[m.id];
        return (
          <div key={m.id} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 48px', alignItems: 'center', gap: 12, marginBottom: 7 }}>
            <span style={{ font: '500 12px var(--lb-font-sans)', color: 'var(--lb-fg-2)' }}>{m.name}</span>
            <div style={{ position: 'relative', height: 8, background: 'var(--lb-ink-100)', borderRadius: 4 }}>
              <div style={{ position: 'absolute', left: 0, top: 0, height: '100%', width: `${(v / max) * 100}%`, background: m.color, borderRadius: 4 }} />
              {ci && (
                <div style={{ position: 'absolute', top: -2, left: `${(ci[0] / max) * 100}%`, width: `${((ci[1] - ci[0]) / max) * 100}%`, height: 12, borderLeft: '1px solid ' + m.color, borderRight: '1px solid ' + m.color }} />
              )}
            </div>
            <span style={{ font: '500 12px var(--lb-font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--lb-fg-1)', textAlign: 'right' }}>{v.toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
};

const CompareView = () => {
  // Aggregate macro F1
  const agg = MODELS.map(m => ({
    ...m,
    avg: TASK_RESULTS.reduce((s, t) => s + t.scores[m.id], 0) / TASK_RESULTS.length,
    wins: TASK_RESULTS.filter(t => Math.max(...Object.values(t.scores)) === t.scores[m.id]).length,
  }));
  return (
    <>
      <div className="page-head">
        <div>
          <div className="lb-eyebrow" style={{ marginBottom: 6 }}>Where the longevity-tuned model beats general-purpose models</div>
          <h1>Model comparison</h1>
          <div className="sub">L-LLM vs GPT-4o vs baselines · 6 LongeBench tasks · macro F1 · 95% CIs</div>
        </div>
        <div className="actions">
          <Button variant="ghost" icon="download" size="small">gap_analysis.md</Button>
          <Button variant="secondary" size="small" icon="file">View JSONL</Button>
        </div>
      </div>

      {/* Aggregate cards */}
      <div className="metric-grid">
        {agg.map(m => (
          <div key={m.id} className="metric" style={{ position: 'relative' }}>
            <div className="lbl" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 10, height: 10, background: m.color, borderRadius: 2, display: 'inline-block' }} />
              {m.name}
            </div>
            <div className="val">{m.avg.toFixed(2)}</div>
            <div className="sub">{m.sub} · {m.wins}/{TASK_RESULTS.length} task wins</div>
          </div>
        ))}
      </div>

      {/* Highlights */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="head">
          <h3>Key findings</h3>
          <p className="sub">where L-LLM beats GPT-4o · and where it doesn't</p>
        </div>
        <div style={{ padding: '14px 20px 18px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
          <div style={{ padding: 14, background: 'var(--lb-success-bg)', borderRadius: 6, border: '1px solid #c1e0b9' }}>
            <div className="lb-eyebrow" style={{ color: 'var(--lb-green-700)', marginBottom: 6 }}>L-LLM wins</div>
            <p style={{ margin: 0, font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', lineHeight: 1.55 }}>
              <strong>+0.07</strong> on lifespan regression (Task B). <strong>+0.05</strong> on organism-pairwise. The fine-tuning carries domain priors GPT-4o lacks for C. elegans gene naming and IIS-pathway logic.
            </p>
          </div>
          <div style={{ padding: 14, background: 'var(--lb-error-bg)', borderRadius: 6, border: '1px solid #f0c8c2' }}>
            <div className="lb-eyebrow" style={{ color: '#8a2419', marginBottom: 6 }}>L-LLM loses</div>
            <p style={{ margin: 0, font: '400 13px var(--lb-font-sans)', color: 'var(--lb-fg-1)', lineHeight: 1.55 }}>
              <strong>−0.23</strong> on negation-binary. GPT-4o handles "which gene is NOT associated…" prompts noticeably better. Fine-tuning on positive examples appears to have hurt negation handling.
            </p>
          </div>
        </div>
      </div>

      {/* Per-task panels */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div className="head">
          <h3>Per-task macro F1</h3>
          <p className="sub">95% CI shown for L-LLM only</p>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0, borderTop: '1px solid var(--lb-border)' }}>
          {TASK_RESULTS.map((t, i) => (
            <div key={t.id} style={{
              borderRight: i % 2 === 0 ? '1px solid var(--lb-border)' : 'none',
              borderBottom: i < TASK_RESULTS.length - 2 ? '1px solid var(--lb-border)' : 'none',
            }}>
              <HorizontalBars task={t} />
            </div>
          ))}
        </div>
      </div>
    </>
  );
};

Object.assign(window, { CompareView, MODELS, TASK_RESULTS });
