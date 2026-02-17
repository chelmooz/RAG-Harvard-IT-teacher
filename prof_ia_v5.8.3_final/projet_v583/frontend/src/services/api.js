/**
 * Prof IA v5.8.3 — Service API centralisé
 * ========================================
 * Centralise tous les appels vers le backend FastAPI.
 * 
 * Ports BC-250 :
 *   Frontend : http://192.168.1.11:3000
 *   Backend  : http://192.168.1.11:8000
 */

import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://192.168.1.11:8000';

// Instance axios avec token de session injecté automatiquement
const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' }
});

// Intercepteur : injecter le token de session sur toutes les requêtes
api.interceptors.request.use(config => {
  const token = localStorage.getItem('session_token');
  if (token) config.headers['X-Session-Token'] = token;
  return config;
});

// Intercepteur : logger les erreurs
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// ═══════════════════════════════════════════════════════════════════
// AUTH
// ═══════════════════════════════════════════════════════════════════
export const authService = {
  async login(username, password) {
    const res = await api.post('/login', { username, password });
    // Stocker le token pour les requêtes suivantes
    if (res.data.token) localStorage.setItem('session_token', res.data.token);
    return res.data;
  },
  async logout() {
    await api.post('/logout');
    localStorage.removeItem('session_token');
  },
};

// ═══════════════════════════════════════════════════════════════════
// SERVICES — Contrôle Docker depuis le dashboard (v5.8.3)
// ═══════════════════════════════════════════════════════════════════
export const servicesService = {
  /**
   * Récupère l'état de tous les conteneurs Docker.
   * Retourne : { postgres: {status, health, indicator}, ollama: {...}, ... }
   * indicator : "green" | "orange" | "red"
   */
  async getStatus() {
    const res = await api.get('/services/status');
    return res.data;
  },

  /** Redémarre un service : postgres | ollama | backend | frontend */
  async restart(serviceName) {
    const res = await api.post(`/services/${serviceName}/restart`);
    return res.data;
  },

  /** Arrête un service */
  async stop(serviceName) {
    const res = await api.post(`/services/${serviceName}/stop`);
    return res.data;
  },

  /** Démarre un service arrêté */
  async start(serviceName) {
    const res = await api.post(`/services/${serviceName}/start`);
    return res.data;
  },
};

// ═══════════════════════════════════════════════════════════════════
// HEALTH
// ═══════════════════════════════════════════════════════════════════
export const healthService = {
  async check() {
    const res = await api.get('/health');
    return res.data;
  },
};

// ═══════════════════════════════════════════════════════════════════
// CHAT / RAG
// ═══════════════════════════════════════════════════════════════════
export const chatService = {
  /**
   * Envoyer une question au système RAG.
   * @param {string} query       Question de l'utilisateur
   * @param {string} sessionId   ID de session (optionnel)
   * @param {string} metier      Filtre : TSSR | AIS | DevOps (optionnel)
   * @param {number} topK        Nombre de chunks (null = auto selon mode)
   * @param {number} threshold   Seuil de similarité (défaut 0.72)
   * @param {string} mode        "précis" | "explore" | "synthèse"
   */
  async sendMessage(query, sessionId = null, metier = null, topK = null, threshold = 0.72, mode = 'précis') {
    const res = await api.post('/chat', {
      query,
      session_id:    sessionId,
      metier,
      top_k:         topK,
      threshold,
      system_prompt: '',
      mode,
    });
    return res.data;
  },

  async getHistory(sessionId = null, metier = null, limit = 20) {
    const params = { limit };
    if (sessionId) params.session_id = sessionId;
    if (metier)    params.metier     = metier;
    const res = await api.get('/chat/history', { params });
    return res.data;
  },

  async rate(conversationId, rating) {
    const res = await api.post(`/chat/${conversationId}/rate`, { rating });
    return res.data;
  },

  async getRatingsStats() {
    const res = await api.get('/chat/ratings/stats');
    return res.data;
  },
};

// ═══════════════════════════════════════════════════════════════════
// MODÈLES
// ═══════════════════════════════════════════════════════════════════
export const modelsService = {
  async getAvailable() {
    const res = await api.get('/models/available');
    return res.data;
  },
  async switchModel(modelId) {
    const res = await api.post('/models/switch', { model_id: modelId });
    return res.data;
  },
};

// ═══════════════════════════════════════════════════════════════════
// DOCUMENTS
// ═══════════════════════════════════════════════════════════════════
export const documentsService = {
  async upload(file, metier = null) {
    const formData = new FormData();
    formData.append('file', file);
    if (metier) formData.append('metier', metier);
    const res = await api.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    });
    return res.data;
  },
  async list() {
    const res = await api.get('/documents/list');
    return res.data;
  },
  async delete(fileId) {
    const res = await api.delete(`/documents/${fileId}`);
    return res.data;
  },
};

// ═══════════════════════════════════════════════════════════════════
// INDEXATION
// ═══════════════════════════════════════════════════════════════════
export const indexingService = {
  async getStats() {
    const res = await api.get('/datasets/stats');
    return res.data;
  },
  async getStatus() {
    const res = await api.get('/indexing/status');
    return res.data;
  },
  async indexDirectory(directory) {
    const res = await api.post('/indexing/directory', null, { params: { directory }, timeout: 300000 });
    return res.data;
  },
};

// ═══════════════════════════════════════════════════════════════════
// DATASET FINE-TUNING
// ═══════════════════════════════════════════════════════════════════
export const datasetService = {
  async getStats() {
    const res = await api.get('/dataset/stats');
    return res.data;
  },
  async export(minRating = 4, format = 'jsonl') {
    const res = await api.post('/dataset/export', null, { params: { min_rating: minRating, format } });
    return res.data;
  },
};

export default api;
