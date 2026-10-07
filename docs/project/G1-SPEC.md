# G1 — Spécification de qualification pré-déploiement

**Statut :** à valider par XZ · **Date :** 2026-10-06 · **Gate :** G1 (IN PROGRESS)
**Périmètre :** qualification **par preuve en pré-déploiement**. Aucune conclusion de
viabilité physique sur BC-250 : la validation.material reste une gate de déploiement.

Cette spécification ne réécrit aucune décision validée. Les gates XZ restent la
source de décision ; le maître et les ADR restent normatifs.

---

## 1. Contexte et état constaté

Le candidat de qualification est `Qwen2.5-7B-Instruct` **Q6_K** GGUF. Le moteur est
`llama.cpp` compilé avec Vulkan, hors conteneur. L'instrument de caractérisation
est `scripts/benchmark/fit_campaign.sh`, piloté par `scripts/benchmark/run_matrix.sh`,
taxonomie de verdicts figée par XZ.

La qualification pré-déploiement a déjà produit des preuves tangibles :

| Fait | Preuve |
|---|---|
| `llama.cpp` se compile avec Vulkan | `-- Including Vulkan backend`, binaire `0.6.0-dev` (`f0c41e0`) |
| Tous les flags requis existent réellement | `-ngl -c -ctk -ctv -np -fa -b -ub --jinja` présents dans le `--help` réel |
| Le candidat est un vrai GGUF | magic `GGUF` v3, 339 tenseurs, 38 entrées, architecture `qwen2` |
| Empreinte réelle du candidat | `6254199488` octets, SHA256 `489138dfed4f04cd6dea56e5a8423e4aa05a0318cce2a4a72250fe1278e97cf8` |
| La chaîne complète répond | campagne réelle : **GREEN**, 4/4 configs, 0 OOM, 0 reset GPU |
| Le backend Vulkan décharge réellement | `offloaded 29/29 layers to GPU`, `Vulkan0 model buffer = 5532.43 MiB` |

## 2. Problème

Trois défauts de l'instrument ont été découverts en exerçant la chaîne réelle. Tous
produisent des rapports **plausibles mais faux**, ce qui est le mode de défaillance
que T0.-1 devait empêcher.

### 2.1 `gpu_layers` vaut toujours 0

L'extraction repose sur `grep "offloaded N/M layers to GPU"`. Or llama.cpp **n'émet
cette ligne qu'à partir d'une verbosité élevée**. À la verbosité par défaut, le champ
vaut 0 y compris quand 29/29 couches sont déchargées.

*Impact :* le rapport affirme qu'aucun déchargement GPU n'a eu lieu alors que la
totalité l'a été. Un opérateur peut en déduire un diagnostic mémoire faux.

### 2.2 `rss_peak_mib` ne représente pas l'empreinte du modèle

Quand le modèle est déchargé, les poids résident dans le buffer Vulkan, pas dans la
RAM du processus. La RSS relevée (≈1 043 Mo) est alors sans rapport avec l'empreinte
réelle (5 532 Mo côté device). L'indicateur principal de la caractérisation
mémoire est donc **inutilisable tel quel** en présence d'offload.

*Impact :* un budget mémoire calculé sur la RSS Conclusionnerait à tort que le modèle
tient largement, alors que la mémoire unifiée de la cible est précisément la
contrainte.

### 2.3 Le repli CPU de `-ngl 999` n'est pas établi

La documentation du service affirme que `-ngl 999` « retombe en CPU si VRAM
insuffisante ». Aucune mesure ne le confirme. La seule observation disponible montre
un déchargement complet, sans cas d'échec.

*Impact :* une affirmation non mesurée dans une configuration de production.

## 3. Solution

Rendre l'instrument capable de décrire **où** le modèle réside réellement, et
retirer de la documentation toute affirmation non mesurée.

1. Extraire les tailles de buffers que llama.cpp publie lui-même (`Vulkan0`,
   `CPU_Mapped`, `CPU`), en montant la verbosité si nécessaire. Ce sont des **données**,
   au même titre que `RSS`.
2. Reporter le déchargement réel (`gpu_layers`) et son origine (Vulkan ou CPU).
3. Remplacer `rss_peak_mib` comme indicateur principal par une décomposition
   explicite : `device_buffer_mib`, `host_buffer_mib`, `rss_mib`.
4. Ramener l'affirmation de repli CPU à ce qui est établi, ou la retirer.

Aucune de ces corrections n'introduit de seuil. Elles ajoutent de l'observabilité.

## 4. Histoires utilisateur

1. Comme opérateur, je veux que le rapport indique le nombre **réel** de couches
   déchargées, afin de ne pas diagnostiquer à tort un défaut d'offload.
2. Comme opérateur, je veux connaître la **répartition mémoire** réelle (device vs
   hôte), afin de comparer utilement une configuration à la cible.
