import { useNavigate } from 'react-router-dom';

const DESIGNS = [
  { id: 'A', path: '/terminal',  icon: '>_', title: 'TERMINAL',
    color: 'var(--cyan)',
    desc: 'Interface hacker. Chat façon console avec sidebar de stats. Style terminal minimaliste.' },
  { id: 'B', path: '/dashboard', icon: '⊞',  title: 'DASHBOARD',
    color: 'var(--cyan)',
    desc: 'Interface ctOS complète. Panneaux multiples, métriques système, vue surveillance.' },
  { id: 'C', path: '/minimal',   icon: '✦',  title: 'MINIMAL',
    color: '#ff2d78',
    desc: "Landing page épurée avec transition vers chat. Focus sur l'expérience utilisateur." },
];

export default function DesignPicker() {
  const nav = useNavigate();
  return (
    <div className="wdogs-bg scanlines" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, position: 'relative' }}>

      <div style={{ textAlign: 'center', marginBottom: 56 }}>
        <div style={{ fontSize: 28, marginBottom: 16, color: 'var(--cyan)', opacity: 0.8 }}>◎</div>
        <h1 className="cyan-glow" style={{ fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 64, letterSpacing: 8, animation: 'flicker 8s infinite' }}>
          PROF_IA
        </h1>
        <p style={{ fontFamily: 'Rajdhani', fontSize: 13, letterSpacing: 5, color: 'rgba(255,255,255,0.45)', marginTop: 6 }}>
          RAG LOCAL SYSTEM — DESIGN PREVIEW
        </p>
        <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.35)', marginTop: 8 }}>
          Choisissez un design pour votre interface RAG locale
        </p>
      </div>

      <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap', justifyContent: 'center' }}>
        {DESIGNS.map(({ id, path, icon, title, color, desc }) => (
          <div key={id} onClick={() => nav(path)}
            className="hud-card"
            style={{ width: 260, cursor: 'pointer', transition: 'all 0.25s' }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(0,229,204,0.05)'; e.currentTarget.style.transform = 'translateY(-4px)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(10,15,15,0.85)'; e.currentTarget.style.transform = 'none'; }}>
            <div style={{ fontSize: 28, color, marginBottom: 12, fontFamily: 'Share Tech Mono' }}>{icon}</div>
            <div style={{ fontSize: 10, letterSpacing: 3, color: 'rgba(255,255,255,0.35)', marginBottom: 4 }}>Design {id}</div>
            <div style={{ fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 22, letterSpacing: 3, color, marginBottom: 12 }}>
              {title}
            </div>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.45)', lineHeight: 1.7 }}>{desc}</p>
          </div>
        ))}
      </div>

      <div style={{ position: 'absolute', bottom: 20, fontSize: 10, letterSpacing: 3, color: 'rgba(255,255,255,0.2)' }}>
        PROF_IA v5.5 // ctOS DESIGN SYSTEM // WATCH_DOGS THEME
      </div>
    </div>
  );
}