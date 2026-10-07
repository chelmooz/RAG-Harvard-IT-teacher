"""
Validators & (LEGACY) ROCm env injection for Prof IA configuration.
=================================================================
Extrait de config.py (PR P2 — audit « Validateurs → validators.py »).

Responsabilité v1.4 : valider les Settings.

`@deprecated _inject_rocm_env` est conservé pour traçabilité mais n'est **plus
appelé** (G2-T00) : ROCm n'est pas le chemin GPU de v1.4 (ADR-002 « Conséquences et risques »). Il
n'injecte donc plus `HSA_OVERRIDE_GFX_VERSION` ni `PYTORCH_HIP_ALLOC_CONF` dans
l'environnement du processus. Le chemin GPU v1.4 est Vulkan/RADV, exécuté par
llama.cpp sur l'hôte — voir ADR-002/003.
"""

import os
import secrets
import warnings
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
    """LEGACY / NON ACTIF — ne plus appeler (G2-T00).

    DÉPRÉCIÉ : ROCm n'est pas le chemin GPU de PROF IA v1.4. Le LLM utilise
    Vulkan/RADV via llama.cpp sur l'hôte ; embeddings et reranker sont CPU.
    Conservé pour traçabilité (ADR-002 « Conséquences et risques »), à supprimer après le gate matériel.

    Injectait `HSA_OVERRIDE_GFX_VERSION` et `PYTORCH_HIP_ALLOC_CONF` pour faire
    reconnaître gfx1013 à torch ROCm. Sans torch ROCm, ces variables n'ont aucun
    effet et surtout introduisaient deux hazards :

    - `PYTORCH_HIP_ALLOC_CONF` était calculé depuis `AMD_GTT_SIZE_MB` /
      `AMD_RDNA2_CUS`, les mêmes knobs qui pilotent `BATCH_SIZE` du CPU. Un
      contexte ROCm pouvait donc fausser le réglage CPU par pur effet de bord.
    - Le déterminisme du build CPU était compromis (cf. Dockerfile, G2-T00).
    """
    warnings.warn(
        "_inject_rocm_env() est LEGACY et n'est plus appelé sur le chemin v1.4 "
        "(G2-T00). Ne pas réintroduire l'injection ROCm.",
        DeprecationWarning,
        stacklevel=2,
    )
    os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", s.HSA_OVERRIDE_GFX_VERSION)
    os.environ.setdefault(
        "PYTORCH_HIP_ALLOC_CONF",
        f"max_split_size_mb:{s.AMD_GTT_SIZE_MB // s.AMD_RDNA2_CUS}"
    )
