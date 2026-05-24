// HomeView — benchmark landing page.
// Follows Insilico Medicine visual system: white-first, DM Sans 500,
// green-50 hero wash, large tabular numbers, scientific tone.

const HomeView = ({ runs = [], records = [], setView }) => {
  const BIDS = ['majority_baseline', 'random_baseline', 'population_prior_baseline'];
  const FMT_LABELS = { mcq: 'MCQ', binary: 'Binary', pairwise: 'Pairwise', regression: 'Regression' };
  const FORMAT_ORDER = ['mcq', 'binary', 'pairwise', 'regression'];

  // ── Derive model list ────────────────────────────────────────────────────────
  const modelMap = {};
  runs.filter(r => r.status === 'complete').forEach(r => {
    if (!modelMap[r.modelId]) modelMap[r.modelId] = {
      id: r.modelId, name: r.model,
      color: (MODEL_COLORS || {})[r.modelId] || 'var(--lb-ink-400)',
    };
  });
  const allModels = Object.values(modelMap);
  const nonBaselines = allModels.filter(m => !BIDS.includes(m.id));
  const fmtsPresent = FORMAT_ORDER.filter(f => records.some(r => r.format === f));

  // ── Per-model avg score ──────────────────────────────────────────────────────
  const modelScores = allModels.map(m => {
    const vals = fmtsPresent.map(fmt => {
      const scored = records.filter(r => r.format === fmt)
        .map(r => r.cells?.[m.id]).filter(c => c && c.score != null);
      return scored.length > 0 ? scored.reduce((s, c) => s + c.score, 0) / scored.length : null;
    }).filter(v => v != null);
    return { ...m, avg: vals.length > 0 ? vals.reduce((a, b) => a + b, 0) / vals.length : null };
  }).sort((a, b) => (b.avg ?? 0) - (a.avg ?? 0));

  const nbScores = modelScores.filter(m => !BIDS.includes(m.id) && m.avg != null);
  const best = nbScores[0];
  const second = nbScores[1];
  const majScore = modelScores.find(m => m.id === 'majority_baseline')?.avg;
  const bestAll = modelScores.reduce((mx, m) => m.avg != null ? Math.max(mx, m.avg) : mx, 0);

  // ── Per-format leaders ───────────────────────────────────────────────────────
  const fmtLeaders = {};
  fmtsPresent.forEach(fmt => {
    const cands = nbScores.map(m => {
      const scored = records.filter(r => r.format === fmt)
        .map(r => r.cells?.[m.id]).filter(c => c && c.score != null);
      const score = scored.length > 0 ? scored.reduce((s, c) => s + c.score, 0) / scored.length : null;
      return { ...m, fmtScore: score };
    }).filter(m => m.fmtScore != null).sort((a, b) => b.fmtScore - a.fmtScore);
    if (cands[0]) fmtLeaders[fmt] = cands[0];
  });

  // ── Task subset counts ───────────────────────────────────────────────────────
  const senRecs = records.filter(r => (r.lb_id || '').startsWith('LB-SEN'));
  const lipRecs = records.filter(r => (r.lb_id || '').startsWith('LB-LIP'));
  const hasData = allModels.length > 0 && records.length > 0;

  // ── Key finding text ─────────────────────────────────────────────────────────
  const findings = [];
  if (best) findings.push(`${best.name} leads overall · ${(best.avg * 100).toFixed(1)}%`);
  Object.entries(fmtLeaders).forEach(([fmt, m]) =>
    findings.push(`${m.name} leads ${FMT_LABELS[fmt] || fmt} (${(m.fmtScore * 100).toFixed(1)}%)`)
  );
  if (best && majScore != null)
    findings.push(`+${((best.avg - majScore) * 100).toFixed(1)}% above majority baseline`);

  // ── Shared micro-styles ──────────────────────────────────────────────────────
  const eyebrow = {
    fontFamily: 'var(--lb-font-mono)', fontSize: 11,
    fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.12em',
    color: 'var(--lb-fg-4)',
  };
  const monoNum = (size = 44, color = 'var(--lb-fg-1)') => ({
    fontFamily: 'var(--lb-font-mono)', fontSize: size,
    fontWeight: 600, letterSpacing: '-0.02em',
    fontVariantNumeric: 'tabular-nums', color, lineHeight: 1,
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>

      {/* ── Hero band ─────────────────────────────────────────────────────────── */}
      <div style={{
        background: 'linear-gradient(180deg, var(--lb-green-50) 0%, var(--lb-ink-0) 100%)',
        borderRadius: 12, border: '1px solid var(--lb-border)',
        borderTop: '3px solid var(--lb-green-500)',
        padding: '40px 48px 36px',
        marginBottom: 20,
        display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 32,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ ...eyebrow, marginBottom: 16 }}>
            Caltech Longevity Hackathon · Track 01 · Sponsored by Insilico Medicine
          </div>
          <h1 style={{
            fontFamily: 'var(--lb-font-display)', fontSize: 44,
            fontWeight: 500, letterSpacing: '-0.022em', lineHeight: 1.08,
            color: 'var(--lb-fg-1)', margin: '0 0 14px',
          }}>
            LongevityBench-X
          </h1>
          <p style={{
            fontFamily: 'var(--lb-font-sans)', fontSize: 17,
            fontWeight: 400, color: 'var(--lb-fg-2)', lineHeight: 1.6,
            margin: '0 0 28px', maxWidth: 520,
          }}>
            Measuring LLMs' ability to derive high-level phenotypes from low-level biological data.
            Two novel task suites, four models, automated reasoning trace scoring.
          </p>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => setView('compare')} style={{
              fontFamily: 'var(--lb-font-sans)', fontSize: 13, fontWeight: 500,
              padding: '9px 20px', borderRadius: 4, border: 'none',
              background: 'var(--lb-green-500)', color: '#fff', cursor: 'pointer',
              letterSpacing: '0.01em',
            }}>
              View results
            </button>
            <button onClick={() => setView('lipidomics')} style={{
              fontFamily: 'var(--lb-font-sans)', fontSize: 13, fontWeight: 500,
              padding: '9px 20px', borderRadius: 4,
              border: '1px solid var(--lb-border)',
              background: 'rgba(255,255,255,0.7)', color: 'var(--lb-fg-2)', cursor: 'pointer',
            }}>
              Browse datasets
            </button>
          </div>
        </div>

        {/* Insilico co-branding */}
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'flex-end',
          gap: 8, flexShrink: 0, paddingTop: 4,
        }}>
          <img
            src="public/insilico-medicine-logo.svg"
            alt="Insilico Medicine"
            style={{ height: 28, opacity: 0.85 }}
          />
          <div style={{
            fontFamily: 'var(--lb-font-mono)', fontSize: 10, color: 'var(--lb-fg-4)',
            textTransform: 'uppercase', letterSpacing: '0.1em', textAlign: 'right',
          }}>
            L-LLM endpoint · Qwen3.5-9B
          </div>
        </div>
      </div>

      {/* ── Stat band — big tabular numbers ─────────────────────────────────── */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        borderRadius: 8, border: '1px solid var(--lb-border)',
        overflow: 'hidden', marginBottom: 20,
      }}>
        {[
          { label: 'Benchmark prompts', value: '583',  sub: '298 senescence · 285 lipidomics', color: 'var(--lb-green-500)' },
          { label: 'Task suites',        value: '2',    sub: 'transcriptomics · lipidomics', color: 'var(--lb-fg-1)' },
          { label: 'Models evaluated',   value: hasData ? String(allModels.length) : '5', sub: hasData ? `${nonBaselines.length} model${nonBaselines.length !== 1 ? 's' : ''} · ${allModels.length - nonBaselines.length} baselines` : 'L-LLM · Claude · 3 baselines', color: 'var(--lb-fg-1)' },
          { label: 'Avg trace faithfulness', value: '0.716', sub: '89.5% gene verification · V5', color: 'var(--lb-info)' },
        ].map(({ label, value, sub, color }, i) => (
          <div key={label} style={{
            padding: '24px 28px',
            background: 'var(--lb-ink-0)',
            borderLeft: i > 0 ? '1px solid var(--lb-border)' : 'none',
          }}>
            <div style={{ ...eyebrow, marginBottom: 10 }}>{label}</div>
            <div style={{ ...monoNum(48, color), marginBottom: 6 }}>{value}</div>
            <div style={{
              fontFamily: 'var(--lb-font-sans)', fontSize: 12,
              color: 'var(--lb-fg-4)', lineHeight: 1.4,
            }}>{sub}</div>
          </div>
        ))}
      </div>

      {/* ── Key finding ───────────────────────────────────────────────────────── */}
      {hasData && findings.length > 0 ? (
        <div style={{
          marginBottom: 20,
          padding: '18px 24px',
          borderRadius: 8, border: '1px solid var(--lb-border)',
          borderLeft: '4px solid var(--lb-green-500)',
          background: 'var(--lb-green-50)',
          display: 'flex', alignItems: 'flex-start', gap: 16,
        }}>
          <div style={{
            fontFamily: 'var(--lb-font-mono)', fontSize: 11, fontWeight: 600,
            textTransform: 'uppercase', letterSpacing: '0.12em',
            color: 'var(--lb-green-700)', flexShrink: 0, paddingTop: 2,
          }}>
            Finding
          </div>
          <div style={{
            fontFamily: 'var(--lb-font-sans)', fontSize: 14,
            color: 'var(--lb-fg-2)', lineHeight: 1.8,
            display: 'flex', flexWrap: 'wrap', gap: '4px 0',
          }}>
            {findings.map((f, i) => (
              <span key={i}>
                {i > 0 && <span style={{ color: 'var(--lb-ink-300)', margin: '0 10px' }}>·</span>}
                {f}
              </span>
            ))}
          </div>
        </div>
      ) : (
        <div style={{
          marginBottom: 20, padding: '14px 20px',
          borderRadius: 8, border: '1px solid var(--lb-border)',
          borderLeft: '4px solid var(--lb-ink-300)',
          fontFamily: 'var(--lb-font-sans)', fontSize: 13, color: 'var(--lb-fg-4)', lineHeight: 1.6,
        }}>
          No completed runs yet. Run{' '}
          <code style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 12 }}>pipeline.py</code>
          {' '}then export logs to populate results.
        </div>
      )}

      {/* ── Task cards ────────────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginBottom: 20 }}>

        {/* Task B — Lipidomics (featured first) */}
        <div style={{
          borderRadius: 8, border: '1px solid var(--lb-border)',
          background: 'var(--lb-ink-0)',
          overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          {/* Accent strip */}
          <div style={{ height: 4, background: 'var(--lb-info)' }} />
          <div style={{ padding: '24px 24px 20px', display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{
                  fontFamily: 'var(--lb-font-mono)', fontSize: 10, fontWeight: 500,
                  textTransform: 'uppercase', letterSpacing: '0.1em',
                  color: 'var(--lb-info)', background: 'var(--lb-info-bg)',
                  padding: '2px 8px', borderRadius: 2,
                }}>Task B · Lipidomics</span>
                <span style={{
                  fontFamily: 'var(--lb-font-mono)', fontSize: 10,
                  color: 'var(--lb-fg-4)', background: 'var(--lb-ink-50)',
                  padding: '2px 8px', borderRadius: 2, border: '1px solid var(--lb-border)',
                }}>MTBLS4461 · EBI MetaboLights</span>
              </div>
              <h2 style={{
                fontFamily: 'var(--lb-font-display)', fontSize: 20,
                fontWeight: 500, letterSpacing: '-0.01em', lineHeight: 1.2,
                color: 'var(--lb-fg-1)', margin: '0 0 10px',
              }}>
                Plasma Lipidomics<br />Age &amp; Diabetes Prediction
              </h2>
              <p style={{
                fontFamily: 'var(--lb-font-sans)', fontSize: 13,
                color: 'var(--lb-fg-3)', lineHeight: 1.65, margin: 0,
              }}>
                Given a plasma lipidomics profile (≈497 lipid species, DI-MS alternating polarity,
                1,864 donors), predict donor age bracket, numeric age, or diabetes status.
                Tests whether LLMs extract clinically meaningful signals from high-dimensional
                metabolomics without sequence modalities.
              </p>
            </div>

            {/* Format tiles */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {[
                { label: 'Age bracket',    metric: 'Off-by-one acc.', fmt: 'mcq',        n: lipRecs.filter(r => r.format === 'mcq').length || 85 },
                { label: 'Age regression', metric: 'MAE (years)',     fmt: 'regression', n: lipRecs.filter(r => r.format === 'regression').length || 100 },
                { label: 'Diabetes',       metric: 'Accuracy',        fmt: 'binary',     n: lipRecs.filter(r => r.format === 'binary').length || 100 },
              ].map(({ label, metric, n }) => (
                <div key={label} style={{
                  padding: '10px 12px',
                  background: 'var(--lb-ink-50)',
                  borderRadius: 6, border: '1px solid var(--lb-border)',
                }}>
                  <div style={{ fontFamily: 'var(--lb-font-sans)', fontSize: 12, fontWeight: 500, color: 'var(--lb-fg-2)', marginBottom: 2 }}>{label}</div>
                  <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 10, color: 'var(--lb-fg-4)', marginBottom: 6 }}>{metric}</div>
                  <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 16, fontWeight: 600, color: 'var(--lb-info)', fontVariantNumeric: 'tabular-nums' }}>{n}</div>
                  <div style={{ fontFamily: 'var(--lb-font-sans)', fontSize: 10, color: 'var(--lb-fg-4)' }}>prompts</div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 12, borderTop: '1px solid var(--lb-border)', marginTop: 'auto' }}>
              <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11, color: 'var(--lb-fg-4)' }}>
                285 prompts · 228 train / 57 test · 1,864 donors
              </div>
              <button onClick={() => setView('lipidomics')} style={{
                fontFamily: 'var(--lb-font-sans)', fontSize: 12, fontWeight: 500,
                padding: '6px 16px', borderRadius: 4,
                border: '1px solid var(--lb-info)',
                background: 'transparent', color: 'var(--lb-info)', cursor: 'pointer',
              }}>Browse prompts →</button>
            </div>
          </div>
        </div>

        {/* Task A — Senescence */}
        <div style={{
          borderRadius: 8, border: '1px solid var(--lb-border)',
          background: 'var(--lb-ink-0)', overflow: 'hidden',
          display: 'flex', flexDirection: 'column',
        }}>
          <div style={{ height: 4, background: 'var(--lb-viz-5)' }} />
          <div style={{ padding: '24px 24px 20px', display: 'flex', flexDirection: 'column', gap: 16, flex: 1 }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{
                  fontFamily: 'var(--lb-font-mono)', fontSize: 10, fontWeight: 500,
                  textTransform: 'uppercase', letterSpacing: '0.1em',
                  color: 'var(--lb-viz-5)', background: '#f0e8fc',
                  padding: '2px 8px', borderRadius: 2,
                }}>Task A · Senescence</span>
                <span style={{
                  fontFamily: 'var(--lb-font-mono)', fontSize: 10,
                  color: 'var(--lb-fg-4)', background: 'var(--lb-ink-50)',
                  padding: '2px 8px', borderRadius: 2, border: '1px solid var(--lb-border)',
                }}>CellAge v3 · GEO</span>
              </div>
              <h2 style={{
                fontFamily: 'var(--lb-font-display)', fontSize: 20,
                fontWeight: 500, letterSpacing: '-0.01em', lineHeight: 1.2,
                color: 'var(--lb-fg-1)', margin: '0 0 10px',
              }}>
                Senescence Perturbation<br />Transcriptomics
              </h2>
              <p style={{
                fontFamily: 'var(--lb-font-sans)', fontSize: 13,
                color: 'var(--lb-fg-3)', lineHeight: 1.65, margin: 0,
              }}>
                Gene-level differential expression across 43 GEO accessions of perturbation experiments
                in human fibroblasts (Senescent Fibroblast Transcriptome Compendium × CellAge v3
                non-cancer genes). Tests perturbation-driven expression change prediction without
                data retrieval.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {[
                { label: 'Direction MCQ',    metric: 'Accuracy (3-class)', fmt: 'mcq',      n: senRecs.filter(r => r.format === 'mcq').length || 99 },
                { label: 'Gene pairwise',    metric: 'Balanced acc.',      fmt: 'pairwise', n: senRecs.filter(r => r.format === 'pairwise').length || 99 },
                { label: 'Significance',     metric: 'Accuracy',           fmt: 'binary',   n: senRecs.filter(r => r.format === 'binary').length || 100 },
              ].map(({ label, metric, n }) => (
                <div key={label} style={{
                  padding: '10px 12px',
                  background: 'var(--lb-ink-50)',
                  borderRadius: 6, border: '1px solid var(--lb-border)',
                }}>
                  <div style={{ fontFamily: 'var(--lb-font-sans)', fontSize: 12, fontWeight: 500, color: 'var(--lb-fg-2)', marginBottom: 2 }}>{label}</div>
                  <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 10, color: 'var(--lb-fg-4)', marginBottom: 6 }}>{metric}</div>
                  <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 16, fontWeight: 600, color: 'var(--lb-viz-5)', fontVariantNumeric: 'tabular-nums' }}>{n}</div>
                  <div style={{ fontFamily: 'var(--lb-font-sans)', fontSize: 10, color: 'var(--lb-fg-4)' }}>prompts</div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: 12, borderTop: '1px solid var(--lb-border)', marginTop: 'auto' }}>
              <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11, color: 'var(--lb-fg-4)' }}>
                298 prompts · 239 train / 59 test · 43 GEO accessions
              </div>
              <button onClick={() => setView('senescence')} style={{
                fontFamily: 'var(--lb-font-sans)', fontSize: 12, fontWeight: 500,
                padding: '6px 16px', borderRadius: 4,
                border: '1px solid var(--lb-border)',
                background: 'transparent', color: 'var(--lb-fg-2)', cursor: 'pointer',
              }}>Browse prompts →</button>
            </div>
          </div>
        </div>
      </div>

      {/* ── Section divider ───────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--lb-fg-4)', flexShrink: 0 }}>Evaluation results</div>
        <div style={{ flex: 1, height: 1, background: 'var(--lb-border)' }} />
      </div>

      {/* ── Bottom row: leaderboard + trace ───────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>

        {/* Model leaderboard */}
        <div style={{ borderRadius: 8, border: '1px solid var(--lb-border)', padding: '22px 24px', background: 'var(--lb-ink-0)' }}>
          <div style={{ marginBottom: 18 }}>
            <div style={{ ...eyebrow, marginBottom: 6 }}>Model leaderboard</div>
            <div style={{
              fontFamily: 'var(--lb-font-sans)', fontSize: 13, color: 'var(--lb-fg-3)',
            }}>Avg score across all formats · test set</div>
          </div>

          {hasData && modelScores.filter(m => m.avg != null).length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {modelScores.filter(m => m.avg != null).map((m, i) => {
                const isBase = BIDS.includes(m.id);
                const pct = bestAll > 0 ? m.avg / bestAll : 0;
                return (
                  <div key={m.id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 5 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 10, color: 'var(--lb-fg-4)', width: 14 }}>{i + 1}</span>
                        <span style={{
                          fontFamily: 'var(--lb-font-sans)', fontSize: 13,
                          fontWeight: isBase ? 400 : 500,
                          color: isBase ? 'var(--lb-fg-4)' : 'var(--lb-fg-1)',
                        }}>{m.name}</span>
                        {!isBase && i === 0 && (
                          <span style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 9, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--lb-green-700)', background: 'var(--lb-green-50)', padding: '1px 5px', borderRadius: 2 }}>best</span>
                        )}
                      </div>
                      <span style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 13, fontWeight: 600, color: m.color, fontVariantNumeric: 'tabular-nums' }}>
                        {(m.avg * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div style={{ height: 3, background: 'var(--lb-ink-100)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${pct * 100}%`, background: isBase ? 'var(--lb-ink-300)' : m.color, borderRadius: 2, transition: 'width 0.5s var(--lb-ease-out)' }} />
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{
              padding: '28px 0', textAlign: 'center',
              fontFamily: 'var(--lb-font-sans)', fontSize: 13, color: 'var(--lb-fg-4)',
            }}>
              No completed runs.
              <br /><code style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 11 }}>pipeline.py</code> to populate.
            </div>
          )}

          <button onClick={() => setView('compare')} style={{
            marginTop: 18, width: '100%',
            fontFamily: 'var(--lb-font-sans)', fontSize: 12, fontWeight: 500,
            padding: '8px 0', borderRadius: 4,
            border: '1px solid var(--lb-border)',
            background: 'transparent', color: 'var(--lb-fg-2)', cursor: 'pointer',
            textTransform: 'uppercase', letterSpacing: '0.06em', fontFamily: 'var(--lb-font-mono)',
          }}>Full comparison →</button>
        </div>

        {/* Trace scorer */}
        <div style={{ borderRadius: 8, border: '1px solid var(--lb-border)', padding: '22px 24px', background: 'var(--lb-ink-0)', display: 'flex', flexDirection: 'column' }}>
          <div style={{ marginBottom: 16 }}>
            <div style={{ ...eyebrow, color: 'var(--lb-info)', marginBottom: 6 }}>
              Reasoning trace scorer · V5 · Extra credit
            </div>
            <div style={{
              fontFamily: 'var(--lb-font-display)', fontSize: 18,
              fontWeight: 500, color: 'var(--lb-fg-1)', marginBottom: 8, lineHeight: 1.2,
            }}>
              Does L-LLM reason correctly?
            </div>
            <div style={{ fontFamily: 'var(--lb-font-sans)', fontSize: 13, color: 'var(--lb-fg-3)', lineHeight: 1.65 }}>
              Getting the right answer for the wrong reasons is a training-time failure mode.
              Each thinking trace is scored against live biological databases.
            </div>
          </div>

          {/* Three metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1, background: 'var(--lb-border)', borderRadius: 6, overflow: 'hidden', marginBottom: 16 }}>
            {[
              { label: 'Faithfulness', value: '0.716', sub: 'n=29 traces' },
              { label: 'Gene score',   value: '0.895', sub: 'mygene.info' },
              { label: 'Kw. consist.', value: '0.448', sub: 'up/down/neg.' },
            ].map(({ label, value, sub }) => (
              <div key={label} style={{ padding: '14px 16px', background: 'var(--lb-ink-50)', textAlign: 'center' }}>
                <div style={{ ...monoNum(24, 'var(--lb-fg-1)'), marginBottom: 4 }}>{value}</div>
                <div style={{ fontFamily: 'var(--lb-font-sans)', fontSize: 11, fontWeight: 500, color: 'var(--lb-fg-3)', marginBottom: 2 }}>{label}</div>
                <div style={{ fontFamily: 'var(--lb-font-mono)', fontSize: 10, color: 'var(--lb-fg-4)' }}>{sub}</div>
              </div>
            ))}
          </div>

          {/* Formula */}
          <div style={{
            padding: '12px 16px', borderRadius: 6,
            border: '1px solid var(--lb-border)', background: 'var(--lb-ink-50)',
            fontFamily: 'var(--lb-font-mono)', fontSize: 11,
            color: 'var(--lb-fg-3)', lineHeight: 1.9, marginBottom: 16,
          }}>
            faithfulness =<br />
            {'  '}0.40 × gene_score<br />
            + 0.20 × keyword_consistency<br />
            + 0.40 × property_score
          </div>

          <button onClick={() => setView('trust')} style={{
            marginTop: 'auto', width: '100%',
            fontFamily: 'var(--lb-font-mono)', fontSize: 12, fontWeight: 500,
            padding: '8px 0', borderRadius: 4,
            border: '1px solid var(--lb-green-400)',
            background: 'transparent', color: 'var(--lb-green-700)', cursor: 'pointer',
            textTransform: 'uppercase', letterSpacing: '0.06em',
          }}>Trust &amp; reasoning →</button>
        </div>

      </div>

    </div>
  );
};

Object.assign(window, { HomeView });
