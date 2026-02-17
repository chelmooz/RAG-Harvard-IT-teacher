# 📘 Guide d'Intégration Prof IA v5.8 ALL-IN-ONE
## Une seule collection pour tout - Parfait pour l'apprentissage Bachelor

**Version** : 1.0 ALL-IN-ONE  
**Date** : Février 2026  
**Upgrade** : v5.7 → v5.8  
**Architecture** : Collection unique universelle

---

## 🎯 Pourquoi ALL-IN-ONE ?

### ❌ **Problème avec les collections séparées**

Imaginez cette question : *"Comment sécuriser un pipeline CI/CD contre les injections de code ?"*

**Avec collections séparées (mauvais)** :
- 🤖 Détection : "pipeline CI/CD" → Route vers **DevOps**
- ❌ Mais l'expertise est dans **AIS** (sécurité) !
- 💥 Vous ratez les meilleures infos

**Avec ALL-IN-ONE (bon)** :
- ✅ Cherche partout dans TOUTE la base
- ✅ Trouve automatiquement ce qui est pertinent (DevOps + AIS)
- ✅ Pas de "mauvais paquet"

### ✅ **Avantages pour l'apprentissage Bachelor**

- ✅ **Zéro confusion** : Le RAG trouve ce qui est pertinent, point final
- ✅ **Questions mixtes** : "Comment monitorer la sécu d'un pipeline K8s ?" → Trouve AIS + DevOps
- ✅ **Apprentissage naturel** : Vous posez vos questions sans réfléchir au métier
- ✅ **Pas de "trou"** : Impossible de rater des infos importantes

---

## 🎯 Nouveautés v5.8 ALL-IN-ONE

### ✅ **7 Datasets intégrés**

**TSSR** (Support technique) :
- Tech Support Conversations (~800 MB)
- Customer Support Tickets (~1.5 GB)

**AIS** (Sécurité) :
- Advanced SIEM Dataset (~2.8 GB) ⭐
- Cybersecurity Threat Detection Logs (~1.9 GB) ⭐

**DevOps** (CI/CD) :
- AI-Driven CI/CD Pipeline Logs (~950 MB)
- DEVOPS Dataset (~200 MB)

**Transverse** :
- Linux Terminal Commands (~45 MB)

**Total** : ~8.2 GB source → ~3.9 GB indexé (~33 000 chunks)

### ✅ **Une seule collection : prof_ia_all**

```
prof_ia_all (~33 000 chunks)
├── TSSR        : ~11 000 chunks
├── AIS         : ~16 700 chunks
├── DevOps      : ~5 300 chunks
└── Transverse  : ~200 chunks
```

---

## 📋 Prérequis

### Datasets téléchargés

✅ **Kaggle** (4 datasets dans `./kaggle_datasets/`) :
- linux-terminal-commands-dataset/
- tech-support-conversations-dataset/
- cybersecurity-threat-detection-logs/
- ai-driven-cicd-pipeline-logs-dataset/

✅ **HuggingFace** (3 datasets dans `./huggingface_datasets/`) :
- customer-support-tickets/
- Advanced_SIEM_Dataset/
- DEVOPS/

❌ **GitHub** : PAS NÉCESSAIRE (cours trop basique pour niveau Bachelor)

### Vérification

```bash
ls kaggle_datasets/
ls huggingface_datasets/
```

---

## 🚀 PARTIE 1 : Installation des Dépendances

```bash
pip install -r requirements_import.txt
```

Ou manuellement :

```bash
pip install chromadb==0.4.22 \
            sentence-transformers==2.3.1 \
            pandas==2.1.4 \
            tqdm==4.66.1 \
            loguru==0.7.2 \
            torch==2.1.2 \
            transformers==4.36.2
```

**Temps estimé** : 2-5 minutes

### Vérification

```bash
python -c "import chromadb; import sentence_transformers; print('OK')"
```

---

## 📥 PARTIE 2 : Import Automatique des Datasets

### Option A : Script automatique (RECOMMANDÉ)

**Sur Windows (PowerShell)** :
```powershell
.\import_all_datasets.ps1
```

**Sur Linux/Mac (Bash)** :
```bash
chmod +x import_all_datasets.sh
./import_all_datasets.sh
```

