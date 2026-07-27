# ServiceStatus — Guide d'intégration v5.8.3

## Où placer ce composant ?

Le composant `ServiceStatus.js` est autonome. Pour l'intégrer dans votre dashboard existant :

### Option A — Dans Dashboard.js (le plus simple)

```jsx
// En haut de Dashboard.js, ajouter :
import ServiceStatus from './ServiceStatus';

// Dans le JSX du Dashboard, ajouter où vous voulez le panneau :
<ServiceStatus
  token={votre_token_de_session}
  apiUrl="http://192.168.1.11:8000"
/>
```

### Option B — Comme page dédiée dans App.js

```jsx
// Dans App.js, ajouter la route :
import ServiceStatus from './pages/ServiceStatus';

// Dans le router :
<Route path="/services" element={
  <ServiceStatus token={token} apiUrl="http://192.168.1.11:8000" />
} />
```

## Ce que vous verrez

4 cartes, une par service :
- 🗄️  PostgreSQL     [● VERT]  [🔄 Redémarrer] [⏹ Arrêter] [▶ Démarrer]
- 🧠  Ollama ROCm    [● VERT]  [🔄 Redémarrer] [⏹ Arrêter] [▶ Démarrer]
- ⚡  Backend FastAPI [● VERT]  [🔄 Redémarrer]
- 🖥️  Frontend React  [● VERT]  [🔄 Redémarrer]

Note : les boutons Stop/Start ne sont pas affichés pour Backend et Frontend
car arrêter le backend couperait l'API elle-même.

## Couleurs des pastilles

| Couleur | Signification |
|---------|---------------|
| 🟢 VERT   | Conteneur running + healthy |
| 🟠 ORANGE | Conteneur starting ou unhealthy |
| 🔴 ROUGE  | Conteneur arrêté ou introuvable |
