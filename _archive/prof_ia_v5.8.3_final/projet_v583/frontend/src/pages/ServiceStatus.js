/**
 * Prof IA v5.8.3 — Composant ServiceStatus
 * =========================================
 * Panneau de contrôle des services Docker depuis le dashboard.
 * 
 * Fonctionnalités :
 *   - Pastilles colorées en temps réel (vert / orange / rouge)
 *   - Boutons Restart / Stop / Start par service
 *   - Rafraîchissement automatique toutes les 30 secondes
 *   - Rafraîchissement manuel
 * 
 * Endpoints utilisés :
 *   GET  /services/status           → état de chaque conteneur
 *   POST /services/{name}/restart   → redémarrer
 *   POST /services/{name}/stop      → arrêter
 *   POST /services/{name}/start     → démarrer
 * 
 * Intégration dans le dashboard existant :
 *   import ServiceStatus from './ServiceStatus';
 *   // Puis dans le JSX : <ServiceStatus token={sessionToken} apiUrl={API_BASE} />
 */

import React, { useState, useEffect, useCallback } from 'react';

// ── Configuration des services affichés ──────────────────────────────────────
const SERVICES_CONFIG = {
  postgres: {
    label:       'PostgreSQL',
    description: 'Base conversations + fine-tuning',
    icon:        '🗄️',
    canStop:     true,   // arrêtable depuis le dashboard
  },
  ollama: {
    label:       'Ollama ROCm',
    description: 'Modèles LLM — Mistral / DeepSeek',
    icon:        '🧠',
    canStop:     true,
  },
  backend: {
    label:       'Backend FastAPI',
    description: 'API RAG + ChromaDB',
    icon:        '⚡',
    canStop:     false,  // arrêter le backend couperait ce composant lui-même
  },
  frontend: {
    label:       'Frontend React',
    description: 'Interface utilisateur',
    icon:        '🖥️',
    canStop:     false,
  },
};

// ── Couleurs des indicateurs ──────────────────────────────────────────────────
const INDICATOR_STYLES = {
  green:   { bg: '#16a34a', text: 'En ligne',    pulse: true  },
  orange:  { bg: '#d97706', text: 'Démarrage…',  pulse: true  },
  red:     { bg: '#dc2626', text: 'Hors ligne',  pulse: false },
  unknown: { bg: '#6b7280', text: 'Inconnu',     pulse: false },
};

