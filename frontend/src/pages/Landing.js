import { useNavigate } from 'react-router-dom';
import { S } from '../styles/shared';

export default function Landing() {
  const nav = useNavigate();
  const badgeStyle = {
  marginBottom: 40, padding: '6px 16px',
  border: '1px solid rgba(0,229,204,0.3)',
  fontSize: 11, letterSpacing: 3,
  color: 'rgba(255,255,255,0.5)',
  ...S.flexCenter, gap: 8,
};
const h1Glow = {
  fontFamily: 'Rajdhani', fontWeight: 700,
  fontSize: 'clamp(56px, 10vw, 96px)',
  letterSpacing: 8, animation: 'flicker 8s infinite',
};
const subtitleStyle = {
  fontFamily: 'Rajdhani', fontSize: 16,
  letterSpacing: 6, color: 'rgba(255,255,255,0.5)',
  marginTop: 8, marginBottom: 16, textTransform: 'uppercase',
};
const descStyle = {
  fontSize: 13, color: 'rgba(255,255,255,0.4)',
  textAlign: 'center', maxWidth: 420,
  lineHeight: 1.8, marginBottom: 48,
};
const cardBase = {
  background: 'rgba(0,229,204,0.04)',
  border: '1px solid rgba(0,229,204,0.15)',
  padding: '20px 24px', textAlign: 'center',
  minWidth: 180, maxWidth: 220,
};
const cardTitle = {
  fontFamily: 'Rajdhani', fontWeight: 600,
  fontSize: 15, letterSpacing: 2, marginBottom: 6,
};

const FEATURES = [
  { icon: '🔒', title: 'Privé', desc: 'Vos données restent sur votre machine' },
  { icon: '⚡', title: 'Rapide', desc: 'Inférence GPU locale optimisée' },
  { icon: '🧠', title: 'Intelligent', desc: 'RAG avec embeddings vectoriels' },
];

function FeatureCard({ icon, title, desc }) {
  return (
    <div style={cardBase}>
      <div style={{ fontSize: 22, marginBottom: 10 }}>{icon}</div>
      <div style={cardTitle}>{title}</div>
      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', lineHeight: 1.6 }}>{desc}</div>
    </div>
  );
}

export default function Landing() {
  const nav = useNavigate();
  return (
    <div className="wdogs-bg scanlines" style={S.page}>

      <div style={badgeStyle}>
        <span>🔒</span> 100% LOCAL • AUCUNE DONNÉE TRANSMISE
      </div>

      <h1 className="cyan-glow" style={h1Glow}>
        PROF_IA
      </h1>

      <p style={subtitleStyle}>
        Retrieval Augmented Generation
      </p>

      <p style={descStyle}>
        Interrogez vos documents en local avec la puissance de l'IA.<br />
        Vos données ne quittent jamais votre machine.
      </p>

      <button className="btn-ctos" onClick={() => nav('/select')}>
        Accéder au système
      </button>

      <div style={{ display: 'flex', gap: 20, marginTop: 64, flexWrap: 'wrap', justifyContent: 'center' }}>
        {FEATURES.map(f => <FeatureCard key={f.title} {...f} />)}
      </div>
    </div>
  );
}