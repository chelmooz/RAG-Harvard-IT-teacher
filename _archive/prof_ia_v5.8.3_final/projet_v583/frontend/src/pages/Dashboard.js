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

  // On définit le style du fond ici pour éviter les erreurs de chemin CSS
  const bgStyle = {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    fontFamily: 'Share Tech Mono',
    fontSize: 12,
    backgroundImage: `url(${process.env.PUBLIC_URL + '/dashboard_bg.png'})`,
    backgroundSize: 'cover',
    backgroundPosition: 'center',
    backgroundColor: '#0a0b0c'
  };

  return (
    <div className="bg-dashboard scanlines" style={bgStyle}>

      {/* TOP BAR */}
      <div style={{ padding: '10px 20px', borderBottom: '1px solid rgba(0,229,204,0.12)', display: 'flex', alignItems: 'center', gap: 16, background: 'rgba(0,0,0,0.7)' }}>
        <span style={{ fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 18, letterSpacing: 4, color: '#00e5cc' }}>PROF_IA</span>
        <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 11, letterSpacing: 2 }}>ctOS DASHBOARD</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: '#00e5cc', fontSize: 13 }}>{hh}:{mm}</span>
      </div>

      <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
        
        {/* LEFT PANEL */}
        <div style={{ width: 240, borderRight: '1px solid rgba(0,229,204,0.1)', padding: 16, background: 'rgba(7,9,10,0.6)' }}>
          <div className="label">Système</div>
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', color: '#00ff88', marginBottom: 5 }}><span>GPU</span><span>78%</span></div>
            <div className="bar-track"><div className="bar-fill" style={{ width: '78%', background: '#00ff88' }} /></div>
          </div>
          <div className="label">Fichiers</div>
          {RECENT_FILES.map(f => (
            <div key={f} style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', padding: '5px 0' }}>{f}</div>
          ))}
        </div>

        {/* CENTER AREA */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'transparent' }}>
          <h2 style={{ fontFamily: 'Rajdhani', fontSize: 32, letterSpacing: 6, color: '#00e5cc', marginBottom: 30 }}>PROF_IA RAG</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 15, width: '100%', maxWidth: 600 }}>
            {SUGGESTIONS.map(s => (
              <div key={s} onClick={() => nav('/terminal')}
                style={{ border: '1px solid rgba(0,229,204,0.3)', padding: '15px', cursor: 'pointer', background: 'rgba(0,0,0,0.5)', color: 'white', textAlign: 'center' }}>
                {s}
              </div>
            ))}
          </div>
        </div>

        {/* RIGHT PANEL */}
        <div style={{ width: 260, borderLeft: '1px solid rgba(0,229,204,0.1)', padding: 16, background: 'rgba(7,9,10,0.6)' }}>
          <div className="label">Activité</div>
          {log.map(({ t, dot, msg }, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 10, fontSize: 11 }}>
              <span style={{ color: 'rgba(255,255,255,0.3)' }}>{t}</span>
              <span style={{ color: dot ? '#ff6b35' : 'white' }}>{msg}</span>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}