// ── Composant principal ───────────────────────────────────────────────────────
export default function ServiceStatus({ token, apiUrl }) {
  const [services,      setServices]      = useState({});
  const [loading,       setLoading]       = useState(true);
  const [lastRefresh,   setLastRefresh]   = useState(null);
  const [actionLoading, setActionLoading] = useState({});  // {serviceName: 'restart'|'stop'|'start'}
  const [error,         setError]         = useState(null);

  // ── Récupérer l'état des services ─────────────────────────────────────────
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiUrl}/services/status`, {
        headers: { 'X-Session-Token': token },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setServices(data);
      setLastRefresh(new Date());
      setError(null);
    } catch (err) {
      setError(`Impossible de contacter l'API : ${err.message}`);
    } finally {
      setLoading(false);
    }
  }, [token, apiUrl]);

  // Chargement initial + rafraîchissement toutes les 30 secondes
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  // ── Action sur un service ─────────────────────────────────────────────────
  const handleAction = async (serviceName, action) => {
    setActionLoading(prev => ({ ...prev, [serviceName]: action }));
    try {
      const res = await fetch(`${apiUrl}/services/${serviceName}/${action}`, {
        method:  'POST',
        headers: { 'X-Session-Token': token },
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      // Attendre 2s puis rafraîchir (le service a besoin d'un instant)
      setTimeout(fetchStatus, 2000);
    } catch (err) {
      setError(`Erreur ${action} sur ${serviceName} : ${err.message}`);
    } finally {
      setActionLoading(prev => {
        const next = { ...prev };
        delete next[serviceName];
        return next;
      });
    }
  };

  // ── Rendu d'une carte service ─────────────────────────────────────────────
  const ServiceCard = ({ name, config }) => {
    const svcData  = services[name] || {};
    const indicator= svcData.indicator || 'unknown';
    const style    = INDICATOR_STYLES[indicator] || INDICATOR_STYLES.unknown;
    const isLoading= !!actionLoading[name];
    const status   = svcData.status || '—';
    const health   = svcData.health && svcData.health !== 'none' ? svcData.health : null;

    return (
      <div style={cardStyle}>
        {/* En-tête : icône + nom + pastille */}
        <div style={cardHeaderStyle}>
          <span style={{ fontSize: '1.4rem' }}>{config.icon}</span>
          <div style={{ flex: 1 }}>
            <div style={cardTitleStyle}>{config.label}</div>
            <div style={cardDescStyle}>{config.description}</div>
          </div>
          {/* Pastille indicateur */}
          <div style={{
            ...dotStyle,
            backgroundColor: style.bg,
            boxShadow: style.pulse ? `0 0 0 4px ${style.bg}33` : 'none',
          }} title={style.text} />
        </div>

        {/* Statut textuel */}
        <div style={statusRowStyle}>
          <span style={{ color: '#9ca3af', fontSize: '0.8rem' }}>Statut</span>
          <span style={{ ...statusTextStyle, color: indicator === 'green' ? '#16a34a' : indicator === 'red' ? '#dc2626' : '#d97706' }}>
            {style.text}
            {health && ` — ${health}`}
            {status !== 'running' && status !== 'not_found' && ` (${status})`}
          </span>
        </div>

        {/* Boutons d'action */}
        <div style={actionsStyle}>
          <ActionButton
            label="Redémarrer"
            emoji="🔄"
            color="#2563eb"
            onClick={() => handleAction(name, 'restart')}
            disabled={isLoading || status === 'not_found'}
            loading={actionLoading[name] === 'restart'}
          />
          {config.canStop && (
            <>
              <ActionButton
                label="Arrêter"
                emoji="⏹"
                color="#dc2626"
                onClick={() => handleAction(name, 'stop')}
                disabled={isLoading || status !== 'running'}
                loading={actionLoading[name] === 'stop'}
              />
              <ActionButton
                label="Démarrer"
                emoji="▶"
                color="#16a34a"
                onClick={() => handleAction(name, 'start')}
                disabled={isLoading || status === 'running'}
                loading={actionLoading[name] === 'start'}
              />
            </>
          )}
        </div>
      </div>
    );
  };

  // ── Bouton d'action réutilisable ─────────────────────────────────────────
  const ActionButton = ({ label, emoji, color, onClick, disabled, loading }) => (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      style={{
        ...btnStyle,
        backgroundColor: disabled ? '#374151' : color,
        opacity: disabled ? 0.5 : 1,
        cursor: disabled ? 'not-allowed' : 'pointer',
      }}
    >
      {loading ? '⏳' : emoji} {label}
    </button>
  );

  // ── Rendu principal ───────────────────────────────────────────────────────
  return (
    <div style={containerStyle}>
      {/* En-tête du panneau */}
      <div style={panelHeaderStyle}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.1rem', color: '#f9fafb' }}>
            🖥️  Services BC-250
          </h2>
          {lastRefresh && (
            <p style={{ margin: 0, fontSize: '0.75rem', color: '#6b7280' }}>
              Mis à jour : {lastRefresh.toLocaleTimeString('fr-FR')} — rafraîchissement auto 30s
            </p>
          )}
        </div>
        <button
          onClick={fetchStatus}
          disabled={loading}
          style={{ ...btnStyle, backgroundColor: '#4b5563' }}
        >
          {loading ? '⏳' : '🔃'} Actualiser
        </button>
      </div>

      {/* Message d'erreur */}
      {error && (
        <div style={errorStyle}>⚠️  {error}</div>
      )}

      {/* Grille des cartes services */}
      {loading && Object.keys(services).length === 0 ? (
        <div style={{ textAlign: 'center', color: '#6b7280', padding: '2rem' }}>
          Chargement des services…
        </div>
      ) : (
        <div style={gridStyle}>
          {Object.entries(SERVICES_CONFIG).map(([name, config]) => (
            <ServiceCard key={name} name={name} config={config} />
          ))}
        </div>
      )}

      <p style={{ fontSize: '0.7rem', color: '#4b5563', marginTop: '0.5rem', textAlign: 'center' }}>
        Prof IA v5.8.3 — AMD BC-250 — Cyan Skillfish RDNA2
      </p>
    </div>
  );
}

// ── Styles inline ─────────────────────────────────────────────────────────────
// Inline styles pour ne pas dépendre de fichiers CSS supplémentaires

const containerStyle = {
  backgroundColor: '#111827',
  borderRadius:    '12px',
  padding:         '1.25rem',
  fontFamily:      "'Segoe UI', system-ui, sans-serif",
  color:           '#f9fafb',
  minWidth:        '320px',
};

const panelHeaderStyle = {
  display:         'flex',
  justifyContent:  'space-between',
  alignItems:      'center',
  marginBottom:    '1rem',
  paddingBottom:   '0.75rem',
  borderBottom:    '1px solid #1f2937',
};

const gridStyle = {
  display:             'grid',
  gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
  gap:                 '0.75rem',
};

const cardStyle = {
  backgroundColor: '#1f2937',
  borderRadius:    '8px',
  padding:         '1rem',
  border:          '1px solid #374151',
};

const cardHeaderStyle = {
  display:        'flex',
  alignItems:     'center',
  gap:            '0.75rem',
  marginBottom:   '0.5rem',
};

const cardTitleStyle = {
  fontWeight:  '600',
  fontSize:    '0.95rem',
  color:       '#f9fafb',
};

const cardDescStyle = {
  fontSize:  '0.75rem',
  color:     '#9ca3af',
};

const dotStyle = {
  width:        '14px',
  height:       '14px',
  borderRadius: '50%',
  flexShrink:   0,
  transition:   'background-color 0.3s',
};

const statusRowStyle = {
  display:         'flex',
  justifyContent:  'space-between',
  alignItems:      'center',
  marginBottom:    '0.75rem',
  fontSize:        '0.8rem',
};

const statusTextStyle = {
  fontWeight:  '500',
};

const actionsStyle = {
  display:  'flex',
  gap:      '0.4rem',
  flexWrap: 'wrap',
};

const btnStyle = {
  padding:      '0.3rem 0.65rem',
  borderRadius: '6px',
  border:       'none',
  color:        '#fff',
  fontSize:     '0.78rem',
  fontWeight:   '500',
  cursor:       'pointer',
  transition:   'opacity 0.2s',
};

const errorStyle = {
  backgroundColor: '#7f1d1d',
  border:          '1px solid #dc2626',
  borderRadius:    '6px',
  padding:         '0.6rem 1rem',
  marginBottom:    '0.75rem',
  fontSize:        '0.85rem',
  color:           '#fca5a5',
};
