################################################################################
# Script PowerShell d'import automatique de tous les datasets
# Prof IA v5.8
# Usage: .\import_all_datasets.ps1
################################################################################

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "IMPORT PROF IA v5.8 - TOUS LES DATASETS" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Vérifier Python
try {
    $pythonVersion = python --version
    Write-Host "[OK] Python detecte: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERREUR] Python n'est pas installe" -ForegroundColor Red
    exit 1
}

# Vérifier les dépendances
Write-Host "[INFO] Verification des dependances..." -ForegroundColor Yellow
$depsCheck = python -c "import chromadb; import sentence_transformers" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Dependances manquantes. Installation..." -ForegroundColor Yellow
    python -m pip install -r requirements_import.txt
}

# Vérifier les répertoires
Write-Host "[INFO] Verification des repertoires..." -ForegroundColor Yellow

$missing = $false
if (!(Test-Path "kaggle_datasets")) {
    Write-Host "[WARN] Repertoire kaggle_datasets/ manquant" -ForegroundColor Yellow
    $missing = $true
}

if (!(Test-Path "huggingface_datasets")) {
    Write-Host "[WARN] Repertoire huggingface_datasets/ manquant" -ForegroundColor Yellow
    $missing = $true
}

if (!(Test-Path "github_datasets")) {
    Write-Host "[WARN] Repertoire github_datasets/ manquant" -ForegroundColor Yellow
    $missing = $true
}

if ($missing) {
    Write-Host "" 
    Write-Host "[ERREUR] Certains repertoires de datasets sont manquants." -ForegroundColor Red
    Write-Host "Assurez-vous d'avoir telecharge tous les datasets avec:" -ForegroundColor Yellow
    Write-Host "  - download_kaggle_datasets.ps1"
    Write-Host "  - download_huggingface_datasets.ps1"
    Write-Host "  - download_github_dataset.ps1"
    exit 1
}

Write-Host "[OK] Tous les repertoires sont presents" -ForegroundColor Green
Write-Host ""

################################################################################
# PHASE 1 : DATASETS ESSENTIELS
################################################################################
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PHASE 1 : DATASET ESSENTIEL (5 min)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/7] Import : Linux Terminal Commands (transverse)..." -ForegroundColor Yellow
python import_datasets.py --source linux_commands
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Linux Commands importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import des commandes Linux" -ForegroundColor Red
}
Write-Host ""

################################################################################
# PHASE 2 : DATASETS TSSR
################################################################################
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PHASE 2 : DATASETS TSSR (30-60 min)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[2/7] Import : Tech Support Conversations..." -ForegroundColor Yellow
python import_datasets.py --source tech_support
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Tech Support importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import tech support" -ForegroundColor Red
}
Write-Host ""

Write-Host "[3/7] Import : Customer Support Tickets..." -ForegroundColor Yellow
python import_datasets.py --source customer_tickets
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Customer Tickets importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import customer tickets" -ForegroundColor Red
}
Write-Host ""

################################################################################
# PHASE 3 : DATASETS AIS
################################################################################
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PHASE 3 : DATASETS AIS (60-120 min)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[4/7] Import : Advanced SIEM Dataset..." -ForegroundColor Yellow
python import_datasets.py --source siem
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] SIEM Dataset importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import SIEM" -ForegroundColor Red
}
Write-Host ""

Write-Host "[5/7] Import : Cybersecurity Threat Detection Logs..." -ForegroundColor Yellow
python import_datasets.py --source threat_logs
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Threat Logs importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import threat logs" -ForegroundColor Red
}
Write-Host ""

################################################################################
# PHASE 4 : DATASETS DEVOPS
################################################################################
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PHASE 4 : DATASETS DEVOPS (30-60 min)" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[6/7] Import : AI-Driven CI/CD Pipeline Logs..." -ForegroundColor Yellow
python import_datasets.py --source cicd_logs
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] CI/CD Logs importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import CI/CD logs" -ForegroundColor Red
}
Write-Host ""

Write-Host "[7/7] Import : DEVOPS Dataset..." -ForegroundColor Yellow
python import_datasets.py --source devops_dataset
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] DevOps Dataset importe" -ForegroundColor Green
} else {
    Write-Host "[ERREUR] Echec de l'import DevOps dataset" -ForegroundColor Red
}
Write-Host ""

################################################################################
# FIN : STATISTIQUES
################################################################################
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "IMPORT TERMINE !" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "Affichage des statistiques finales..." -ForegroundColor Yellow
python import_datasets.py --stats

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "PROCHAINES ETAPES :" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "1. Integrer rag_engine_v58.py dans backend/api/" -ForegroundColor Yellow
Write-Host "2. Mettre a jour main.py" -ForegroundColor Yellow
Write-Host "3. Relancer Prof IA v5.7" -ForegroundColor Yellow
Write-Host "4. Tester avec: curl http://localhost:8000/datasets/stats" -ForegroundColor Yellow
Write-Host ""
Write-Host "Consultez GUIDE_INTEGRATION_v5.8.md pour plus de details" -ForegroundColor Magenta
Write-Host ""
