# Cahier des charges — Bot SkillUp

**Projet :** Bot Discord d'accompagnement des sessions SkillUp
**Communauté :** Alumni CPS — Initiative SkillUp
**Version du document :** 1.4
**Statut :** Complet — prêt pour l'implémentation
**Auteur :** Abdoul A. M. DIOUF
**Périmètre de cette version :** V1 (MVP)

---

## 1. Contexte

Alumni CPS est une communauté qui porte plusieurs **initiatives**, c'est-à-dire des projets au service de ses membres (CPS Connect, SkillUp, CPSport, etc.).

**SkillUp** est l'initiative dédiée à la montée en compétence collective. Son principe : au lieu de préparer seul dans son coin une certification, une formation ou un projet, chaque membre avance **avec les autres**, en sessions de coworking sur Discord (caméra allumée, ambiance « salle de classe »), pour rester régulier et motivé.

Le fonctionnement de la **première vague** (lancée le 2 août 2026, clôturée au Bootcamp des 29-30 août) repose sur quelques mécaniques clés :

- Chaque membre fixe un **objectif global** pour toute la vague (ex. obtenir une certification Databricks).
- Le travail se fait en **sessions quotidiennes**, sur l'un des trois créneaux proposés selon les disponibilités.
- Chaque session ouvre sur un **objectif de session** et se clôture par un **bilan de session**.
- En fin de semaine, une **réunion de bilan hebdomadaire** fait le point sur la progression.
- La vague progresse par étapes : **semaine 1 en solo** (phase d'acclimatation), puis travail **en binômes** constitués par proximité de domaine (ex. deux membres sur Databricks, deux membres sur la cybersécurité).
- À partir du travail en binôme, les **bilans hebdomadaires se font en regards croisés** : chaque membre présente le bilan de son binôme, et réciproquement.

La vague compte **8 membres** aux profils variés (étudiant, demandeur d'emploi, cadre, alternant), le point commun étant l'intention de monter en compétence.

Aujourd'hui, les données du niveau **vague** (objectifs globaux + bilans hebdomadaires) sont gérées dans un **forum Discord `objectifs`** : un post par membre, avec les réponses de bilan attachées. Ce niveau fonctionne correctement et reste consultable dans le temps.

---

## 2. Problématique

Le niveau **session** (objectif de début et bilan de fin, chaque jour, sur chaque créneau) n'a **pas de source de vérité durable**. Ces informations sont saisies dans les salons vocaux/textuels de coworking, où :

- au bout de quelques jours, les messages sont **ensevelis** ;
- pour reconstituer la semaine passée d'un membre, il faut **scroller manuellement** les salons de coworking ;
- il n'existe **aucune agrégation automatique** : le bilan hebdomadaire est reconstitué à la main ;
- la mécanique des **bilans croisés en binôme** est particulièrement pénible : pour écrire le bilan de son binôme, il faut retrouver toutes ses sessions dispersées.

Le problème n'est pas Discord en soi, mais l'**absence d'un référentiel structuré au niveau session** et d'une **restitution automatisée**.

---

## 3. Objectifs du projet

Le bot SkillUp doit :

1. **Centraliser** la saisie des sessions (objectif de début, bilan de fin) dans un référentiel unique et durable.
2. **Restituer instantanément** le journal d'un membre ou de son binôme sur une semaine, sans avoir à scroller.
3. **Automatiser** la génération des bilans hebdomadaires (par membre et par binôme) à partir des sessions saisies.
4. **Faciliter les bilans croisés** : permettre à chaque membre de retrouver en une commande toutes les sessions de son binôme.
5. Rester **simple à utiliser** (au fil de l'eau, sans friction) et **simple à maintenir** (petite équipe, petit effectif).

**Indicateur de réussite V1 :** un membre peut préparer le bilan de son binôme en lisant un journal propre généré par le bot, sans jamais retourner scroller les salons de coworking.

---

## 4. Périmètre

### 4.1 Dans le périmètre de la V1 (MVP)

- Enregistrement d'une session (début + fin) via commandes.
- Consultation de son propre journal de sessions sur une semaine.
- Consultation du journal de son binôme sur une semaine.
- Génération d'un bilan hebdomadaire agrégé (par membre).
- Gestion des vagues, des membres et des binômes (côté admin).
- Enregistrement de l'objectif global de vague de chaque membre (pour contexte dans les bilans).

### 4.2 Hors périmètre V1 — reporté en backlog (voir §16)

- Streaks / séries de régularité.
- Cumul d'heures de coworking et statistiques de présence.
- Rappels automatiques à l'ouverture des créneaux.
- Classements / gamification.
- Dashboard web externe.
- Multi-vague avancé (comparaison entre vagues, historique long).

**Principe directeur :** sortir vite le plus petit outil qui supprime la douleur actuelle, le faire adopter par les 8 membres, puis itérer. On ne code pas la V2 tant que la V1 n'est pas utilisée.

---

## 5. Acteurs et rôles

| Acteur | Description | Ce qu'il peut faire |
|---|---|---|
| **Membre SkillUp** | Participant de la vague en cours | Enregistrer ses sessions, consulter son journal, consulter le journal de son binôme, générer son bilan de semaine, définir son objectif de vague |
| **Admin SkillUp** | Équipe qui pilote l'initiative | Tout ce qu'un membre peut faire + créer/gérer les vagues, ajouter/éditer les membres, définir les binômes de la semaine, générer le bilan de n'importe quel membre |
| **Bot** | Application automatisée | Horodater, stocker, agréger et restituer les données |

L'appartenance à un rôle est déterminée par les **rôles Discord** (un rôle `Admin SkillUp` sur le serveur).

---

## 6. Vocabulaire et concepts clés

| Terme | Définition |
|---|---|
| **Vague** | Cycle SkillUp d'environ un mois, du lancement au Bootcamp. La V1 concerne la vague d'août 2026. |
| **Membre** | Participant inscrit à une vague. |
| **Objectif global (de vague)** | But que le membre vise sur toute la vague (ex. « obtenir la certification Databricks Data Engineer Associate »). |
| **Créneau** | Plage horaire de coworking. Trois valeurs possibles : `5h-7h`, `19h-21h`, `21h-23h`. |
| **Canal de coworking** | Salon vocal Discord dans lequel se déroule effectivement la session (ex. Coworking 1, Coworking 2). Le canal utilisé **peut varier** d'un créneau ou d'un jour à l'autre : il est donc **détecté**, non présumé. |
| **Session** | Une période de travail sur un créneau donné, avec un objectif de début et un bilan de fin. |
| **Objectif de session** | Ce que le membre compte accomplir pendant la session. |
| **Bilan de session** | Ce qui a réellement été fait + blocages rencontrés. |
| **Semaine SkillUp** | Unité de temps servant aux bilans hebdomadaires (S1, S2, …), du **lundi au dimanche** (RG-14). |
| **Binôme** | Association de deux membres sur une semaine donnée, généralement par proximité de domaine. Peut changer d'une semaine à l'autre. |
| **Bilan hebdomadaire** | Synthèse des sessions d'un membre sur une semaine. En travail en binôme, il est présenté en **regards croisés** (chacun présente celui de l'autre). |

---

## 7. Règles de gestion

- **RG-01** — Les créneaux autorisés sont exactement : `5h-7h`, `19h-21h`, `21h-23h`. Toute session est rattachée à l'un de ces créneaux.
- **RG-02** — Un membre ne peut avoir **qu'une seule session ouverte** (démarrée mais non clôturée) à la fois.
- **RG-03** — Une session est considérée comme **complète** lorsqu'elle possède un objectif de début **et** un bilan de fin. Une session ouverte non clôturée en fin de journée est marquée comme **incomplète** (clôture automatique, voir RG-16).
- **RG-04** — L'**horodatage** de début et de fin est enregistré automatiquement par le bot ; la **durée réelle** de la session en est déduite (fin − début).
- **RG-05** — Une session appartient à **une semaine SkillUp** et à **une vague**, déterminées par sa date.
- **RG-06** — Les **binômes sont définis par semaine**. Un membre peut être en solo une semaine et en binôme la suivante. Le journal du binôme (`/binome-journal`) se base sur le binôme **de la semaine consultée**.
- **RG-07** — Un membre a **un seul objectif global** par vague (modifiable).
- **RG-08** — Seuls les **admins** peuvent créer une vague, gérer les membres et définir les binômes.
- **RG-09** — Un membre ne peut consulter/modifier que **ses propres sessions** ; il peut **lire** (sans modifier) le journal de son binôme. Un admin peut lire le journal de tout membre.
- **RG-10** — Toutes les heures (créneaux, horodatages) sont gérées dans le fuseau de référence de la communauté : **Europe/Paris** (voir RG-15).
- **RG-11** — Au démarrage d'une session, le bot **détecte automatiquement le salon vocal** dans lequel se trouve le membre et l'enregistre. Le canal n'est pas saisi manuellement ni déduit d'une correspondance figée créneau → canal (celle-ci serait fragile puisque le canal peut changer).
- **RG-12** — Une session ne peut être démarrée que si le membre est présent dans un **salon reconnu comme salon de coworking** (liste configurable, voir §10 `coworking_channels` — en V1 : les salons Coworking uniquement, à l'exclusion du salon Live). Si le membre n'est dans aucun salon de coworking au moment du `/session-start`, la commande est **refusée** et un **message d'avertissement explicite** lui est renvoyé (ex. « Rejoins un salon de coworking avant de démarrer ta session »).
- **RG-13** — Un membre peut enchaîner **plusieurs sessions dans la même journée** (ex. créneau 5h-7h puis 19h-21h). Chaque créneau du jour donne lieu à une session distincte dans `sessions`. Cela reste compatible avec RG-02 : il ne peut simplement pas y avoir **deux sessions ouvertes en même temps**.
- **RG-14** — La **semaine SkillUp** court du **lundi au dimanche**. Le dimanche de lancement de la vague n'est pas compté comme un jour de la semaine 1 (jour de kickoff hors-semaine) ; le bilan hebdomadaire du dimanche clôture la semaine qui vient de s'écouler.
- **RG-15** — Le **fuseau horaire de référence** est **Europe/Paris**. Il doit être géré comme un fuseau nommé (pas un simple décalage fixe), afin que les passages heure d'été/heure d'hiver soient pris en compte automatiquement dans les horodatages et les créneaux.
- **RG-16** — Une session restée **ouverte à minuit** (fin de journée dans le fuseau de référence) est **clôturée automatiquement** par le bot, avec le statut **« incomplète »** (pas de bilan renseigné). Cela évite qu'une session oubliée bloque le membre pour ses sessions suivantes (RG-02).

---

## 8. Besoins fonctionnels (vue d'ensemble)

| Réf. | Besoin | Priorité |
|---|---|---|
| BF-01 | Démarrer une session (créneau + objectif) | Indispensable |
| BF-02 | Clôturer une session (bilan + blocages) | Indispensable |
| BF-03 | Consulter son journal de la semaine | Indispensable |
| BF-04 | Consulter le journal de son binôme de la semaine | Indispensable (killer feature) |
| BF-05 | Générer le bilan hebdomadaire agrégé d'un membre | Indispensable |
| BF-06 | Définir / mettre à jour son objectif global de vague | Important |
| BF-07 | Créer et gérer une vague (admin) | Indispensable |
| BF-08 | Ajouter / éditer un membre (admin) | Indispensable |
| BF-09 | Définir les binômes d'une semaine (admin) | Indispensable |
| BF-10 | Corriger / supprimer une session saisie par erreur | Important |

---

## 9. Spécification des commandes (slash-commands)

> Convention : les commandes membres commencent par un verbe d'action clair. Les paramètres entre `[ ]` sont optionnels.

### 9.1 Commandes membre

#### `/session-start`
- **Acteur :** membre
- **Description :** démarre une session de coworking.
- **Paramètres :**
  - `créneau` (obligatoire) — liste de choix : `5h-7h`, `19h-21h`, `21h-23h`
  - `objectif` (obligatoire) — texte libre : objectif de la session
- **Comportement :** crée une session ouverte, horodatée au moment de la commande, rattachée au membre, à la semaine et à la vague en cours. Le bot **lit l'état vocal du membre** et enregistre automatiquement le **salon de coworking** où il se trouve (RG-11).
- **Contrôles :** refuse si le membre a déjà une session ouverte (RG-02) ; **refuse avec message d'avertissement** si le membre n'est pas dans un salon de coworking reconnu (RG-12).
- **Sortie :** confirmation privée avec le récap de la session ouverte (créneau + canal détecté).

#### `/session-end`
- **Acteur :** membre
- **Description :** clôture la session en cours.
- **Paramètres :**
  - `bilan` (obligatoire) — texte libre : ce qui a été fait
  - `blocages` (optionnel) — texte libre : difficultés rencontrées
- **Comportement :** clôture la session ouverte, enregistre l'heure de fin, calcule la durée (RG-04).
- **Contrôles :** refuse s'il n'y a pas de session ouverte.
- **Sortie :** confirmation avec durée et récap.

#### `/mon-journal`
- **Acteur :** membre
- **Description :** affiche ses sessions.
- **Paramètres :**
  - `semaine` (optionnel) — n° de semaine (S1, S2, …) ; défaut : semaine en cours
- **Sortie :** liste chronologique des sessions (date, créneau, objectif, bilan, blocages, durée).

#### `/binome-journal`
- **Acteur :** membre
- **Description :** affiche les sessions de son binôme sur une semaine. **Fonctionnalité centrale pour les bilans croisés.**
- **Paramètres :**
  - `semaine` (optionnel) — défaut : semaine en cours
- **Comportement :** identifie le binôme du membre pour la semaine demandée (RG-06), puis restitue le journal du partenaire.
- **Contrôles :** message clair si le membre était en solo cette semaine-là (pas de binôme défini).
- **Sortie :** journal du partenaire (lecture seule), formaté prêt à servir de base au bilan.

#### `/bilan-semaine`
- **Acteur :** membre (pour lui-même) / admin (pour tout membre)
- **Description :** génère un bilan hebdomadaire agrégé.
- **Paramètres :**
  - `membre` (optionnel, admin uniquement) — défaut : soi-même
  - `semaine` (optionnel) — défaut : semaine en cours
  - `poster` (optionnel, booléen — ajout 2026-08-14) — défaut : `false` (aperçu ephemeral, rien n'est écrit dans le forum). Passer `true` pour poster réellement (le post en thread n'est pas idempotent : chaque appel avec `poster:true` ajoute un nouveau message, sans édition ni déduplication — d'où le défaut prudent à `false`).
- **Comportement :** agrège les sessions de la semaine (nombre de sessions, temps total, objectifs atteints/non atteints, blocages récurrents) et met en forme un récap.
- **Sortie *(mise à jour 2026-08-14, décision #7 révisée — voir §17)* :** par défaut (`poster:false`), le bilan reste affiché en ephemeral, comme avant. Si `poster:true` et que le membre a un post objectif lié (`thread_objectif_id` renseigné), le bot **poste directement le bilan en réponse dans ce post**, sur le forum `objectifs` (confirmation ephemeral). Si `poster:true` mais aucun post n'est lié, le bilan reste affiché en ephemeral avec une invite à utiliser `/objectif-vague` ou à demander à un admin `/membre-lier-thread`.

#### `/objectif-vague`
- **Acteur :** membre
- **Description :** définit ou met à jour son objectif global de la vague.
- **Paramètres :**
  - `objectif` (obligatoire) — texte libre
- **Comportement :** enregistre/écrase l'objectif global du membre pour la vague en cours (RG-07).
- **Intégration forum *(ajout 2026-08-14, décision #7 révisée — voir §17)* :** au premier appel, crée automatiquement un post dans le forum `objectifs` (titre « Objectif <nom> », contenu = l'objectif), et enregistre son identifiant dans `members.thread_objectif_id`. Aux appels suivants, **édite ce même post** au lieu d'en créer un nouveau. Si le forum est introuvable sur le serveur, l'objectif reste enregistré côté bot avec un avertissement ephemeral.

#### `/session-corriger` *(BF-10)*
- **Acteur :** membre (ses sessions) / admin (toutes)
- **Description :** corrige ou supprime une session saisie par erreur.
- **Paramètres :**
  - `id_session` (obligatoire)
  - `champ` (obligatoire) — objectif / bilan / blocages / créneau / suppression
  - `valeur` (selon le cas)

### 9.2 Commandes admin

#### `/vague-creer`
- **Paramètres :** `nom`, `date_debut`, `date_fin`
- **Comportement :** crée une nouvelle vague et la définit comme vague active.

#### `/membre-ajouter`
- **Paramètres :** `@utilisateur`, `profil` (étudiant / demandeur d'emploi / cadre / alternant / autre), `certif_ou_projet` (optionnel)
- **Comportement :** enregistre un membre dans la vague active.

#### `/membre-editer`
- **Paramètres :** `@utilisateur`, `champ`, `valeur`

#### `/membre-lier-thread` *(ajout 2026-08-14, décision #7 révisée — voir §17)*
- **Paramètres :** `@utilisateur`, `lien_ou_id` (lien du post Discord ou ID brut)
- **Comportement :** rattache manuellement un post existant du forum `objectifs` au membre (`members.thread_objectif_id`). Nécessaire pour les membres dont le post a été créé à la main **avant** l'automatisation par le bot — sans ce rattachement, `/bilan-semaine` ne trouve pas de post où répondre.

#### `/binome-definir`
- **Paramètres :** `semaine`, `@membre_a`, `@membre_b`
- **Comportement :** associe deux membres pour la semaine indiquée (RG-06). Les membres sans binôme cette semaine-là sont considérés en solo.

#### `/salon-coworking-ajouter` / `/salon-coworking-retirer` *(révisé 2026-08-14)*
- **Paramètres :** aucun — la commande ouvre un **menu de sélection multiple** (jusqu'à 25 salons).
- **Comportement :** les salons sont désormais **rattachés à la vague active** (`coworking_channels.wave_id` — auparavant, un salon coworking était global, valable pour toutes les vagues sans distinction). `/salon-coworking-ajouter` ne propose que les salons vocaux du serveur **pas encore ajoutés à la vague active** (pas de doublon possible à l'usage) ; `/salon-coworking-retirer` ne propose que ceux déjà liés. Les deux permettent de sélectionner plusieurs salons en un seul appel. La sélection dans le menu ne fait qu'aperçu (rien n'est encore écrit en base) — un **bouton « Valider »** confirme et déclenche l'ajout/retrait effectif.

#### `/salons-coworking-lister` *(ajout 2026-08-14)*
- **Paramètres :** `vague` (optionnel) — défaut : toutes les vagues
- **Comportement :** liste les salons de coworking avec, pour chacun, la vague à laquelle il est rattaché et son statut (actif/inactif) — répond au manque de visibilité relevé en usage (« quel salon est rattaché à quelle vague »).

---

## 10. Modèle de données

Modèle relationnel minimal, pensé pour être simple et évolutif.

### Table `waves` (vagues)
| Champ | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Identifiant |
| nom | TEXT | Ex. « Vague Août 2026 » |
| date_debut | DATE | Date de lancement |
| date_fin | DATE | Date de clôture (Bootcamp) |
| active | BOOLEAN | Vague en cours ou non |

### Table `members` (membres)
| Champ | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Identifiant interne |
| discord_id | TEXT | Identifiant Discord |
| nom | TEXT | Nom affiché |
| profil | TEXT | étudiant / demandeur d'emploi / cadre / alternant / autre |
| certif_ou_projet | TEXT | Ex. « Databricks Data Engineer Associate » |
| objectif_vague | TEXT | Objectif global de la vague |
| thread_objectif_id | TEXT | ID du post Discord du membre dans le forum `objectifs` (NULL si aucun post lié — ajout 2026-08-14, voir §17 décision #7) |
| wave_id | INTEGER (FK → waves.id) | Vague de rattachement |

### Table `sessions`
| Champ | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Identifiant |
| member_id | INTEGER (FK → members.id) | Auteur |
| wave_id | INTEGER (FK → waves.id) | Vague |
| semaine | INTEGER | N° de semaine SkillUp (1, 2, …) |
| date | DATE | Jour de la session |
| creneau | TEXT | `5h-7h` / `19h-21h` / `21h-23h` |
| canal_id | TEXT | Identifiant Discord du salon vocal détecté au démarrage (NULL si non détecté) |
| canal_nom | TEXT | Nom lisible du salon (ex. « Coworking 1 »), figé au moment de la session |
| debut | DATETIME | Horodatage de `/session-start` |
| fin | DATETIME | Horodatage de `/session-end` (NULL si ouverte) |
| objectif | TEXT | Objectif de session |
| bilan | TEXT | Bilan de session (NULL tant qu'ouverte) |
| blocages | TEXT | Difficultés (optionnel) |
| statut | TEXT | ouverte / complète / incomplète |

### Table `binomes`
| Champ | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Identifiant |
| wave_id | INTEGER (FK → waves.id) | Vague |
| semaine | INTEGER | N° de semaine concernée |
| membre_a | INTEGER (FK → members.id) | Premier membre |
| membre_b | INTEGER (FK → members.id) | Second membre |

### Table `coworking_channels` (salons reconnus comme coworking)
| Champ | Type | Description |
|---|---|---|
| id | INTEGER (PK) | Identifiant interne |
| canal_id | TEXT | Identifiant Discord du salon vocal |
| canal_nom | TEXT | Nom lisible (ex. « Coworking 1 ») |
| actif | BOOLEAN | Salon pris en compte ou non pour les sessions |
| wave_id | INTEGER (FK → waves.id) | Vague de rattachement (ajout 2026-08-14 — auparavant un salon était global, valable pour toutes les vagues) |

> Cette table permet au bot de savoir **quels salons comptent comme coworking** (Coworking 1, Coworking 2… — le salon « Live » étant probablement à exclure). Elle est gérée par les admins et évite tout codage en dur des salons. Contrainte `UNIQUE (canal_id, wave_id)` : un même salon Discord peut être réutilisé d'une vague à l'autre, mais chaque vague a sa propre liste.

**Relations principales :**
- une vague possède plusieurs membres, sessions et binômes ;
- un membre possède plusieurs sessions ;
- un binôme relie deux membres pour une semaine donnée.

**Requête type (killer feature) :** `/binome-journal` = sélectionner, dans `binomes`, la ligne où figure le membre pour la semaine → identifier le partenaire → lister ses `sessions` de cette semaine.

---

## 11. Contraintes techniques

- **Langage :** Python (aligné avec le profil data engineer de l'auteur et sa certification en cours).
- **Bibliothèque Discord :** `discord.py` (slash-commands + modals pour les formulaires de saisie).
- **Base de données :** SQLite en V1 (un simple fichier, aucune infrastructure à gérer pour 8 membres). Migration possible vers PostgreSQL si l'effectif grandit ou si plusieurs vagues coexistent.
- **Interface de saisie :** privilégier les **modals** (fenêtres de formulaire Discord) pour les champs texte longs (objectif, bilan), afin de réduire la friction.
- **Détection vocale :** le bot doit activer l'**intent des états vocaux** (`GUILD_VOICE_STATES` / `voice_states`) pour lire le salon dans lequel se trouve le membre au démarrage d'une session (RG-11). Cet intent est aussi le socle nécessaire à la future détection automatique des sessions (V2).
- **Hébergement :** **hors périmètre de ce document**, à traiter au moment du déploiement (un bot doit tourner en continu). Point d'attention connu : les offres gratuites qui se mettent en veille ne conviennent pas.
- **Propriété / maintenance :** un responsable identifié doit détenir le bot (token, hébergement, sauvegardes). En V1 : l'auteur.

---

## 12. Exigences non-fonctionnelles

- **Simplicité d'usage :** une session doit se déclarer en quelques secondes, sans quitter Discord.
- **Fiabilité :** aucune perte de session enregistrée ; sauvegarde régulière du fichier de base de données.
- **Maintenabilité :** code lisible et commenté, modèle de données stable, dépendances minimales.
- **Lisibilité des restitutions :** journaux et bilans formatés proprement, directement copiables dans le forum `objectifs`.
- **Robustesse :** messages d'erreur clairs (session déjà ouverte, pas de binôme cette semaine, etc.).
- **Évolutivité :** le modèle de données doit permettre d'ajouter streaks, statistiques et rappels sans refonte.

---

## 13. Sécurité et données personnelles

- Les données stockées sont **peu sensibles** (objectifs de travail, bilans, identifiants Discord), mais restent des données personnelles des membres.
- **Accès :** un membre ne voit que ses données et celles de son binôme (lecture seule) ; les admins ont un accès élargi (RG-09).
- **Token du bot :** stocké hors du code (variable d'environnement / fichier de configuration non versionné).
- **Consentement :** l'usage du bot s'inscrit dans le cadre de l'initiative SkillUp ; informer les membres de ce qui est stocké.
- **Suppression :** prévoir la possibilité de purger les données d'un membre sur demande.

---

## 14. Livrables

1. Le présent **cahier des charges** validé.
2. Le **schéma de base de données** (script de création des tables).
3. Le **code source du bot** (dépôt versionné).
4. Un **guide d'utilisation court** pour les 8 membres (liste des commandes + exemples).
5. Une **procédure de déploiement/sauvegarde** (à compléter avec le choix d'hébergement).

---

## 15. Planning indicatif

Contrainte : la vague se termine au Bootcamp des **29-30 août 2026**. L'objectif est de disposer d'une V1 utilisable **avant la fin de la vague**, pour la faire tester en conditions réelles.

| Étape | Contenu | Repère |
|---|---|---|
| J1 | Squelette du bot (connexion + `/session-start`) | Immédiat |
| J1-J3 | Cycle complet `/session-start` → `/session-end` + stockage | Court terme |
| Semaine en cours | `/mon-journal`, `/binome-journal`, `/bilan-semaine` | MVP fonctionnel |
| Avant le Bootcamp | Commandes admin + guide d'utilisation + tests par les 8 | V1 livrée |
| Après le Bootcamp | Rétrospective d'usage → priorisation V2 | Itération |

---

## 16. Évolutions futures (backlog V2+)

- **Streaks** : suivi de la régularité (nombre de jours consécutifs avec au moins une session).
- **Sessions pilotées par la présence vocale** : le bot écoute les entrées/sorties des salons de coworking, ouvre/clôture les sessions automatiquement, calcule la **durée réelle de présence** et fiabilise le canal utilisé. Gère les cas limites (reconnexion, changement de salon, bot hors-ligne, AFK).
- **Statistiques** : heures cumulées de coworking, présence par créneau, taux d'objectifs atteints, répartition par salon.
- **Rappels automatiques** à l'ouverture de chaque créneau.
- **Classements / gamification** légère pour la motivation.
- **Génération automatique du bilan de binôme** (fusion des deux journaux, prêt pour la présentation croisée).
- **Dashboard web** de visualisation (si SkillUp grandit).
- **Support multi-vague** : historique, comparaisons, réinscription simplifiée.
- **Export** des données (CSV) — utile aussi comme exercice data engineering.

---

## 17. Décisions actées

Tous les points initialement ouverts ont été tranchés. Cette section fait office de journal de décisions, pour traçabilité.

| # | Sujet | Décision | Règle associée |
|---|---|---|---|
| 1 | Bornes de la semaine SkillUp | **Lundi → Dimanche** (le dimanche de lancement de vague est hors-semaine ; le bilan du dimanche clôture la semaine écoulée) | RG-14 |
| 2 | Fuseau horaire de référence | **Europe/Paris** (fuseau nommé, DST géré automatiquement) | RG-10, RG-15 |
| 3 | Clôture des sessions oubliées | **Clôture automatique à minuit**, statut « incomplète » — évite qu'une session oubliée bloque le membre le lendemain (RG-02) | RG-16 |
| 4 | Salons comptant comme coworking | **Salons Coworking uniquement**, le salon Live est exclu | RG-12 |
| 5 | Session lancée hors vocal de coworking | **Refus de la commande + message d'avertissement explicite** | RG-12 |
| 6 | Multi-session par jour | **Autorisé** — un membre peut enchaîner plusieurs créneaux le même jour | RG-13 |
| 7 | Rôle du bot vis-à-vis du forum `objectifs` | ~~Le bot produit un texte copiable ; il n'écrit pas automatiquement dans le forum (garde un humain dans la boucle avant publication).~~ **Révisé le 2026-08-14**, à la demande du gestionnaire du serveur prod : le bot **écrit directement dans le forum**. `/objectif-vague` crée le post au premier appel puis édite ce même post aux appels suivants (`members.thread_objectif_id`). `/bilan-semaine` poste sa réponse en reply dans ce post plutôt qu'en affichage ephemeral. Les posts créés à la main avant cette date n'ont pas de `thread_objectif_id` — rattachement ponctuel via `/membre-lier-thread` (nouvelle commande admin). | §9.1 `/objectif-vague`, `/bilan-semaine` ; §9.2 `/membre-lier-thread` ; §10 `members.thread_objectif_id` |
| 8 | Comportement de `/binome-journal` en solo | **Message explicite** informant le membre qu'il était en solo cette semaine-là (pas d'erreur technique) | §9.1 `/binome-journal` |

Le cahier des charges est considéré **complet et prêt pour l'implémentation** à ce stade.

---

*Document de travail — à faire évoluer après validation par l'équipe SkillUp et retour d'usage de la V1.*