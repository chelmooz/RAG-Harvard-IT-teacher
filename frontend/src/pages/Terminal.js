import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { chatService, healthService, documentService } from '../services/api';
import { S } from '../styles/shared';

const SESSIONS = ['Recherche sécu', 'Audit infra', 'Documentation API'];

const INIT_MESSAGES = [
  { role: 'sys', text: '[SYS] ctOS_RAG v6.0 initialized. Local knowledge base loaded.' },
];

function Sidebar({ health, docStats, nav }) {
  const sessionStyle = {
    fontSize: 12, color: 'rgba(255,255,255,0.5)',
    padding: '6px 0', cursor: 'pointer',
    ...S.flexCenter, gap: 6,
  };
  return (
    <div style={{
      width: 200,
      borderRight: '1px solid rgba(0,229,204,0.12)',
      padding: '20px 0', ...S.flexCol, background: '#07090a',
    }}>
      <div style={{ padding: '0 16px 20px', borderBottom: '1px solid rgba(0,229,204,0.1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ color: '#00e5cc', fontSize: 12 }}>›_</span>
          <span style={{ color: '#00e5cc', fontSize: 14, letterSpacing: 2 }}>ctOS_RAG</span>
          <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)' }}>v6.0</span>
        </div>
      </div>

      <div style={{ padding: '16px 16px 12px' }}>
        <div className="label">Base de données</div>
        {[
          ['Documents', docStats?.length ?? '...'],
          ['Chunks', docStats?.length ? docStats.reduce((a, d) => a + d.chunks, 0).toLocaleString() : '...'],
          ['Backend', health?.status === 'healthy' ? 'OK' : '...'],
        ].map(([k, v]) => (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: 12 }}>
            <span style={{ color: 'rgba(255,255,255,0.5)' }}>{k}</span>
            <span style={{ color: v === 'OK' ? '#00e5cc' : 'rgba(255,255,255,0.7)' }}>{v}</span>
          </div>
        ))}
        <div style={{ textAlign: 'right', color: 'rgba(0,229,204,0.3)', fontSize: 16, marginTop: 4 }}>┘</div>
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(0,229,204,0.08)' }}>
        <div className="label">Modèle actif</div>
        <div style={{ fontSize: 12, lineHeight: 1.8 }}>
          <span style={{ color: 'rgba(255,255,255,0.7)' }}>{health?.ollama || 'qwen3:14b'}</span><br />
          <span style={{ color: 'rgba(255,255,255,0.4)' }}>{health?.gpu?.includes('ok') ? 'ROCm' : 'CPU'}</span><br />
          <span style={{ color: '#00e5cc' }}>● En ligne</span>
        </div>
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid rgba(0,229,204,0.08)', flex: 1 }}>
        <div className="label">Sessions</div>
        {SESSIONS.map(s => (
          <div key={s}
            style={sessionStyle}
            onMouseEnter={e => e.currentTarget.style.color = '#00e5cc'}
            onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.5)'}>
            <span style={{ color: 'rgba(0,229,204,0.4)' }}>›</span> {s}
          </div>
        ))}
      </div>

      <div className="footer-link"
        onClick={() => nav('/select')}>
        [ DESIGN A — TERMINAL ]
      </div>
    </div>
  );
}

