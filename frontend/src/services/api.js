/**
  * Service API pour Prof IA v6.0
 * Centralise tous les appels au backend FastAPI
 * 
 * À placer dans : /frontend/src/services/api.js
 * 
 * AUTH : Le token API est injecté globalement via l'instance axios.
 * Chaque endpoint listé ici est protégé par le backend (verify_api_token).
 * Voir backend/api/main.py:verify_api_token.
 */

import axios from 'axios';

// Configuration de l'URL backend et token API
// En production, utiliser des variables d'environnement
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8001';
const API_TOKEN = process.env.REACT_APP_API_TOKEN || 'dev-token';
const DEFAULT_TIMEOUT_MS = 30000;

// Instance axios configurée
const api = axios.create({
  baseURL: API_BASE,
  timeout: DEFAULT_TIMEOUT_MS,
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${API_TOKEN}`
  }
});

// Intercepteur pour logger les erreurs
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      console.error('API Auth Error: Token invalide. Vérifiez REACT_APP_API_TOKEN dans .env');
    } else {
      console.error('API Error:', error.response?.data || error.message);
    }
    return Promise.reject(error);
  }
);

// ═══════════════════════════════════════════════════════════════════════════
// CHAT / RAG
// ═══════════════════════════════════════════════════════════════════════════

export const chatService = {
  /**
   * Envoyer une question au système RAG
   * @param {string} query - Question de l'utilisateur
   * @param {string|null} sessionId - ID de session (optionnel)
   * @param {string|null} metier - Filtre métier : TSSR, AIS, DevOps (optionnel)
   * @param {number} topK - Nombre de chunks à récupérer
   * @param {number} threshold - Seuil de similarité
   * @returns {Promise<ChatResponse>}
   */
  async sendMessage({ query, sessionId, metier, topK = 5, threshold = 0.7 }) {
    const response = await api.post('/chat', {
      query,
      session_id: sessionId,
      metier,
      top_k: topK,
      threshold,
    });
    return response.data;
  },

  /**
   * Récupérer l'historique des conversations
   * @param {string|null} sessionId - Filtrer par session (optionnel)
   * @param {string|null} metier - Filtrer par métier (optionnel)
   * @param {number} limit - Nombre max de résultats
   * @returns {Promise<Array>}
   */
  async getHistory(sessionId = null, metier = null, limit = 20) {
    const response = await api.get('/chat/history', {
      params: {
        session_id: sessionId,
        metier,
        limit
      }
    });
    return response.data;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// DOCUMENTS
// ═══════════════════════════════════════════════════════════════════════════

export const documentService = {
  /**
   * Upload et indexer un document
   * @param {File} file - Fichier à uploader
   * @param {string|null} metier - Métier associé (TSSR, AIS, DevOps)
   * @returns {Promise<Object>}
   */
  async uploadDocument(file, metier = null) {
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await api.post('/documents/upload', formData, {
      params: { metier },
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    });
    return response.data;
  },

  /**
   * Lister tous les documents indexés
   * @returns {Promise<Array>}
   */
  async listDocuments() {
    const response = await api.get('/documents/list');
    return response.data;
  },

  /**
   * Supprimer un document et ses chunks
   * @param {string} fileId - ID du fichier
   * @returns {Promise<Object>}
   */
  async deleteDocument(fileId) {
    const response = await api.delete(`/documents/${fileId}`);
    return response.data;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// SYSTEM / HEALTH
// ═══════════════════════════════════════════════════════════════════════════

export const healthService = {
  /**
   * Vérifier l'état du système
   * @returns {Promise<HealthResponse>}
   */
  async checkHealth() {
    const response = await api.get('/health');
    return response.data;
  },

  /**
   * Obtenir les statistiques d'indexation
   * @returns {Promise<Object>}
   */
  async getIndexingStatus() {
    const response = await api.get('/indexing/status');
    return response.data;
  }
};

// ═══════════════════════════════════════════════════════════════════════════
// INDEXATION
// ═══════════════════════════════════════════════════════════════════════════

export const indexingService = {
  /**
   * Indexer un répertoire complet
   * @param {string} directory - Chemin du répertoire
   * @returns {Promise<Object>}
   */
  async indexDirectory(directory) {
    const response = await api.post('/indexing/directory', { directory });
    return response.data;
  },

  /**
   * Réinitialiser la collection (DANGER : efface tout)
   * @returns {Promise<Object>}
   */
  async resetCollection() {
    const response = await api.post('/indexing/reset');
    return response.data;
  }
};

// Export par défaut de l'instance axios (si besoin de requêtes custom)
export default api;