⏱️ **Durée totale** : 2-4 heures

### Option B : Import manuel étape par étape

```bash
# 1. Linux Commands (5 min)
python import_datasets.py --source linux_commands

# 2. Tech Support (20 min)
python import_datasets.py --source tech_support

# 3. Customer Tickets (30 min)
python import_datasets.py --source customer_tickets

# 4. SIEM Dataset (60 min) ⭐
python import_datasets.py --source siem

# 5. Threat Logs (45 min) ⭐
python import_datasets.py --source threat_logs

# 6. CI/CD Logs (25 min)
python import_datasets.py --source cicd_logs

# 7. DevOps Dataset (10 min)
python import_datasets.py --source devops_dataset

# Vérifier les stats
python import_datasets.py --stats
```

### Ce que vous verrez pendant l'import

```
[1/7] Import : Linux Terminal Commands (transverse)...
Lecture de linux_terminal_commands.csv...
Nombre de lignes: 5000
Génération des embeddings pour 1200 chunks...
100%|████████████████████| 1200/1200 [00:45<00:00, 26.5it/s]
Ajout de 1200 chunks à 'prof_ia_all'...
[OK] Linux Commands importé

[2/7] Import : Tech Support Conversations...
...
```

---

## 🔄 PARTIE 3 : Intégration dans Prof IA v5.7

### Étape 3.1 : Sauvegarder l'ancien RAG engine

```bash
cd backend/api
cp rag_engine.py rag_engine_v57_backup.py
```

### Étape 3.2 : Installer le nouveau RAG engine

```bash
# Copier le nouveau moteur
cp rag_engine_v58_all_in_one.py backend/api/rag_engine.py
```

### Étape 3.3 : Mettre à jour main.py

Ouvrez `backend/api/main.py` et modifiez :

**AVANT (v5.7)** :
```python
from .rag_engine import RAGEngine

# Initialisation
rag_engine = RAGEngine()
```

**APRÈS (v5.8 ALL-IN-ONE)** :
```python
from .rag_engine import RAGEngineV58AllInOne

# Initialisation avec ChromaDB ALL-IN-ONE
rag_engine = RAGEngineV58AllInOne(chromadb_path="./chromadb_data")
```

### Étape 3.4 : Ajouter un endpoint de stats

Ajoutez dans `main.py` :

```python
@app.get("/datasets/stats")
async def get_datasets_stats():
    """
    Retourne les statistiques des datasets importés
    Architecture ALL-IN-ONE : une seule collection universelle
    """
    stats = rag_engine.get_stats()
    return {
        "status": "success",
        "architecture": "all-in-one",
        "collection": "prof_ia_all",
        "total_documents": stats["total_documents"],
        "by_metier": stats["by_metier"]
    }
```

### Étape 3.5 : Relancer le backend

```bash
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🧪 PARTIE 4 : Tests de Validation

### Test 1 : Vérifier les stats

```bash
curl http://localhost:8000/datasets/stats
```

**Résultat attendu** :
```json
{
  "status": "success",
  "architecture": "all-in-one",
  "collection": "prof_ia_all",
  "total_documents": 33000,
  "by_metier": {
    "TSSR": 11000,
    "AIS": 16700,
    "DevOps": 5300
  }
}
```

### Test 2 : Question TSSR pure

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Comment réinitialiser un mot de passe Windows ?",
    "mode": "precise"
  }'
```

**Attendu** : Réponse avec contexte TSSR

### Test 3 : Question AIS pure

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Comment analyser des logs SIEM pour détecter une intrusion ?",
    "mode": "explore"
  }'
```

**Attendu** : Réponse avec contexte AIS

### Test 4 : Question DevOps pure

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Comment configurer un pipeline GitLab CI avec Docker ?",
    "mode": "synthesis"
  }'
```

**Attendu** : Réponse avec contexte DevOps

### Test 5 : Question MIXTE (le plus important !)

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Comment sécuriser un pipeline CI/CD contre les injections de code malveillant ?",
    "mode": "explore"
  }'
```

**Attendu** : Réponse avec contexte **AIS + DevOps** combinés ! ⭐

---

## 📊 PARTIE 5 : Vérifications

### Vérifier la taille de ChromaDB

```bash
du -sh chromadb_data/
```

**Attendu** : ~3.9 GB

### Vérifier le nombre de documents

```bash
python import_datasets.py --stats
```

**Attendu** :
```
=== Statistiques ChromaDB ===
Collection 'prof_ia_all': 33000 documents

