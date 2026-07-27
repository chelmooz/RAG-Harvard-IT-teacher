import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { healthService, documentService } from '../services/api';
import { S, cyan, muted, mutedDim, statusTag, inputBtn, brandGlow } from '../styles/shared';

const RECENT_FILES = ['rapport_secu_2024.pdf', 'architecture_reseau.md', 'logs_Q3.csv', 'procedures.docx'];

const SUGGESTIONS = [
  'Résume les derniers rapports de sécurité',
  'Quelles vulnérabilités ont été détectées ?',
  'Compare les métriques Q2 vs Q3',
  "Génère un rapport d'audit",
];

const leftSidebar = {
  width: 240,
  borderRight: '1px solid rgba(0,229,204,0.1)',
  ...S.sidebar,
};
const centerCol = { flex: 1, ...S.flexCol, overflow: 'hidden' };
const centerTop = {
  padding: '12px 20px',
  borderBottom: '1px solid rgba(0,229,204,0.1)',
  ...S.flexBetween, alignItems: 'center',
};
const centerCont = {
  flex: 1, ...S.flexCol, alignItems: 'center',
  justifyContent: 'center', padding: 40,
};
const rightSide = {
  width: 260,
  borderLeft: '1px solid rgba(0,229,204,0.1)',
  ...S.sidebar,
};
const suggestionBox = {
  border: '1px solid rgba(0,229,204,0.15)',
  padding: '14px 16px', cursor: 'pointer', fontSize: 12,
  color: 'rgba(255,255,255,0.55)',
  ...S.flexCenter, gap: 8, transition: 'all 0.2s',
};
const logRow = {
  ...S.flex, gap: 10, marginBottom: 10,
  fontSize: 11, alignItems: 'flex-start',
};