3. Comme opérateur, je veux que la source du déchargement soit nommée (Vulkan ou CPU),
   afin de distinguer « GPU utilisé » de « repli silencieux ».
4. Comme mainteneur, je veux qu'aucune documentation n'affirme un repli CPU non
   mesuré, afin de ne pas propager une garantie fictive.
5. Comme mainteneur, je veux que la détection du déchargement soit vérifiée par un
   test qui reproduit le cas réel, afin qu'elle ne retombe pas à zéro silencieusement.
6. Comme XZ, je veux que la taxonomie de verdicts reste inchangée, afin que la
   comparabilité des campagnes soit préservée.
7. Comme XZ, je veux qu'aucun seuil de débit ou de mémoire ne soit introduit, afin
   qu'aucun résultat ne soit transformé artificiellement en GREEN.
8. Comme opérateur, je veux que `METRIC_MISSING` reste INCONCLUSIVE, afin qu'une
   métrique absente ne condamne pas une machine.

## 5. Décisions d'implémentation

- L'extraction du déchargement s'appuie sur les lignes que llama.cpp publie, avec
  montée de la verbosité si la ligne est absente du flux par défaut.
- Le rapport conserve les champs existants et **en ajoute** ; aucun champ n'est
  retiré dans cette passe, pour que les campagnes déjà archivées restent lisibles.
- La répartition mémoire est lue dans le flux du serveur au chargement, pas
  échantillonnée pendant les requêtes.
- L'indicateur `rss_mib` reste présent et gagne un qualificatif explicite.

### 5.1 Lecture de l'empreinte après correction

Le rapport expose désormais, dans `startup` :

- `gpu_layers` : nombre de couches réellement déchargées, `null` si le serveur n'a
  publié aucune ligne d'offload. Un offload `0/29` reste `0` : c'est une
  observation, pas une absence.
- `offload_backend` : `GPU`, `CPU`, ou `null` si la ligne d'offload est absente.
- `device_buffer_mib` : poids côté accélérateur, `null` si aucun buffer device.
- `host_buffer_mib` : poids côté hôte, `null` si aucun buffer hôte.
- `model_buffer_mib` : somme des buffers publiés par le serveur.

`summary.rss_peak_mib` reste disponible mais ne doit **plus** être lu comme
l'empreinte du modèle. Sur la campagne réelle, la RSS valait 1 043 Mo pour un
modèle de 6 254 Mo : les poids étaient dans le buffer device. Une campagne doit
donc être comparée à une cible en mémoire unifiée via `model_buffer_mib`, et
`rss_peak_mib` ne sert qu'à suivre la mémoire résidente du processus.
- Le commentaire du service systemd sur le repli CPU est reformulé pour n'affirmer
  que ce qui a été observé.
- Aucun changement de taxonomie, de seuil ou de runtime.
- Les données non disponibles restent `null` avec un drapeau, jamais une valeur
  substituée.

## 6. Décisions de test

Un bon test ici vérifie un **comportement externe observable** : la valeur
rapportée reflète-t-elle ce que le serveur a réellement publié ?

- Priorité aux tests d'intégration contre le binaire et le modèle réels, dans le
  bac. C'est la seule façon de reproduire le défaut 2.1 : un stub dont le `--help`
  et le flux de chargement sont synthétiques ne l'exposerait pas.
- Un test unitaire doit pouvoir reproduire le cas « ligne absente à verbosité par
  défaut » pour prouver que la correction ne dépend pas de la verbosité.
- Le test doit être en échec avant la correction : c'est la preuve que le test
  détecte bien la régression.
- Les 101 tests existants sont conservés et doivent rester verts.
- Aucun test ne doit devenir plus permissif.

## 7. Hors périmètre

- Toute conclusion de viabilité sur BC-250.
- Le rechargement CPU automatique de `-ngl 999` : à qualifier sur la cible, pas ici.
- ROCm, CUDA, tout autre runtime.
- Le client web, Odysseus, MCP : horizon **G8**, documenté, non implémenté.
- Le passage à Docker/Compose pour le backend : les composants applicatifs ne sont
  pas construits.
- La correction d'ADR-003 sur le nommage réseau : constatée, mais relève d'une
  décision XZ distincte.

## 8. Notes

- `INSTALLATION.md` est cité comme référence de déploiement mais **n'existe pas** dans
  le dépôt. À créer, ou à retirer de la liste des références.
- Aucun issue tracker n'est configuré ; le suivi se fait par `docs/project/`, ce qui
  évite une seconde source de vérité.
- L'écart Debian 13 (noyau `6.12.111` en stable, `7.2.6` en backports ; Mesa stable
  `25.0.x` sous le plancher BC-250 de `25.1`) est établi et doit être tranché avant
  la campagne réelle.