export const flex = { display: 'flex' };
export const flexCol = { display: 'flex', flexDirection: 'column' };
export const flexCenter = { display: 'flex', alignItems: 'center' };
export const flexBetween = { display: 'flex', justifyContent: 'space-between' };

export const page = {
  minHeight: '100vh', display: 'flex', flexDirection: 'column',
  alignItems: 'center', justifyContent: 'center', padding: 24,
  position: 'relative',
};
export const pageRow = {
  height: '100vh', background: '#090b0c', display: 'flex',
  fontFamily: 'Share Tech Mono', fontSize: 13,
};

export const topbar = {
  padding: '10px 20px',
  borderBottom: '1px solid rgba(0,229,204,0.12)',
  display: 'flex', alignItems: 'center', gap: 16,
  background: 'rgba(0,0,0,0.4)',
};

export const sidebar = {
  padding: 16, display: 'flex', flexDirection: 'column', gap: 16,
  overflowY: 'auto', background: '#07090a',
};

export const cyan = { color: '#00e5cc' };
export const muted = { color: 'rgba(255,255,255,0.45)' };
export const mutedDim = { color: 'rgba(255,255,255,0.3)', fontSize: 11, letterSpacing: 2 };
export const statusTag = {
  fontSize: 10,
  background: 'rgba(0,255,136,0.08)',
  border: '1px solid rgba(0,255,136,0.3)',
  color: '#00ff88', padding: '3px 10px', letterSpacing: 2,
};

export const inputBtn = {
  position: 'absolute', right: 12, top: '50%',
  transform: 'translateY(-50%)',
  background: 'none', border: 'none',
  color: '#00e5cc', cursor: 'pointer', fontSize: 18,
};

export const chip = {
  fontFamily: 'Share Tech Mono',
  fontSize: 11, padding: '6px 14px',
  background: 'transparent',
  border: '1px solid rgba(255,255,255,0.2)',
  borderRadius: 20,
  color: 'rgba(255,255,255,0.55)',
  cursor: 'pointer', transition: 'all 0.2s', letterSpacing: 0.5,
};

export const brandGlow = {
  fontFamily: 'Rajdhani', fontWeight: 700, fontSize: 18,
  letterSpacing: 4, ...cyan,
  textShadow: '0 0 20px rgba(0,229,204,0.4)',
};

export const S = {
  flex, flexCol, flexCenter, flexBetween,
  page, pageRow, topbar, sidebar,
  cyan, muted, mutedDim, statusTag, inputBtn, chip, brandGlow,
};