export default function Dashboard() {
  const nav = useNavigate();
  const [time, setTime] = useState(new Date());
  const [health, setHealth] = useState(null);
  const [docStats, setDocStats] = useState(null);
  const [log, setLog] = useState([
    { t: '--:--', dot: false, msg: 'Waiting for backend...' },
  ]);
  const [input, setInput] = useState('');

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const h = await healthService.checkHealth();
        setHealth(h);
        setLog(prev => [{ t: new Date().toLocaleTimeString(), dot: false, msg: 'System online' }, ...prev.slice(0, 4)]);
      } catch {
        setLog(prev => [{ t: '--:--', dot: true, msg: 'Backend unreachable' }, ...prev.slice(0, 4)]);
      }
    };
    const fetchDocs = async () => {
      try {
        const d = await documentService.listDocuments();
        setDocStats(d);
      } catch {
        // silent
      }
    };
    fetchHealth();
    fetchDocs();
  }, []);

  useEffect(() => {
    const id = setInterval(() => setTime(new Date()), 10000);
    return () => clearInterval(id);
  }, []);

  const hh = String(time.getHours()).padStart(2, '0');
  const mm = String(time.getMinutes()).padStart(2, '0');
  const statusColor = health?.status === 'healthy' ? '#00ff88' : '#ff6b35';
  const docCount = docStats?.length
    ? `${docStats.reduce((a, d) => a + d.chunks, 0)}`
    : '...';
  const recentStyle = {
    fontSize: 11, color: 'rgba(255,255,255,0.5)',
    padding: '5px 0',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    cursor: 'pointer', ...S.flexCenter, gap: 6,
  };
  const statusDot = {
    width: 8, height: 8, borderRadius: '50%',
    background: '#ff6b35', boxShadow: '0 0 8px #ff6b35',
    display: 'inline-block',
  };
  const h2Glow = {
    fontFamily: 'Rajdhani', fontSize: 28, letterSpacing: 4,
    marginBottom: 12, ...cyan,
    textShadow: '0 0 20px rgba(0,229,204,0.4)',
  };
  const descStyle = {
    fontSize: 12, color: 'rgba(255,255,255,0.4)',
    textAlign: 'center', lineHeight: 1.8,
    maxWidth: 400, marginBottom: 40,
  };
  const modelStyle = {
    color: 'rgba(255,255,255,0.8)',
    fontFamily: 'Rajdhani', fontWeight: 600, fontSize: 14,
  };
  const uploadBox = {
    border: '1px dashed rgba(0,229,204,0.2)',
    padding: '24px 16px', textAlign: 'center',
    cursor: 'pointer', fontSize: 11,
    color: 'rgba(255,255,255,0.35)',
    lineHeight: 2, transition: 'all 0.2s',
  };
  const sysRows = [
    { k: '⬡ Statut', v: health?.status || '...', color: statusColor },
    { k: '⊟ GPU', v: health?.gpu?.includes('ok') ? 'ROCm' : 'cpu', color: 'rgba(255,255,255,0.7)' },
    { k: '◈ Vectors', v: docCount, color: 'rgba(255,255,255,0.7)' },
    { k: '⚡ Modèle', v: health?.ollama?.split(' ')[0] || '...', color: '#00e5cc' },
  ];

  return (
    <div style={S.page}>

      <div style={S.topbar}>
        <span style={brandGlow}>
          PROF_IA
        </span>
        <span style={mutedDim}>ctOS DASHBOARD // LOCAL RAG SYSTEM</span>
        <div style={{ flex: 1 }} />
        <span style={statusTag}>● SYSTEM ONLINE</span>
        <span style={{ ...cyan, fontSize: 13, letterSpacing: 2 }}>{hh}:{mm}</span>
      </div>

      <div style={{ flex: 1, ...S.flex, overflow: 'hidden' }}>

        <div style={leftSidebar}>
          <div>
            <div className="label">Système</div>
            {sysRows.map(({ k, v, color }) => (
              <div key={k} style={{ ...S.flexBetween, marginBottom: 8 }}>
                <span style={muted}>{k}</span>
                <span style={{ color }}>{v}</span>
              </div>
            ))}
            <div style={{ textAlign: 'right', color: 'rgba(0,229,204,0.25)', fontSize: 14, marginTop: 2 }}>┘</div>
          </div>

          <div>
            <div className="label">Performance</div>
            {[
              { k: 'CPU', v: 45, color: '#00e5cc' },
              { k: 'GPU', v: 78, color: '#00e5cc' },
              { k: 'VRAM', v: 62, color: '#ff2d78' },
            ].map(({ k, v, color }) => (
              <div key={k} style={{ marginBottom: 12 }}>
                <div style={{ ...S.flexBetween, marginBottom: 4 }}>
                  <span style={muted}>{k}</span>
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
              <div key={f} style={recentStyle}
                onMouseEnter={e => e.currentTarget.style.color = '#00e5cc'}
                onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.5)'}>
                <span style={{ color: 'rgba(0,229,204,0.4)', fontSize: 10 }}>⊟</span> {f}
              </div>
            ))}
          </div>
        </div>

        <div style={centerCol}>
          <div style={centerTop}>
            <span style={{ letterSpacing: 3, fontSize: 11, color: 'rgba(255,255,255,0.6)' }}>INTERFACE DE REQUÊTE</span>
            <span style={statusDot} />
          </div>

          <div style={centerCont}>
            <div style={{ fontSize: 32, marginBottom: 16, color: '#00e5cc', opacity: 0.7 }}>◎</div>
            <h2 style={h2Glow}>
              PROF_IA RAG
            </h2>
            <p style={descStyle}>
              Système d'interrogation locale de documents.<br />
              Vos données restent sur votre machine.<br />
              Aucune donnée n'est transmise à l'extérieur.
            </p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, width: '100%', maxWidth: 600 }}>
              {SUGGESTIONS.map(s => {
                const onEnter = e => { e.currentTarget.style.borderColor = 'rgba(0,229,204,0.4)'; e.currentTarget.style.color = cyan.color; };
                const onLeave = e => { e.currentTarget.style.borderColor = 'rgba(0,229,204,0.15)'; e.currentTarget.style.color = 'rgba(255,255,255,0.55)'; };
                return (
                  <div key={s} onClick={() => nav('/terminal')}
                    style={suggestionBox}
                    onMouseEnter={onEnter}
                    onMouseLeave={onLeave}>
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
              <button onClick={() => nav('/terminal')} style={inputBtn}>›</button>
            </div>
          </div>
        </div>

        <div style={rightSide}>
          <div>
            <div className="label">Activité réseau</div>
            {log.map(({ t, dot, msg }, i) => (
              <div key={i} style={logRow}>
                <span style={{ color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>{t}</span>
                {dot && <span className="dot dot-orange" style={{ marginTop: 4, flexShrink: 0 }} />}
                <span style={{ color: dot ? '#ff6b35' : 'rgba(255,255,255,0.55)' }}>{msg}</span>
              </div>
            ))}
          </div>

          <div>
            <div className="label">Upload</div>
            <div style={uploadBox}
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
              <div style={modelStyle}>{health?.ollama || 'qwen3:14b'}</div>
              <div style={{ color: 'rgba(255,255,255,0.4)' }}>{health?.embedding_model || 'BAAI/bge-m3'}</div>
              <div style={{ color: 'rgba(255,255,255,0.4)' }}>Temp: 0.3 | Top-P: 0.9</div>
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
