"""
Validators & ROCm env injection for Prof IA configuration.
=========================================================
Extrait de config.py (PR P2 — audit « Validateurs → validators.py »).

Responsabilité unique : valider les Settings et injecter les variables
d'environnement ROCm AVANT tout import torch/transformers.
"""

import os
import secrets
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from .config import Settings


def _validate_token_source(s: "Settings") -> None:
    if not s.API_TOKEN_SOURCE:
        s.API_TOKEN_SOURCE = secrets.token_urlsafe(32)
        logger.warning(
            "⚠️  API_TOKEN_SOURCE non défini dans .env — clé aléatoire générée. "
            "Les sessions seront invalidées au redémarrage. "
            "Ajoutez API_TOKEN_SOURCE=<votre_clé> dans .env pour la persistance."
        )


def _validate_database_url(s: "Settings") -> None:
    if not s.DATABASE_URL:
        raise ValueError(
            "DATABASE_URL obligatoire dans .env. "
            "Exemple : DATABASE_URL=postgresql://user:password@localhost:5432/prof_ia_v5"
        )


def _validate_api_token(s: "Settings") -> None:
    if not s.API_TOKEN:
        s.API_TOKEN = s.API_TOKEN_SOURCE
        if not s.API_TOKEN:
            s.API_TOKEN = secrets.token_urlsafe(32)
            logger.warning(
                "⚠️  API_TOKEN non défini dans .env — clé aléatoire générée. "
                "Ajoutez API_TOKEN=<votre_clé> dans .env pour la persistance."
            )


def _validate_cors(s: "Settings") -> None:
    if s.CORS_ORIGINS == "*" and not s.DEBUG:
        logger.warning(
            "⚠️  CORS_ORIGINS='*' en mode non DEBUG — restreignez les origines "
            "dans .env (ex: CORS_ORIGINS=http://localhost:3000) en production."
        )


def _validate_amd_cus(s: "Settings") -> None:
    if s.AMD_RDNA2_CUS not in (24, 40):
        logger.warning(
            f"⚠️  AMD_RDNA2_CUS={s.AMD_RDNA2_CUS} inhabituel (24=stock, 40=débloqué). "
            "Vérifiez votre .env."
        )
    if s.AMD_RDNA2_CUS == 40 and not s.AMD_CU_UNLOCK_APPLIED:
        logger.warning(
            "⚠️  AMD_RDNA2_CUS=40 mais AMD_CU_UNLOCK_APPLIED=False — "
            "si le module amdgpu patché (bc250-40cu-unlock) n'est pas chargé, "
            "cette valeur est juste un mensonge de config qui fausse "
            "PYTORCH_HIP_ALLOC_CONF et EMBEDDING_BATCH_SIZE. "
            "Vérifiez avec : sudo dmesg | grep active_cu_number"
        )
    if s.AMD_RDNA2_CUS == 24 and s.AMD_CU_UNLOCK_APPLIED:
        logger.warning(
            "⚠️  AMD_CU_UNLOCK_APPLIED=True mais AMD_RDNA2_CUS=24 — "
            "mettez AMD_RDNA2_CUS=40 dans .env pour que le calcul mémoire en profite."
        )


def _inject_rocm_env(s: "Settings") -> None:
    os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", s.HSA_OVERRIDE_GFX_VERSION)
    os.environ.setdefault(
        "PYTORCH_HIP_ALLOC_CONF",
        f"max_split_size_mb:{s.AMD_GTT_SIZE_MB // s.AMD_RDNA2_CUS}"
    )
