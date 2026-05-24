// Sidebar — Overview → Results → Data & Prompts → Reasoning → System

const Sidebar = ({ view, setView, runsCount, liveCount }) => {
  const item = (id, icon, label, count, isLive) => (
    <div className={`nav-item ${view === id ? 'active' : ''}`} onClick={() => setView(id)}>
      <Icon name={icon} className="ico" />
      <span>{label}</span>
      {isLive && count > 0 && (
        <span className="count" style={{ color: 'var(--lb-green-700)', background: 'var(--lb-green-50)', padding: '1px 6px', borderRadius: 3 }}>
          <span style={{ display: 'inline-block', width: 5, height: 5, borderRadius: '50%', background: 'var(--lb-green-500)', marginRight: 4, animation: 'pulse 1.4s ease-in-out infinite' }} />
          {count} live
        </span>
      )}
      {!isLive && count != null && <span className="count">{count}</span>}
    </div>
  );

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="sym">LB</div>
        <div className="word">
          <span className="a">LongevityBench</span>
          <span className="b">SD hackers · Track 01</span>
        </div>
      </div>

      <div className="nav-section">
        <p className="heading">Overview</p>
        {item('home',    'chart',  'Home')}
      </div>

      <div className="nav-section">
        <p className="heading">Data &amp; Prompts</p>
        {item('lipidomics', 'flask', 'Lipidomics',  '285')}
        {item('senescence', 'flask', 'Senescence',  '298')}
      </div>

      <div className="nav-section">
        <p className="heading">Results</p>
        {item('compare', 'chart',  'Compare models')}
        {item('gap',     'chart',  'Gap analysis')}
        {item('matrix',  'table',  'Eval matrix')}
        {item('answers', 'table',  'Answers')}
      </div>

      <div className="nav-section">
        <p className="heading">Reasoning</p>
        {item('trust',   'target', 'Trust & traces')}
      </div>

      <div className="nav-section">
        <p className="heading">System</p>
        {item('runs',     'play',     'Live runs', liveCount, true)}
        {item('settings', 'settings', 'Settings')}
      </div>

      <div className="footer">
        Caltech Longevity Hackathon · Track 01
        <div className="sponsor">
          <span style={{ color: 'var(--lb-fg-3)' }}>Sponsor</span>
          <img src="public/insilico-medicine-logo.svg" alt="Insilico Medicine" />
        </div>
      </div>
    </aside>
  );
};

Object.assign(window, { Sidebar });
