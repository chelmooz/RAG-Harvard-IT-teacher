# experimental/ — Code hors perimetre de production

Ce repertoire contient des scripts **experimentaux**, volontairement **exclus**
du flux principal de l'application Prof IA (aucun import depuis `backend/api`).
Ils servent de reference ou de developpement futur, mais ne doivent pas etre
considers comme stables ni testes par la CI.

---

## fine_tuning/train.py — BLOQUE par le materiel (BC-250 / gfx1013)

Script de fine-tuning QLoRA 4-bit (PEFT + SFTTrainer, `transformers.BitsAndBytesConfig`).

### Blocage materiel (HW-blocker)

Le BC-250 embarque un GPU **Cyan Skillfish (gfx1013, RDNA2)**. Or :

- **bitsandbytes ROCm ne supporte pas gfx1013** dans ses builds officiels.
  QLoRA 4-bit (`load_in_4bit=True`) repose sur bitsandbytes, donc le
  fine-tuning echoue au chargement du modele sur le BC-250 **en configuration
  stock** (ROCm systeme par defaut).
- Le fine-tuning necessite la **Phase 2** du deploiement : un build ROCm
  custom de bitsandbytes (ou une version de la lib ajoutant le target gfx1013).
  Sans cela, le script n'est pas executable sur cette machine.

### Prerequis supplementaires (si Phase 2 debloquee)

1. **Liberer la VRAM** : arreter Ollama (`systemctl stop ollama`) — le script
   quantifie Qwen3-14B en 4-bit (~8 Go) qui doit tenir dans les ~12 Go BC-250
   sans partage avec l'inference.
2. **Golden dataset** : definir `FINE_TUNING_DB_URL` (meme instance PostgreSQL
   que le backend) ; le script lit les lignes `is_golden=true` de
   `response_evaluations`.
3. Lancer depuis `experimental/fine_tuning/` :
   ```bash
   cd experimental/fine_tuning
   python train.py
   ```

### Statut

| Element            | Etat                                              |
|--------------------|---------------------------------------------------|
| Script             | Present (`train.py` + `config.yaml`)              |
| Executable BC-250  | BLOQUE — bitsandbytes ROCm vs gfx1013             |
| Debloque           | Phase 2 (build ROCm custom) — hors scope v6.0     |
| Auto-scoring LLM   | NON cable (`AUTO_EVALUATE=False` dans config)     |

Le job d'auto-scoring (LLM-juge) n'est pas encore implemente ; le marquage
`is_golden` repose aujourd'hui uniquement sur le feedback humain via
`POST /feedback`.