Répartition par métier:
  - TSSR: 11000 chunks
  - AIS: 16700 chunks
  - DevOps: 5300 chunks
  - Linux (Transverse): 200 chunks
```

### Tester la recherche dans Python

```python
from backend.api.rag_engine import RAGEngineV58AllInOne

rag = RAGEngineV58AllInOne()

# Question mixte AIS + DevOps
results = rag.retrieve(
    "Comment monitorer la sécurité d'un cluster Kubernetes ?",
    mode="explore",
    top_k=5
)

# Vérifier qu'on a des résultats des 2 métiers
metiers = set(r['metadata'].get('source', '') for r in results)
print(f"Métiers trouvés: {metiers}")
# Attendu: {'AIS', 'DevOps'}
```

---

## ✅ Checklist Finale

- [ ] 7 datasets importés (33 000 chunks)
- [ ] Collection `prof_ia_all` créée
- [ ] RAG engine v5.8 ALL-IN-ONE intégré
- [ ] Endpoint `/datasets/stats` fonctionnel
- [ ] Test TSSR validé
- [ ] Test AIS validé
- [ ] Test DevOps validé
- [ ] **Test mixte AIS+DevOps validé** ⭐ (le plus important)

---

## 🎓 Pourquoi c'est parfait pour votre Bachelor ?

### Scénarios réels d'apprentissage

**Scenario 1** : Vous étudiez la sécurité des containers

Question : *"Quelles sont les vulnérabilités courantes dans Docker ?"*

- ✅ ALL-IN-ONE trouve : Infos AIS (vulnérabilités) + DevOps (Docker)
- ❌ Collections séparées : Rateriez les vulnérabilités si routé vers DevOps uniquement

**Scenario 2** : Vous préparez un projet de pipeline sécurisé

Question : *"Comment implémenter SAST et DAST dans GitLab CI ?"*

- ✅ ALL-IN-ONE trouve : DevOps (GitLab CI) + AIS (SAST/DAST)
- ❌ Collections séparées : Information fragmentée

**Scenario 3** : Dépannage réseau avec aspect sécurité

Question : *"Comment diagnostiquer une attaque DDoS sur mon infrastructure ?"*

- ✅ ALL-IN-ONE trouve : TSSR (diagnostic) + AIS (DDoS) + DevOps (infra)
- ❌ Collections séparées : Impossible de combiner les 3 expertises

---

## 🆘 Dépannage

### Erreur : "Collection not found"

```bash
python -c "
import chromadb
client = chromadb.PersistentClient(path='./chromadb_data')
print(client.list_collections())
"
```

Si vide → Relancer l'import

### Import trop lent

Réduire `batch_size` dans `import_datasets.py` ligne ~240 :
```python
batch_size=16  # au lieu de 32
```

### Out of Memory pendant l'import

Importer dataset par dataset au lieu du script complet :
```bash
python import_datasets.py --source linux_commands
# Attendre que ça finisse
python import_datasets.py --source tech_support
# etc.
```

---

## 📝 Notes de Version

### v5.8 ALL-IN-ONE (Février 2026)

**Architecture** :
- ✅ Collection unique universelle `prof_ia_all`
- ❌ Pas de détection de métier (inutile)
- ✅ Le RAG trouve ce qui est pertinent automatiquement

**Datasets** :
- ✅ 7 datasets intégrés (~8.2 GB source)
- ✅ ~33 000 chunks indexés (~3.9 GB)
- ❌ Cours admin réseaux retiré (trop basique)

**Avantages** :
- ✅ Zéro confusion de routage
- ✅ Questions mixtes parfaitement gérées
- ✅ Parfait pour apprentissage Bachelor AIS+DevOps

**Compatibilité** :
- ✅ Compatible v5.7 (drop-in replacement)
- ✅ API inchangée
- ✅ AMD BC-250 compatible

---

**🎉 Bon apprentissage avec Prof IA v5.8 ALL-IN-ONE !**

*Document créé pour les étudiants Bachelor AIS/DevOps*  
*Version 1.0 — Février 2026*
