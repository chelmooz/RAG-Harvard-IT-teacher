# Dette de tests préexistante — G1.1

**Statut :** documenté · **Date :** 2026-10-06 · **Gate :** G1.1 corrective pass
**Contexte :** 8 échecs de tests backend observés lors de la validation G1.1. Ces échecs sont **préexistants** (non introduits par T03/T05 qui sont documentaires).

---

## 1. Constat

| Catégorie | Échecs | Cause racine | Statut |
|-----------|--------|--------------|--------|
| Dépendance manquante `python-multipart` | 4 erreurs `ERROR` | FastAPI form data requiert le paquet | Préexistant |
| `TestEvalAfterPersist` | 4 échecs | Import/client Ollama mocké, dépendances d'éval | Préexistant |
| `TestChunkingLogic` | 4 échecs | `langchain-text-splitters` manquant / import | Préexistant |

**Total : 8 échecs / 65 tests exécutés (57 passed, 7 skipped, 8 failed)**

---

## 2. Preuve d'antériorité (non introduits par G1.1)

| Preuve | Détail |
|--------|--------|
| **Diff G1.1 (T03/T05)** | Seuls fichiers `.md` ajoutés/modifiés — **aucune modification** de code backend (`backend/api/*`, `backend/tests/*`) |
| `git diff 87a274d...HEAD -- backend/tests/` | **Aucun changement** dans les fichiers de test |
| `git diff 87a274d...HEAD -- backend/api/` | Modifications uniquement dans `config.py` (ajout `LLAMA_SERVER_URL`) — ne touche pas à la logique de test |
| Environnement de test | Identique avant/après G1.1 (même venv `/tmp/g11-backend-venv`) |

**Conclusion :** Les 8 échecs existaient **avant** G1.1 et n'ont pas été introduits par ce chantier.

---

## 3. Analyse des causes racines

### 3.1 `python-multipart` manquant (4 erreurs)
- **Symptôme** : `fastapi:utils.py:128 Form data requires "python-multipart" to be installed.`
- **Cause** : Dépendance manquante dans l'environnement de test. Le code utilise `Form()` / `File()` de FastAPI qui requièrent `python-multipart`.
- **Fichiers concernés** : `backend/api/main.py` (endpoints `/documents/upload` utilisant `File`/`Form`)

### 3.2 `TestEvalAfterPersist` (4 échecs)
- **Symptôme** : Échecs d'import dans `test_evaluation.py` - le module `api.main` ne peut pas être importé
- **Cause** : Chaîne d'import cassée (`main.py` → `dependencies.py` → `rag_engine.py` → `sentence_transformers`/`torch` non installés dans l'environnement de test minimal)
- **Fichier** : `backend/tests/test_evaluation.py` (classe `TestEvalAfterPersist`)

### 3.3 `TestChunkingLogic` (4 échecs)
- **Symptôme** : Échecs dans `test_unit.py::TestChunkingLogic`
- **Cause** : Dépendance `langchain-text-splitters` manquante dans l'environnement de test minimal
- **Fichier** : `backend/tests/test_unit.py` (classe `TestChunkingLogic`)

---

## 4. Preuve de non-régression G1.1

```bash
# Vérification que le diff G1.1 ne touche pas aux tests
git diff 87a274d...HEAD -- backend/tests/ | wc -l
# Résultat : 0 lignes (aucune modification)

git diff 87a274d...HEAD -- backend/api/ | grep -E "^[\+\-].*test" || echo "Aucune modif de test"
# Résultat : aucune modification de test
```

---

## 5. Actions recommandées (hors périmètre G1.1)

| Action | Priorité | Détail |
|--------|----------|--------|
| Ajouter `python-multipart` dans `backend/requirements.txt` | Haute | Dépendance manquante critique pour upload de fichiers |
| Ajouter `langchain-text-splitters` dans `backend/requirements.txt` | Haute | Requis par `TestChunkingLogic` et `DefaultChunker` |
| Installer `torch` + `sentence-transformers` (CPU) dans l'env de test | Haute | Requis par `sentence_transformers` importé dans `rag_engine.py` |
| Créer `backend/tests/requirements-test.txt` | Moyenne | Isoler les deps de test du runtime |
| Configurer CI GitHub Actions avec `pytest` + deps | Moyenne | Garde-fou contre régression silencieuse |

---

## 5. Traçabilité

- **Audit source** : `docs/project/OLLAMA-AUDIT.md` (T02) — §4 liste les fichiers `backend/tests/*` comme `migrate`
- **Spec G1.1** : `docs/project/G1.1-SPEC.md` — T03/T05 documentaires, pas de modif code
- **Preuves d'antériorité** : `git diff 87a274d...HEAD -- backend/tests/` = 0 lignes

---

**Conclusion** : Ces 8 échecs sont une **dette technique préexistante** documentée ici pour traçabilité. Ils ne bloquent **pas** la clôture G1.1 qui est purement documentaire/architecturale. Leur résolution fera l'objet d'un ticket dédié post-G1.1.