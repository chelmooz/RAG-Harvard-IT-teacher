import { useNavigate } from 'react-router-dom';

export default function Landing() {
  const nav = useNavigate();
  return (
    <div className="wdogs-bg scanlines" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: 24, position: 'relative' }}>

      <div style={{ marginBottom: 40, padding: '6px 16px', border: '1px solid rgba(0,229,204,0.3)', fontSize: 11, letterSpacing: 3, color: 'rgba(255,255,255,0.5)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>🔒</span> 100% LOCAL • AUCUNE DONNÉE TRANSMISE
      </div>

      <h1 className="cyan-glow" style={{ fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 'clamp(56px, 10vw, 96px)', letterSpacing: 8, animation: 'flicker 8s infinite' }}>
        PROF_IA
      </h1>

      <p style={{ fontFamily: 'Rajdhani', fontSize: 16, letterSpacing: 6, color: 'rgba(255,255,255,0.5)', marginTop: 8, marginBottom: 16, textTransform: 'uppercase' }}>
        Retrieval Augmented Generation
      </p>

      <p style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)', textAlign: 'center', maxWidth: 420, lineHeight: 1.8, marginBottom: 48 }}>
        Interrogez vos documents en local avec la puissance de l'IA.<br />
        Vos données ne quittent jamais votre machine.
      </p>

      <button className="btn-ctos" onClick={() => nav('/select')}>
        Accéder au système
      </button>

      <div style={{ display: 'flex', gap: 20, marginTop: 64, flexWrap: 'wrap', justifyContent: 'center' }}>
        {[
          { icon: '🔒', title: 'Privé',      desc: 'Vos données restent sur votre machine' },
          { icon: '⚡', title: 'Rapide',      desc: 'Inférence GPU locale optimisée' },
          { icon: '🧠', title: 'Intelligent', desc: 'RAG avec embeddings vectoriels' },
        ].map(({ icon, title, desc }) => (
          <div key={title} style={{ background: 'rgba(0,229,204,0.04)', border: '1px solid rgba(0,229,204,0.15)', padding: '20px 24px', textAlign: 'center', minWidth: 180, maxWidth: 220 }}>
            <div style={{ fontSize: 22, marginBottom: 10 }}>{icon}</div>
            <div style={{ fontFamily: 'Rajdhani', fontWeight: 600, fontSize: 15, letterSpacing: 2, marginBottom: 6 }}>{title}</div>
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', lineHeight: 1.6 }}>{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}