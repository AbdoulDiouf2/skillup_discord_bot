# Guide d'utilisation — Bot SkillUp

Petit guide pour les 8 membres de la vague. Toutes les commandes se tapent dans un salon texte du serveur.

Pour un résumé rapide sans lire tout ce document, tape `/aide` — le bot t'affiche l'essentiel en privé.

La plupart des réponses sont privées (visibles par toi seul). Exception : `/session-start` et `/session-end` postent publiquement dans le salon, comme avant le bot (ambiance collective du coworking) — les refus/erreurs restent privés.

## Le cycle d'une session

### 1. Rejoins un salon vocal de coworking

Avant de démarrer une session, connecte-toi à un salon vocal **Coworking** (le bot détecte automatiquement lequel). Si tu n'es pas en vocal, la commande de démarrage sera refusée.

### 2. Démarre ta session — `/session-start`

```
/session-start créneau:5h-7h objectif:Terminer le module 3 de la certif Databricks
```

- `créneau` : choisis dans la liste (`5h-7h`, `19h-21h`, `21h-23h`)
- `objectif` : ce que tu comptes faire pendant la session

Le bot confirme avec le salon détecté.

### 3. Clôture ta session en fin de créneau — `/session-end`

```
/session-end bilan:Module 3 terminé, quiz réussi blocages:Bloqué sur la partie SQL avancé
```

- `bilan` : ce que tu as réellement fait (obligatoire)
- `blocages` : difficultés rencontrées (optionnel)

⚠️ Tu ne peux avoir qu'**une seule session ouverte** à la fois. Si tu oublies de clôturer, le bot le fait automatiquement à minuit (statut « incomplète »).

Tu peux enchaîner plusieurs sessions dans la même journée (ex. 5h-7h puis 19h-21h) — juste clôture la précédente avant d'en démarrer une nouvelle.

## Consulter ton journal

### `/mon-journal`

Affiche toutes tes sessions de la semaine en cours (vague active) :
```
/mon-journal
```

Pour une semaine précédente, **sans préciser de vague**, le bot cherche ce numéro de semaine à travers **toutes** les vagues auxquelles tu as participé :
```
/mon-journal semaine:1
```

Pour cibler une vague précise (utile si tu as fait plusieurs vagues) :
```
/mon-journal vague:[choisis dans la liste] semaine:1
```

Chaque session affiche un numéro (`#12`) — utile pour `/session-corriger`.

### `/binome-journal` — la fonctionnalité clé pour les bilans croisés

À partir de la semaine 2, tu es en binôme avec un autre membre. Pour préparer **son** bilan, tu lis directement son journal (lecture seule) :
```
/binome-journal
```

Sans précision, ça regarde toujours la **vague active**. Si tu précises `semaine` sans préciser `vague` et que plusieurs vagues existent, le bot te demande de préciser laquelle (les binômes sont définis par vague + semaine, pas de recherche floue possible ici).

Si tu étais en solo cette semaine-là, le bot te le dit clairement — pas d'erreur, juste une info.

## Générer ton bilan hebdomadaire — `/bilan-semaine`

```
/bilan-semaine
```

Même logique que `/mon-journal` pour les paramètres `vague`/`semaine` optionnels.

Le bot génère un récap propre (nombre de sessions, temps total, blocages) — copie-le tel quel dans le forum `objectifs` pour ta réunion de bilan.

## Ton objectif de vague — `/objectif-vague`

À définir une fois en début de vague (modifiable à tout moment) :
```
/objectif-vague objectif:Obtenir la certification Databricks Data Engineer Associate
```

## Corriger une erreur de saisie — `/session-corriger`

Tapé le mauvais bilan ? Oublié un blocage ? Tape `/session-corriger`, le champ `id_session` te propose directement tes sessions récentes (pas besoin de retenir le numéro) :
```
/session-corriger id_session:[choisis dans la liste] champ:bilan valeur:Le vrai bilan cette fois
```

Pour supprimer une session saisie par erreur :
```
/session-corriger id_session:[...] champ:suppression
```

## Récap des commandes

| Commande | À quoi ça sert |
|---|---|
| `/session-start` | Démarrer une session (en vocal coworking) |
| `/session-end` | Clôturer ta session en cours |
| `/mon-journal` | Voir tes sessions de la semaine |
| `/binome-journal` | Voir le journal de ton binôme (lecture seule) |
| `/bilan-semaine` | Générer ton bilan hebdomadaire |
| `/objectif-vague` | Définir/modifier ton objectif global |
| `/session-corriger` | Corriger ou supprimer une session |
| `/aide` | Résumé rapide des commandes, en privé |
| `/guide` | Poste ce guide complet dans le salon |

## Questions fréquentes

**Le bot me dit « Rejoins un salon de coworking avant de démarrer ta session »**
Tu n'es pas connecté à un salon vocal reconnu comme coworking. Rejoins un des salons Coworking (pas le salon Live) avant de retaper la commande.

**Le bot me dit « Tu as déjà une session ouverte »**
Tu as oublié de clôturer une session précédente. Fais `/session-end` d'abord (ou attends la clôture automatique à minuit si tu ne te souviens plus du bilan).

**J'étais en solo cette semaine, `/binome-journal` ne trouve rien**
Normal — les binômes ne démarrent qu'à partir de la semaine 2. Le message du bot te le confirme.
