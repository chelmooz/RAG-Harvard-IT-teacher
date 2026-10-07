# PROF IA v1.4

Contexte du produit actuel : un système RAG dont le LLM est llama.cpp exécuté sur
l'hôte, avec un backend FastAPI, des embeddings et un reranker CPU, PostgreSQL/
pgvector, React et Nginx. Il succède à un projet antérieur dont l'inférence
passait par Ollama.

## Language

**Ollama** :
L'ancien serveur d'inférence du projet antérieur. Il appartient à l'historique,
jamais à l'architecture cible.
_Avoid_ : « migrer Ollama », « réparer Ollama », « garder Ollama temporairement »,
« Ollama fallback », « migration Ollama → llama.cpp »

**Reliquat legacy** :
Une pièce du projet antérieur conservée uniquement pour la traçabilité, hors
exécution v1.4.
_Avoid_ : « dépendance », « fallback », « à réparer »

**Adaptation** :
Le travail des tickets G2 : amener le code existant à l'architecture PROF IA v1.4.
_Avoid_ : migration (implique que l'ancien système reste une étape du nouveau)

**llama.cpp** :
Le serveur d'inférence de PROF IA v1.4, exécuté sur l'hôte avec Vulkan/RADV et non
conteneurisé.
_Avoid_ : Ollama

**Contrat de santé** :
La forme de l'état des composants exposée par l'endpoint de santé du backend. Il
remplace l'ancien contrat du projet antérieur.
_Avoid_ : « renommer health.ollama », « réparer /health.ollama »

**Résidu actif** :
Toute occurrence d'une dépendance du projet antérieur encore atteignable pendant
l'exécution v1.4. C'est ce que les tickets G2 éliminent.
_Avoid_ : « fonctionnalité à préserver »
