import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const RECENT_FILES = ['rapport_secu_2024.pdf', 'architecture_reseau.md', 'logs_Q3.csv', 'procedures.docx'];

const SUGGESTIONS = [
  'Résume les derniers rapports de sécurité',
  'Quelles vulnérabilités ont été détectées ?',
  'Compare les métriques Q2 vs Q3',
  "Génère un rapport d'audit",
];

export default function Dashboard() {
  const nav = useNavigate();
  const [time, setTime] = useState(new Date());
  const [log, setLog] = useState([
    { t: '16:42', dot: false, msg: 'Query processed' },
    { t: '16:41', dot: false, msg: 'Embedding generated' },
    { t: '16:40', dot: false, msg: 'Document indexed' },
    { t: '16:38', dot: true,  msg: 'Model loaded' },
    { t: '16:35', dot: false, msg: 'System initialized' },
  ]);
  const [input, setInput] = useState('');

  useEffect(() => {
    const id = setInterval(() => {
      setTime(new Date());
      setLog(prev => {
        const events = ['Query processed', 'Embedding generated', 'Chunk retrieved', 'Cache hit'];
        const now = new Date();
        const t = `${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`;
        return [{ t, dot: Math.random() > 0.7, msg: events[Math.floor(Math.random()*4)] }, ...prev.slice(0,4)];
      });
    }, 4000);
    return () => clearInterval(id);
  }, []);

  const hh = String(time.getHours()).padStart(2,'0');
  const mm = String(time.getMinutes()).padStart(2,'0');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: '#090b0c', fontFamily: 'Share Tech Mono', fontSize: 12 }}>

      {/* Top bar */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid rgba(0,229,204,0.12)', display: 'flex', alignItems: 'center', gap: 16, background: 'rgba(0,0,0,0.4)' }}>
        <span style={{ fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 18, letterSpacing: 4, color: '#00e5cc', textShadow: '0 0 20px rgba(0,229,204,0.4)' }}>PROF_IA</span>
        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 11, letterSpacing: 2 }}>ctOS DASHBOARD // LOCAL RAG SYSTEM</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, background: 'rgba(0,255,136,0.08)', border: '1px solid rgba(0,255,136,0.3)', color: '#00ff88', padding: '3px 10px', letterSpacing: 2 }}>
          ● SYSTEM ONLINE
        </span>
        <span style={{ color: '#00e5cc', fontSize: 13, letterSpacing: 2 }}>{hh}:{mm}</span>
      </div>

      {/* 3 colonnes */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>

        {/* LEFT */}
        <div style={{ width: 240, borderRight: '1px solid rgba(0,229,204,0.1)', padding: 16, display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto', background: '#07090a' }}>

          <div>
            <div className="label">Système</div>
            {[
              { k: '⬡ GPU',     v: '78%',    color: '#00ff88' },
              { k: '⊟ RAM',     v: '6.2 GB', color: 'rgba(255,255,255,0.7)' },
              { k: '◈ Vectors', v: '12,841', color: 'rgba(255,255,255,0.7)' },
              { k: '⚡ Latence', v: '~340ms', color: '#ff6b35' },
            ].map(({ k, v, color }) => (
              <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ color: 'rgba(255,255,255,0.45)' }}>{k}</span>
                <span style={{ color }}>{v}</span>
              </div>
            ))}
            <div style={{ textAlign: 'right', color: 'rgba(0,229,204,0.25)', fontSize: 14, marginTop: 2 }}>┘</div>
          </div>

          <div>
            <div className="label">Performance</div>
            {[
              { k: 'CPU',  v: 45, color: '#00e5cc' },
              { k: 'GPU',  v: 78, color: '#00e5cc' },
              { k: 'VRAM', v: 62, color: '#ff2d78' },
            ].map(({ k, v, color }) => (
              <div key={k} style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ color: 'rgba(255,255,255,0.45)' }}>{k}</span>
                  <span style={{ color }}>{v}%</span>
                </div>
                <div className="bar-track">
                  <div className="bar-fill" style={{ width: `${v}%`, background: color }} />
                </div>
              </div>
            ))}
          </div>

          <div>
            <div className="label">Fichiers récents</div>
            {RECENT_FILES.map(f => (
              <div key={f} style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', padding: '5px 0', borderBottom: '1px solid rgba(255,255,255,0.04)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
                onMouseEnter={e => e.currentTarget.style.color = '#00e5cc'}
                onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.5)'}>
                <span style={{ color: 'rgba(0,229,204,0.4)', fontSize: 10 }}>⊟</span> {f}
              </div>
            ))}
          </div>
        </div>

        {/* CENTER */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(0,229,204,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ letterSpacing: 3, fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>INTERFACE DE REQUÊTE</span>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#ff6b35', boxShadow: '0 0 8px #ff6b35', display: 'inline-block' }} />
          </div>

          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
            <div style={{ fontSize: 32, marginBottom: 16, color: '#00e5cc', opacity: 0.7 }}>◎</div>
            <h2 style={{ fontFamily: 'Rajdhani', fontSize: 28, letterSpacing: 4, marginBottom: 12, color: '#00e5cc', textShadow: '0 0 20px rgba(0,229,204,0.4)' }}>
              PROF_IA RAG
            </h2>
            <p style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', textAlign: 'center', lineHeight: 1.8, maxWidth: 400, marginBottom: 40 }}>
              Système d'interrogation locale de documents.<br />
              Vos données restent sur votre machine.<br />
              Aucune donnée n'est transmise à l'extérieur.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, width: '100%', maxWidth: 600 }}>
              {SUGGESTIONS.map(s => (
                <div key={s} onClick={() => nav('/terminal')}
                  style={{ border: '1px solid rgba(0,229,204,0.15)', padding: '14px 16px', cursor: 'pointer', fontSize: 12, color: 'rgba(255,255,255,0.55)', display: 'flex', alignItems: 'center', gap: 8, transition: 'all 0.2s' }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(0,229,204,0.4)'; e.currentTarget.style.color = '#00e5cc'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,229,204,0.15)'; e.currentTarget.style.color = 'rgba(255,255,255,0.55)'; }}>
                  <span style={{ color: 'rgba(0,229,204,0.4)', fontSize: 11 }}>▣</span> {s}
                </div>
              ))}
            </div>
          </div>

          <div style={{ padding: 16, borderTop: '1px solid rgba(0,229,204,0.1)' }}>
            <div style={{ position: 'relative' }}>
              <input className="ctos-input"
                placeholder="Posez votre question..."
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && nav('/terminal')} />
              <button onClick={() => nav('/terminal')} style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: '#00e5cc', cursor: 'pointer', fontSize: 18 }}>›</button>
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div style={{ width: 260, borderLeft: '1px solid rgba(0,229,204,0.1)', padding: 16, display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto', background: '#07090a' }}>

          <div>
            <div className="label">Activité réseau</div>
            {log.map(({ t, dot, msg }, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 10, fontSize: 11, alignItems: 'flex-start' }}>
                <span style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>{t}</span>
                {dot && <span className="dot dot-orange" style={{ marginTop: 4, flexShrink: 0 }} />}
                <span style={{ color: dot ? '#ff6b35' : 'rgba(255,255,255,0.55)' }}>{msg}</span>
              </div>
            ))}
          </div>

          <div>
            <div className="label">Upload</div>
            <div style={{ border: '1px dashed rgba(0,229,204,0.2)', padding: '24px 16px', textAlign: 'center', cursor: 'pointer', fontSize: 11, color: 'rgba(255,255,255,0.35)', lineHeight: 2, transition: 'all 0.2s' }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'rgba(0,229,204,0.4)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(0,229,204,0.2)'}>
              <div style={{ fontSize: 20, marginBottom: 8 }}>⬆</div>
              Glissez vos fichiers ici<br />
              <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>PDF, MD, TXT, DOCX</span>
            </div>
          </div>

          <div>
            <div className="label">Modèle</div>
            <div style={{ fontSize: 12, lineHeight: 1.9 }}>
              <div style={{ color: 'rgba(255,255,255,0.8)', fontFamily: 'Rajdhani', fontWeight: 600, fontSize: 14 }}>Mistral-7B-Instruct</div>
              <div style={{ color: 'rgba(255,255,255,0.4)' }}>GGUF Q4_K_M</div>
              <div style={{ color: 'rgba(255,255,255,0.4)' }}>Context: 8192 tokens</div>
              <div style={{ color: 'rgba(255,255,255,0.4)' }}>Temp: 0.1 | Top-P: 0.9</div>
            </div>
          </div>

          <div style={{ marginTop: 'auto', fontSize: 10, color: 'rgba(255,255,255,0.2)', cursor: 'pointer' }}
            onClick={() => nav('/select')}>
            [ DESIGN B — DASHBOARD ]
          </div>
        </div>
      </div>
    </div>
  );
}