import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

const CHIPS = ['Résumé des rapports', 'Vulnérabilités détectées', 'Métriques Q3', 'Procédures sécurité'];

export default function Minimal() {
  const nav = useNavigate();
  const [input, setInput] = useState('');

  const send = (q) => {
    if (!q.trim()) return;
    nav('/terminal');
  };

  return (
    <div style={{ height: '100vh', background: '#090b0c', display: 'flex', flexDirection: 'column', fontFamily: 'Share Tech Mono', fontSize: 13 }}>

      {/* Header */}
      <div style={{ padding: '16px 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(0,229,204,0.1)' }}>
        <span style={{ fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 18, letterSpacing: 4, color: '#00e5cc' }}>
          PROF_IA
        </span>
        <span onClick={() => nav('/select')}
          style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', cursor: 'pointer', letterSpacing: 2, transition: 'color 0.2s' }}
          onMouseEnter={e => e.target.style.color = '#00e5cc'}
          onMouseLeave={e => e.target.style.color = 'rgba(255,255,255,0.35)'}>
          [RETOUR]
        </span>
      </div>

      <div style={{ height: 1, background: 'linear-gradient(90deg, transparent, rgba(0,229,204,0.1), transparent)' }} />

      {/* Centre */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 40, gap: 24 }}>

        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <div style={{ fontSize: 28, marginBottom: 16, color: 'rgba(255,255,255,0.6)', animation: 'pulse 3s ease-in-out infinite' }}>✦</div>
          <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.55)', letterSpacing: 1 }}>
            Prêt à interroger vos 247 documents
          </p>
        </div>

        {/* Chips */}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', justifyContent: 'center', maxWidth: 600 }}>
          {CHIPS.map(chip => (
            <button key={chip} onClick={() => send(chip)} style={{
              fontFamily: 'Share Tech Mono', fontSize: 11,
              padding: '6px 14px',
              background: 'transparent',
              border: '1px solid rgba(255,255,255,0.2)',
              borderRadius: 20,
              color: 'rgba(255,255,255,0.55)',
              cursor: 'pointer', transition: 'all 0.2s', letterSpacing: 0.5,
            }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#00e5cc'; e.currentTarget.style.color = '#00e5cc'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)'; e.currentTarget.style.color = 'rgba(255,255,255,0.55)'; }}>
              {chip}
            </button>
          ))}
        </div>

        {/* Input */}
        <div style={{ width: '100%', maxWidth: 600, position: 'relative' }}>
          <input className="ctos-input"
            placeholder="Interroger vos documents..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && send(input)} />
          <button onClick={() => send(input)} style={{
            position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
            background: 'none', border: 'none', color: '#00e5cc', cursor: 'pointer', fontSize: 18,
          }}>›</button>
        </div>
      </div>

      {/* Footer */}
      <div style={{ padding: '12px 24px', borderTop: '1px solid rgba(0,229,204,0.08)', display: 'flex', justifyContent: 'center', gap: 20, fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
        <span>⊟ RAG</span>
        <span>•</span>
        <span>Mistral-7B</span>
        <span>•</span>
        <span>Local</span>
      </div>
    </div>
  );
}