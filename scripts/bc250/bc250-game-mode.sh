#!/usr/bin/env bash
# =============================================================================
# BC-250 — Bascule mode JEU <-> mode RAG (libération/réservation VRAM Ollama)
# -----------------------------------------------------------------------------
# Le BC-250 partage 16 Go GDDR6 (GPU+CPU). En mode RAG, Ollama verrouille
# ~9,3 Go (qwen3:14b Q4). Pour jouer, on libère ce VRAM.
#
#   game       : décharge le modèle / stoppe Ollama → VRAM libre pour le jeu
#   rag        : redémarre Ollama + recharge le modèle
#   game-boot  : pose kargs split 8 Go GPU / 8 Go CPU + reboot (profil jeu pur)
#   rag-boot   : restaure kargs split 12 Go GPU / 4 Go CPU + reboot (profil RAG)
#   status     : état Ollama + mémoire
#
# Note : le split fin (kargs) nécessite un reboot. `game`/`rag` suffisent pour
# basculer à chaud sans reboot (le GPU utilise jusqu'au plafond ttm.pages_limit).
# =============================================================================
set -uo pipefail

MODEL="${OLLAMA_MODEL:-qwen3:14b}"

case "${1:-status}" in
    game)
        echo "Mode JEU : libération VRAM Ollama ($MODEL)..."
        ollama stop "$MODEL" 2>/dev/null || true
        systemctl --user stop ollama 2>/dev/null || true
        echo "VRAM libérée. Pour un split plus favorable au jeu, utiliser 'game-boot'."
        ;;
    rag)
        echo "Mode RAG : démarrage Ollama + chargement $MODEL..."
        systemctl --user start ollama 2>/dev/null || true
        ollama pull "$MODEL" 2>/dev/null || true
        ollama run "$MODEL" "ping" >/dev/null 2>&1 || true
        echo "Modèle prêt (VRAM réservée)."
        ;;
    game-boot)
        echo "Profil JEU : kargs ttm.pages_limit=2097152 (~8 Go GPU) + reboot..."
        rpm-ostree kargs --append-if-missing="ttm.pages_limit=2097152"
        echo "Reboot requis (sudo systemctl reboot)."
        ;;
    rag-boot)
        echo "Profil RAG : kargs ttm.pages_limit=3014656 (~12 Go GPU) + reboot..."
        rpm-ostree kargs --delete="ttm.pages_limit=2097152" 2>/dev/null || true
        rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"
        echo "Reboot requis (sudo systemctl reboot)."
        ;;
    status)
        echo "--- Ollama ---"; ollama ps 2>/dev/null || echo "  (indisponible)"
        echo "--- Mémoire ---"; free -h
        echo "--- kargs ttm ---"; rpm-ostree kargs 2>/dev/null | grep -o 'ttm.pages_limit=[0-9]*' || echo "  (défaut)"
        ;;
    *)
        echo "Usage: $0 {game|rag|game-boot|rag-boot|status}"
        exit 1
        ;;
esac
