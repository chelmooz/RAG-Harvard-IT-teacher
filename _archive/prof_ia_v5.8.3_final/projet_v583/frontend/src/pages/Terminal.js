/**
 * Terminal.js v5.7 — Prof IA Harvard
 * Ajouts v5.7 :
 *   - Sélecteur de modèle : Mistral 7B ↔ DeepSeek R1 7B
 *   - Notation étoiles (1-5) après chaque réponse IA
 *   - Affichage du modèle actif dans la barre de statut
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatService, ratingService, modelService } from '../services/api';

const SESSIONS = ['Recherche sécu', 'Audit infra', 'Documentation API'];

// ── Composant étoiles de vote ────────────────────────────────────────────────
function StarRating({ conversationId, onRated }) {
  const [hovered, setHovered]   = useState(0);
  const [selected, setSelected] = useState(0);
  const [loading, setLoading]   = useState(false);
  const [saved, setSaved]       = useState(false);

  if (!conversationId) return null;
  if (saved) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 10, fontSize: 11, color: 'rgba(255,215,0,0.7)' }}>
        {'⭐'.repeat(selected)}
        <span style={{ color: 'rgba(255,255,255,0.3)', marginLeft: 4 }}>Note enregistrée — merci !</span>
      </div>
    );
  }

  const handleRate = async (stars) => {
    setLoading(true);
    try {
      await ratingService.rateConversation(conversationId, stars);
      setSelected(stars);
      setSaved(true);
      if (onRated) onRated(stars);
    } catch (e) {
      console.error('Erreur notation:', e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginRight: 4 }}>
        Cette réponse était :
      </span>
      {[1, 2, 3, 4, 5].map(star => (
        <button
          key={star}
          onClick={() => !loading && handleRate(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          disabled={loading}
          title={['', 'Très mauvaise', 'Mauvaise', 'Moyenne', 'Bonne', 'Excellente'][star]}
          style={{
            background: 'none',
            border: 'none',
            cursor: loading ? 'wait' : 'pointer',
            fontSize: 18,
            padding: '0 2px',
            color: star <= (hovered || selected) ? '#FFD700' : 'rgba(255,255,255,0.2)',
            transition: 'color 0.15s',
            lineHeight: 1,
          }}
        >
          ★
        </button>
      ))}
      {loading && <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', marginLeft: 4 }}>...</span>}
    </div>
  );
}

// ── Composant sélecteur de modèle ────────────────────────────────────────────
function ModelSelector({ currentModel, onSwitch }) {
  const [models, setModels]     = useState([]);
  const [open, setOpen]         = useState(false);
  const [switching, setSwitching] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    modelService.getAvailableModels()
      .then(data => setModels(data.models || []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSwitch = async (modelId) => {
    if (modelId === currentModel) { setOpen(false); return; }
    setSwitching(true);
    try {
      await modelService.switchModel(modelId);
      onSwitch(modelId);
    } catch (e) {
      console.error('Erreur switch modèle:', e);
    } finally {
      setSwitching(false);
      setOpen(false);
    }
  };

  const label = currentModel.includes('deepseek') ? 'DeepSeek R1' : 'Mistral 7B';
  const icon  = currentModel.includes('deepseek') ? '🧠' : '⚡';

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        disabled={switching}
        style={{
          background: 'rgba(0,229,204,0.08)',
          border: '1px solid rgba(0,229,204,0.25)',
          color: switching ? 'rgba(255,255,255,0.4)' : '#00e5cc',
          cursor: switching ? 'wait' : 'pointer',
          padding: '4px 10px',
          fontSize: 11,
          letterSpacing: 1,
          display: 'flex',
          alignItems: 'center',
          gap: 6,
        }}
      >
        <span>{icon}</span>
        <span>{switching ? 'Chargement...' : label}</span>
        <span style={{ opacity: 0.5 }}>▾</span>
      </button>

      {open && (
        <div style={{
          position: 'absolute',
          top: '100%',
          right: 0,
          marginTop: 4,
          background: '#0d1117',
          border: '1px solid rgba(0,229,204,0.2)',
          minWidth: 280,
          zIndex: 100,
          boxShadow: '0 8px 24px rgba(0,0,0,0.6)',
        }}>
          <div style={{ padding: '8px 12px', fontSize: 10, color: 'rgba(255,255,255,0.3)', borderBottom: '1px solid rgba(0,229,204,0.1)', letterSpacing: 2 }}>
            CHOISIR LE MODÈLE IA
          </div>
          {models.map(m => (
            <div
              key={m.id}
              onClick={() => handleSwitch(m.id)}
              style={{
                padding: '12px 14px',
                cursor: 'pointer',
                borderBottom: '1px solid rgba(255,255,255,0.05)',
                background: m.id === currentModel ? 'rgba(0,229,204,0.07)' : 'transparent',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(0,229,204,0.05)'}
              onMouseLeave={e => e.currentTarget.style.background = m.id === currentModel ? 'rgba(0,229,204,0.07)' : 'transparent'}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: m.id === currentModel ? '#00e5cc' : 'white', fontWeight: m.id === currentModel ? 'bold' : 'normal', fontSize: 13 }}>
                  {m.id.includes('deepseek') ? '🧠' : '⚡'} {m.name}
                </span>
                {m.id === currentModel && (
                  <span style={{ fontSize: 10, color: '#00ff88', background: 'rgba(0,255,136,0.1)', padding: '2px 6px' }}>ACTIF</span>
                )}
              </div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginTop: 4 }}>{m.description}</div>
              <div style={{ display: 'flex', gap: 12, marginTop: 6 }}>
                <span style={{ fontSize: 10, color: 'rgba(0,229,204,0.6)' }}>💾 {m.vram_gb} Go VRAM</span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>⏱ {m.latency}</span>
              </div>
            </div>
          ))}
          <div style={{ padding: '8px 12px', fontSize: 10, color: 'rgba(255,255,255,0.25)' }}>
            ⚠️ Le changement prend effet à la prochaine question
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page Terminal principale ─────────────────────────────────────────────────
export default function Terminal() {
  const nav = useNavigate();
  const [input, setInput]       = useState('');
  const [messages, setMessages] = useState([
    { role: 'sys', text: '[SYS] ctOS_RAG v5.7 initializing...' }
  ]);
  const [loading, setLoading]   = useState(false);
  const [connected, setConnected] = useState(false);
  const [sessionId]             = useState(() => `session-${Date.now()}`);
  const [currentModel, setCurrentModel] = useState('mistral:7b-instruct-q4_K_M');
  const [queryMode, setQueryMode]       = useState('précis');
  const bottomRef = useRef(null);

  // Vérifier la connexion au backend + récupérer le modèle actif
  useEffect(() => {
    const init = async () => {
      try {
        await chatService.getHistory(null, null, 1);
        setConnected(true);
        setMessages(prev => [...prev, {
          role: 'sys',
          text: '[SYS] Connected to backend. Local knowledge base loaded. Ready.'
        }]);
        // Récupérer le modèle actif depuis le backend
        const modelsData = await modelService.getAvailableModels();
        setCurrentModel(modelsData.current_model || 'mistral:7b-instruct-q4_K_M');
      } catch (error) {
        setConnected(false);
        setMessages(prev => [...prev,
          { role: 'sys', text: `[ERROR] Backend unreachable — ${error.message}` },
          { role: 'sys', text: "[SYS] Verify: docker compose up -d backend" }
        ]);
      }
    };
    init();
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading || !connected) return;
    const query = input;
    setInput('');
    setLoading(true);
    setMessages(prev => [...prev, { role: 'user', text: query }]);

    try {
      const response = await chatService.sendMessage(query, sessionId, null, null, 0.72, queryMode);
      const modelLabel = response.model_used?.includes('deepseek') ? '🧠 DeepSeek R1' : '⚡ Mistral 7B';
      const modeEmoji  = {'précis': '🎯', 'explore': '🔍', 'synthèse': '📚'}[response.mode_used || queryMode] || '🎯';
      const modeLabel  = response.mode_used || queryMode;
      const lines = ['ctOS_RAG >'];

      if (response.rag_used && response.chunks_retrieved > 0) {
        lines.push(`Recherche effectuée. ${response.chunks_retrieved} chunks trouvés.`);
        lines.push('');
        response.sources.forEach((src, i) => {
          lines.push(`> [DOC-${String(i+1).padStart(4,'0')}] ${src.source} (similarité: ${(src.score * 100).toFixed(1)}%)`);
        });
        lines.push('');
        lines.push(response.response);
        lines.push('');
        lines.push(`[${response.response_time_ms}ms | ${modelLabel} | ${modeEmoji} mode:${modeLabel} | ${response.chunks_retrieved} sources]`);
      } else {
        lines.push('Aucun document pertinent trouvé dans la base locale.');
        lines.push('');
        lines.push(response.response);
        lines.push('');
        lines.push(`[${response.response_time_ms}ms | ${modelLabel} | Mode: direct (sans RAG)]`);
      }

      setMessages(prev => [...prev, {
        role: 'rag',
        lines,
        conversationId: response.conversation_id,
      }]);
      if (response.model_used) setCurrentModel(response.model_used);

    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'rag',
        lines: [
          'ctOS_RAG >',
          `[ERROR] ${error.response?.data?.detail || error.message}`,
          '',
          'Statut backend: UNREACHABLE',
          'Action: Vérifier docker compose logs backend',
        ]
      }]);
      setConnected(false);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: 'flex', height: '100vh', background: '#090b0c', fontFamily: 'Share Tech Mono', fontSize: 13 }}>

      {/* Sidebar */}
      <div style={{ width: 200, borderRight: '1px solid rgba(0,229,204,0.12)', padding: '20px 0', display: 'flex', flexDirection: 'column', background: '#07090a' }}>
        <div style={{ padding: '0 16px 20px', borderBottom: '1px solid rgba(0,229,204,0.1)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ color: '#00e5cc', fontSize: 12 }}>›_</span>
            <span style={{ color: '#00e5cc', fontSize: 14, letterSpacing: 2 }}>ctOS_RAG</span>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>v5.7</span>
          </div>
        </div>

        <div style={{ padding: '16px 16px 12px' }}>
          <div className="label">Connexion</div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <span className={`dot ${connected ? 'dot-green' : 'dot-orange'}`} />
            <span style={{ fontSize: 11, color: connected ? '#00ff88' : '#ff6b35' }}>
              {connected ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>

          <div className="label">Session active</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', wordBreak: 'break-all' }}>
            {sessionId.slice(0, 16)}...
          </div>
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(0,229,204,0.08)' }}>
          <div className="label">Messages</div>
          <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.7)' }}>
            Total: {messages.filter(m => m.role === 'user').length}
          </div>
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(0,229,204,0.08)', flex: 1 }}>
          <div className="label">Sessions</div>
          {SESSIONS.map(s => (
            <div key={s}
              style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', padding: '6px 0', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}
              onMouseEnter={e => e.currentTarget.style.color = '#00e5cc'}
              onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.5)'}>
              <span style={{ color: 'rgba(0,229,204,0.4)' }}>›</span> {s}
            </div>
          ))}
        </div>

        <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(0,229,204,0.08)', fontSize: 10, color: 'rgba(255,255,255,0.2)', cursor: 'pointer' }}
          onClick={() => nav('/select')}>
          [ DESIGN A — TERMINAL ]
        </div>
      </div>

      {/* Main */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>

        {/* Top bar — avec sélecteur de modèle */}
        <div style={{ padding: '8px 20px', borderBottom: '1px solid rgba(0,229,204,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#00e5cc', opacity: 0.6 }}>›_</span>
            <span style={{ color: '#00e5cc', letterSpacing: 2 }}>ctOS_RAG</span>
            <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 11 }}>v5.7</span>
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
            {/* Sélecteur de modèle */}
            <ModelSelector
              currentModel={currentModel}
              onSwitch={(m) => {
                setCurrentModel(m);
                const label = m.includes('deepseek') ? 'DeepSeek R1 7B 🧠' : 'Mistral 7B ⚡';
                setMessages(prev => [...prev, {
                  role: 'sys',
                  text: `[SYS] Modèle changé → ${label} (actif à la prochaine question)`
                }]);
              }}
            />
            <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>
              <span>
                <span className={`dot ${connected ? 'dot-cyan' : 'dot-orange'}`} />
                {connected ? 'BACKEND OK' : 'BACKEND DOWN'}
              </span>
              <span><span className="dot dot-cyan" />LOCAL</span>
            </div>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, padding: 20, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {messages.map((msg, i) => (
            <div key={i} className="anim-fade">
              {msg.role === 'sys' && (
                <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>{msg.text}</p>
              )}
              {msg.role === 'user' && (
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <div style={{ background: 'rgba(0,229,204,0.06)', border: '1px solid rgba(0,229,204,0.2)', padding: '12px 16px', maxWidth: '55%' }}>
                    <div style={{ fontSize: 10, color: 'rgba(0,229,204,0.5)', marginBottom: 6 }}>user@local ~$</div>
                    {msg.text}
                  </div>
                </div>
              )}
              {msg.role === 'rag' && (
                <div style={{ background: 'rgba(0,229,204,0.03)', border: '1px solid rgba(0,229,204,0.15)', padding: 16, maxWidth: '75%' }}>
                  {msg.lines.map((line, j) => (
                    <div key={j} style={{
                      fontSize: 13, lineHeight: '22px',
                      color: j === 0 ? '#00e5cc' : line.startsWith('>') ? 'rgba(255,255,255,0.75)' : line.startsWith('[') ? 'rgba(255,255,255,0.4)' : 'rgba(255,255,255,0.65)',
                      fontStyle: line.startsWith('[ERROR]') ? 'italic' : 'normal',
                    }}>
                      {line || <br />}
                    </div>
                  ))}
                  {/* ⭐ Notation étoiles après chaque réponse */}
                  <StarRating
                    conversationId={msg.conversationId}
                    onRated={(stars) => console.log(`Conversation notée ${stars}/5`)}
                  />
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="anim-fade" style={{ color: 'rgba(0,229,204,0.5)', fontSize: 12 }}>
              <span style={{ animation: 'pulse 1.5s infinite' }}>
                {currentModel.includes('deepseek')
                ? (queryMode === 'synthèse' ? '🧠 Raisonnement approfondi...' : '🧠 Raisonnement...')
                : (queryMode === 'synthèse' ? '📚 Synthèse multi-sources...' : queryMode === 'explore' ? '🔍 Exploration diversifiée...' : '⋯ Traitement...')}
              </span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ padding: '12px 20px 16px', borderTop: '1px solid rgba(0,229,204,0.1)', background: 'rgba(0,0,0,0.3)' }}>

          {/* Sélecteur de mode RAG — v5.7 */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 10, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', letterSpacing: 1, marginRight: 4 }}>MODE</span>
            {[
              { key: 'précis',   icon: '🎯', label: 'Précis',   sub: 'top-5 rapide',        tip: 'Question directe ~0.5s' },
              { key: 'explore',  icon: '🔍', label: 'Explore',  sub: 'top-12 + diversité',  tip: 'Plusieurs angles ~1.5s' },
              { key: 'synthèse', icon: '📚', label: 'Synthèse', sub: 'top-20 + multi-query', tip: 'Vue complète ~4-6s' },
            ].map(m => (
              <button
                key={m.key}
                onClick={() => setQueryMode(m.key)}
                title={m.tip}
                style={{
                  background:    queryMode === m.key ? 'rgba(0,229,204,0.12)' : 'rgba(255,255,255,0.03)',
                  border:        `1px solid ${queryMode === m.key ? 'rgba(0,229,204,0.5)' : 'rgba(255,255,255,0.1)'}`,
                  color:         queryMode === m.key ? '#00e5cc' : 'rgba(255,255,255,0.4)',
                  cursor:        'pointer',
                  padding:       '5px 12px',
                  fontSize:      11,
                  display:       'flex',
                  alignItems:    'center',
                  gap:           5,
                  transition:    'all 0.15s',
                }}
              >
                <span>{m.icon}</span>
                <span style={{ fontWeight: queryMode === m.key ? 'bold' : 'normal' }}>{m.label}</span>
                <span style={{ fontSize: 9, opacity: 0.6, display: queryMode === m.key ? 'inline' : 'none' }}>{m.sub}</span>
              </button>
            ))}
            {queryMode === 'synthèse' && (
              <span style={{ fontSize: 10, color: 'rgba(255,215,0,0.6)', marginLeft: 4 }}>
                ⚠ Multi-query · 16k ctx · 4-6s
              </span>
            )}
          </div>

          <div style={{ position: 'relative' }}>
            <input
              className="ctos-input"
              placeholder={connected ? "Interroger la base de connaissances..." : "Backend déconnecté..."}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && send()}
              disabled={!connected || loading}
            />
            <button
              onClick={send}
              disabled={!connected || loading}
              style={{
                position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none',
                color: connected && !loading ? '#00e5cc' : 'rgba(255,255,255,0.3)',
                cursor: connected && !loading ? 'pointer' : 'not-allowed', fontSize: 18
              }}
            >
              {loading ? '⋯' : '›'}
            </button>
          </div>
          <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
            <span>⊟ RAG Mode</span>
            <span>Top-K: 5</span>
            <span>Threshold: 0.72</span>
            <span>{currentModel.includes('deepseek') ? '🧠 DeepSeek R1 7B' : '⚡ Mistral 7B'}</span>
            <span style={{color: queryMode==='synthèse'?'#7DDFFF':queryMode==='explore'?'#A0FFB8':'rgba(255,255,255,0.25)'}}>
              {{'précis':'🎯 Précis','explore':'🔍 Explore','synthèse':'📚 Synthèse'}[queryMode]}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
