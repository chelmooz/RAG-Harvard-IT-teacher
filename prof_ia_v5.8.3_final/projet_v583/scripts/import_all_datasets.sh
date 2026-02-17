#!/bin/bash

################################################################################
# Script d'import automatique de tous les datasets
# Prof IA v5.8
# Usage: ./import_all_datasets.sh
################################################################################

set -e  # Arrêter en cas d'erreur

echo "=========================================="
echo "IMPORT PROF IA v5.8 - TOUS LES DATASETS"
echo "=========================================="
echo ""

# Vérifier que Python est installé
if ! command -v python &> /dev/null; then
    echo "ERREUR: Python n'est pas installé"
    exit 1
fi

# Vérifier que les dépendances sont installées
echo "[INFO] Vérification des dépendances..."
python -c "import chromadb; import sentence_transformers" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[WARN] Dépendances manquantes. Installation..."
    pip install -r requirements_import.txt
fi

# Vérifier que les répertoires de datasets existent
echo "[INFO] Vérification des répertoires..."

MISSING=0
if [ ! -d "kaggle_datasets" ]; then
    echo "[WARN] Répertoire kaggle_datasets/ manquant"
    MISSING=1
fi

if [ ! -d "huggingface_datasets" ]; then
    echo "[WARN] Répertoire huggingface_datasets/ manquant"
    MISSING=1
fi

if [ ! -d "github_datasets" ]; then
    echo "[WARN] Répertoire github_datasets/ manquant"
    MISSING=1
fi

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "ERREUR: Certains répertoires de datasets sont manquants."
    echo "Assurez-vous d'avoir téléchargé tous les datasets avec:"
    echo "  - download_kaggle_datasets.ps1"
    echo "  - download_huggingface_datasets.ps1"
    echo "  - download_github_dataset.ps1"
    exit 1
fi

echo "[OK] Tous les répertoires sont présents"
echo ""

################################################################################
# PHASE 1 : DATASET ESSENTIEL
################################################################################
echo "=========================================="
echo "PHASE 1 : DATASET ESSENTIEL (5 min)"
echo "=========================================="
echo ""

echo "[1/7] Import : Linux Terminal Commands (transverse)..."
python import_datasets.py --source linux_commands
if [ $? -eq 0 ]; then
    echo "[OK] Linux Commands importé"
else
    echo "[ERREUR] Échec de l'import des commandes Linux"
fi
echo ""

################################################################################
# PHASE 2 : DATASETS TSSR
################################################################################
echo "=========================================="
echo "PHASE 2 : DATASETS TSSR (30-60 min)"
echo "=========================================="
echo ""

echo "[2/7] Import : Tech Support Conversations..."
python import_datasets.py --source tech_support
if [ $? -eq 0 ]; then
    echo "[OK] Tech Support importé"
else
    echo "[ERREUR] Échec de l'import tech support"
fi
echo ""

echo "[3/7] Import : Customer Support Tickets..."
python import_datasets.py --source customer_tickets
if [ $? -eq 0 ]; then
    echo "[OK] Customer Tickets importé"
else
    echo "[ERREUR] Échec de l'import customer tickets"
fi
echo ""

################################################################################
# PHASE 3 : DATASETS AIS
################################################################################
echo "=========================================="
echo "PHASE 3 : DATASETS AIS (60-120 min)"
echo "=========================================="
echo ""

echo "[4/7] Import : Advanced SIEM Dataset..."
python import_datasets.py --source siem
if [ $? -eq 0 ]; then
    echo "[OK] SIEM Dataset importé"
else
    echo "[ERREUR] Échec de l'import SIEM"
fi
echo ""

echo "[5/7] Import : Cybersecurity Threat Detection Logs..."
python import_datasets.py --source threat_logs
if [ $? -eq 0 ]; then
    echo "[OK] Threat Logs importé"
else
    echo "[ERREUR] Échec de l'import threat logs"
fi
echo ""

################################################################################
# PHASE 4 : DATASETS DEVOPS
################################################################################
echo "=========================================="
echo "PHASE 4 : DATASETS DEVOPS (30-60 min)"
echo "=========================================="
echo ""

echo "[6/7] Import : AI-Driven CI/CD Pipeline Logs..."
python import_datasets.py --source cicd_logs
if [ $? -eq 0 ]; then
    echo "[OK] CI/CD Logs importé"
else
    echo "[ERREUR] Échec de l'import CI/CD logs"
fi
echo ""

echo "[7/7] Import : DEVOPS Dataset..."
python import_datasets.py --source devops_dataset
if [ $? -eq 0 ]; then
    echo "[OK] DevOps Dataset importé"
else
    echo "[ERREUR] Échec de l'import DevOps dataset"
fi
echo ""

################################################################################
# FIN : STATISTIQUES
################################################################################
echo "=========================================="
echo "IMPORT TERMINÉ !"
echo "=========================================="
echo ""

echo "Affichage des statistiques finales..."
python import_datasets.py --stats

echo ""
echo "=========================================="
echo "PROCHAINES ÉTAPES :"
echo "=========================================="
echo "1. Intégrer rag_engine_v58.py dans backend/api/"
echo "2. Mettre à jour main.py"
echo "3. Relancer Prof IA v5.7"
echo "4. Tester avec: curl http://localhost:8000/datasets/stats"
echo ""
echo "Consultez GUIDE_INTEGRATION_v5.8.md pour plus de détails"
echo ""
