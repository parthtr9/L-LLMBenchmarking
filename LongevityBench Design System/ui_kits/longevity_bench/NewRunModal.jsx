// NewRunModal — configure a benchmark run.

const NewRunModal = ({ onCancel, onStart }) => {
  const [lbId, setLbId] = React.useState('LB-0038');
  const [split, setSplit] = React.useState('benchmark / eval');
  const [model, setModel] = React.useState('longevity-llm');
  const [limit, setLimit] = React.useState(20);
  const [concurrency, setConcurrency] = React.useState(4);
  const [maxTokens, setMaxTokens] = React.useState(500);
  const [think, setThink] = React.useState(false);
  const [dryRun, setDryRun] = React.useState(false);

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="head">
          <h2>New run</h2>
          <p>Run a LongeBench task against the hosted L-LLM endpoint or a baseline.</p>
        </div>
        <div className="body">
          <div className="field">
            <label>Task ID</label>
            <input className="input mono" value={lbId} onChange={e => setLbId(e.target.value)} />
            <span className="hint">e.g. LB-0038, LB-0042</span>
          </div>
          <div className="field">
            <label>Dataset config / split</label>
            <select className="input" value={split} onChange={e => setSplit(e.target.value)}>
              <option>benchmark / eval</option>
              <option>extra / eval</option>
              <option>benchmark / train</option>
            </select>
          </div>
          <div className="field full">
            <label>Model</label>
            <select className="input" value={model} onChange={e => setModel(e.target.value)}>
              <option value="longevity-llm">longevity-llm (HF endpoint)</option>
              <option value="gpt-4o">gpt-4o</option>
              <option value="majority-baseline">majority-class baseline</option>
              <option value="random-uniform">random-uniform baseline</option>
            </select>
          </div>
          <div className="field">
            <label>Row limit</label>
            <input className="input mono" type="number" value={limit} onChange={e => setLimit(+e.target.value)} />
            <span className="hint">empty = full split</span>
          </div>
          <div className="field">
            <label>Concurrency</label>
            <input className="input mono" type="number" min={1} max={8} value={concurrency} onChange={e => setConcurrency(+e.target.value)} />
            <span className="hint">cap 8 · endpoint shared</span>
          </div>
          <div className="field">
            <label>Max tokens</label>
            <input className="input mono" type="number" value={maxTokens} onChange={e => setMaxTokens(+e.target.value)} />
          </div>
          <div className="field">
            <label>Seed</label>
            <input className="input mono" type="number" defaultValue={42} />
          </div>
          <div className="field full" style={{ display: 'flex', gap: 24, marginTop: 2 }}>
            <label className="check"><input type="checkbox" checked={think} onChange={e => setThink(e.target.checked)} />Enable Qwen thinking mode</label>
            <label className="check"><input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} />Dry run · skip API calls</label>
          </div>
        </div>
        <div className="foot">
          <span className="meta">seed 42 · cl100k_base tokenizer</span>
          <Button variant="ghost" onClick={onCancel}>Cancel</Button>
          <Button variant="primary" icon="play" onClick={() => onStart({ lbId, model, limit, concurrency, maxTokens, think, dryRun, split })}>Start run</Button>
        </div>
      </div>
    </div>
  );
};

Object.assign(window, { NewRunModal });