function MessageItem({ msg }) {
  const userBubble = {
    background: 'rgba(0,229,204,0.06)',
    border: '1px solid rgba(0,229,204,0.2)',
    padding: '12px 16px', maxWidth: '55%',
  };
  const ragBubble = {
    background: 'rgba(0,229,204,0.03)',
    border: '1px solid rgba(0,229,204,0.15)',
    padding: 16, maxWidth: '65%',
  };
  const lineColor = (j, line) => {
    if (j === 0) return '#00e5cc';
    if (line.startsWith('>')) return 'rgba(255,255,255,0.75)';
    return 'rgba(255,255,255,0.55)';
  };
  return (
    <div className="anim-fade">
      {msg.role === 'sys' && (
        <p style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12 }}>{msg.text}</p>
      )}
      {msg.role === 'user' && (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <div style={userBubble}>
            <div style={{ fontSize: 10, color: 'rgba(0,229,204,0.5)', marginBottom: 6 }}>user@local ~$</div>
            {msg.text}
          </div>
        </div>
      )}
      {msg.role === 'rag' && (
        <div style={ragBubble}>
          {msg.lines.map((line, j) => (
            <div key={j} style={{
              fontSize: 13, lineHeight: '22px',
              color: lineColor(j, line),
            }}>
              {line || <br />}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function InputBar({ input, setInput, send }) {
  return (
    <div style={{
      padding: '16px 20px',
      borderTop: '1px solid rgba(0,229,204,0.1)',
      background: 'rgba(0,0,0,0.3)',
    }}>
      <div style={{ position: 'relative' }}>
        <input className="ctos-input"
          placeholder="Interroger la base de connaissances..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && send()} />
        <button onClick={send} style={{
          position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
          background: 'none', border: 'none', color: '#00e5cc',
          cursor: 'pointer', fontSize: 18,
        }}>
          ›
        </button>
      </div>
      <div style={{ display: 'flex', gap: 20, marginTop: 8, fontSize: 11, color: 'rgba(255,255,255,0.25)' }}>
        <span>⊟ RAG Mode</span>
        <span>Température: 0.1</span>
        <span>Top-K: 5</span>
      </div>
    </div>
  );
}

export default function Terminal() {
  const nav = useNavigate();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState(INIT_MESSAGES);
  const [health, setHealth] = useState(null);
  const [docStats, setDocStats] = useState(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    healthService.checkHealth().then(setHealth).catch(() => {});
    documentService.listDocuments().then(setDocStats).catch(() => {});
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim()) return;
    const q = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: q }]);

    try {
      const data = await chatService.sendMessage({ query: q });
      const lines = [
        'ctOS_RAG >',
        data.response,
        '',
        ...data.sources.map(s => `> (score: ${s.score}) ${s.source}`),
      ];
      setMessages(prev => [...prev, { role: 'rag', lines }]);
    } catch {
      setMessages(prev => [...prev, { role: 'rag', lines: [
        'ctOS_RAG >',
        'Erreur de connexion au serveur. Vérifiez que le backend est en ligne.',
      ]}]);
    }
  };

  const rootStyle = {
    display: 'flex', height: '100vh', background: '#090b0c',
    fontFamily: 'Share Tech Mono', fontSize: 13,
  };
  const topbarStyle = {
    padding: '10px 20px',
    borderBottom: '1px solid rgba(0,229,204,0.1)',
    ...S.flexBetween, background: 'rgba(0,0,0,0.3)',
  };

  return (
    <div style={rootStyle}>
      <Sidebar health={health} docStats={docStats} nav={nav} />

      <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>

        <div style={topbarStyle}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ color: '#00e5cc', opacity: 0.6 }}>›_</span>
            <span style={{ color: '#00e5cc', letterSpacing: 2 }}>ctOS_RAG</span>
            <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: 11 }}>v6.0</span>
          </div>
          <div style={{ display: 'flex', gap: 20, fontSize: 11, color: 'rgba(255,255,255,0.4)' }}>
            <span><span className="dot dot-cyan" />LOCAL</span>
            <span><span className="dot dot-cyan" />SECURED</span>
            <span><span className="dot dot-green" />GPU ACTIVE</span>
          </div>
        </div>

        <div style={{ flex: 1, padding: 20, overflowY: 'auto', ...S.flexCol, gap: 20 }}>
          {messages.map((msg, i) => (
            <MessageItem key={i} msg={msg} />
          ))}
          <div ref={bottomRef} />
        </div>

        <InputBar input={input} setInput={setInput} send={send} />
      </div>
    </div>
  );
}