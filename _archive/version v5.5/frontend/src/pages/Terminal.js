/**
 * Terminal.js - VERSION CORRIGÉE avec intégration API
 * À remplacer dans : /frontend/src/pages/Terminal.js
 */

import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatService } from '../services/api';

const SESSIONS = ['Recherche sécu', 'Audit infra', 'Documentation API'];

export default function Terminal() {
  const nav = useNavigate();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    { role: 'sys', text: '[SYS] ctOS_RAG v5.5 initializing...' }
  ]);
  const [loading, setLoading] = useState(false);
  const [connected, setConnected] = useState(false);
  const [sessionId] = useState(() => `session-${Date.now()}`);
  const bottomRef = useRef(null);

  // Vérifier la connexion au backend au démarrage
  useEffect(() => {
    const checkConnection = async () => {
      try {
        await chatService.getHistory(null, null, 1);
        setConnected(true);
        setMessages(prev => [...prev, {
          role: 'sys',
          text: '[SYS] Connected to backend. Local knowledge base loaded. Ready.'
        }]);
      } catch (error) {
        setConnected(false);
        setMessages(prev => [...prev, {
          role: 'sys',
          text: `[ERROR] Backend unreachable at 192.168.1.11:8000 — ${error.message}`
        }, {
          role: 'sys',
          text: '[SYS] Verify that backend is running: docker-compose up -d backend'
        }]);
      }
    };
    checkConnection();
  }, []);

  // Auto-scroll vers le bas
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading || !connected) return;
    
    const query = input;
    setInput('');
    setLoading(true);

    // Ajouter le message utilisateur
    setMessages(prev => [...prev, { role: 'user', text: query }]);

    try {
      // Appel API réel au backend
      const response = await chatService.sendMessage(query, sessionId);
      
      // Construire la réponse formatée
      const lines = ['ctOS_RAG >'];
      
      if (response.rag_used && response.chunks_retrieved > 0) {
        lines.push(`Recherche effectuée. ${response.chunks_retrieved} chunks trouvés.`);
        lines.push('');
        
        // Afficher les sources
        response.sources.forEach((src, i) => {
          lines.push(`> [DOC-${String(i+1).padStart(4, '0')}] ${src.source} (similarité: ${(src.score * 100).toFixed(1)}%)`);
        });
        
        lines.push('');
        lines.push(response.response);
        lines.push('');
        lines.push(`[Traitement: ${response.response_time_ms}ms | Session: ${response.session_id.slice(0, 8)}...]`);
      } else {
        lines.push('Aucun document pertinent trouvé dans la base locale.');
        lines.push('');
        lines.push(response.response);
        lines.push('');
        lines.push(`[Traitement: ${response.response_time_ms}ms | Mode: direct (sans RAG)]`);
      }

      setMessages(prev => [...prev, { role: 'rag', lines }]);
      
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'rag',
        lines: [
          'ctOS_RAG >',
          `[ERROR] ${error.response?.data?.detail || error.message}`,
          '',
          'Statut backend: UNREACHABLE',
          'Action requise: Vérifier docker-compose logs backend',
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
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>v5.5</span>
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

        {/* Top bar */}
        <div style={{ padding: '10px 20px', borderBottom: '1px solid rgba(0,229,204,0.1)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.3)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#00e5cc', opacity: 0.6 }}>›_</span>
            <span style={{ color: '#00e5cc', letterSpacing: 2 }}>ctOS_RAG</span>
            <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 11 }}>v5.5</span>
          </div>
          <div style={{ display: 'flex', gap: 20, fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>
            <span>
              <span className={`dot ${connected ? 'dot-cyan' : 'dot-orange'}`} />
              {connected ? 'BACKEND OK' : 'BACKEND DOWN'}
            </span>
            <span><span className="dot dot-cyan" />LOCAL</span>
            <span><span className="dot dot-cyan" />SECURED</span>
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
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="anim-fade" style={{ color: 'rgba(0,229,204,0.5)', fontSize: 12 }}>
              <span style={{ animation: 'pulse 1.5s infinite' }}>⋯ Traitement en cours...</span>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div style={{ padding: '16px 20px', borderTop: '1px solid rgba(0,229,204,0.1)', background: 'rgba(0,0,0,0.3)' }}>
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
                position: 'absolute', 
                right: 12, 
                top: '50%', 
                transform: 'translateY(-50%)', 
                background: 'none', 
                border: 'none', 
                color: connected && !loading ? '#00e5cc' : 'rgba(255,255,255,0.3)', 
                cursor: connected && !loading ? 'pointer' : 'not-allowed', 
                fontSize: 18 
              }}
            >
              {loading ? '⋯' : '›'}
            </button>
          </div>
          <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
            <span>⊟ RAG Mode</span>
            <span>Top-K: 5</span>
            <span>Threshold: 0.7</span>
            <span>Backend: 192.168.1.11:8000</span>
          </div>
        </div>
      </div>
    </div>
  );
}
