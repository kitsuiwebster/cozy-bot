# Blue/Green Deployment avec drainage progressif (Bot Discord)

## Objectif
Assurer des déploiements **sans coupure audio** ni déconnexion des utilisateurs lors des mises à jour du bot Discord, même avec des sessions vocales longues.

---

## Problème initial
Lors d’un `git push main` :
- La pipeline CI/CD redéploie le container
- Le bot est arrêté brutalement
- Toutes les sessions vocales en cours sont coupées

Ce comportement n’est pas acceptable en production.

---

## Principe général
On utilise un **Blue/Green deployment** avec **drainage progressif** :

- **BLUE** : ancienne version (en production)
- **GREEN** : nouvelle version (en préparation puis production)

À **aucun moment**, les utilisateurs déjà connectés ne sont déplacés ou déconnectés.

---

## Règles fondamentales
1. **Un seul bot Discord logique** (une seule application, un seul token)
2. **Deux instances techniques** (containers / process)
3. **Une seule instance connectée à Discord à un instant T**
4. Les utilisateurs terminent leur session sur l’instance qui les a pris en charge

---

## États possibles d’une instance
Chaque instance possède une variable d’environnement :

```env
BOT_MODE=active | standby | drain
```

### Signification
- **active** :
  - Se connecte à Discord (`client.login()`)
  - Accepte les nouveaux utilisateurs

- **standby** :
  - Ne se connecte PAS à Discord
  - N’accepte aucun utilisateur
  - Process vivant uniquement

- **drain** :
  - Ne prend plus de nouveaux utilisateurs
  - Continue les sessions existantes
  - S’éteint une fois à 0 session

---

## Déroulement d’un déploiement

### 1. Production initiale
- BLUE = active
- GREEN = arrêté
- Tous les utilisateurs sont sur BLUE

### 2. Déploiement de la nouvelle version
- GREEN démarre avec la nouvelle image
- GREEN est en `standby`
- BLUE continue normalement
- Aucun utilisateur impacté

### 3. Drainage progressif (switch)
- GREEN passe en `active`
- BLUE passe en `drain`

Effets :
- Les **anciens utilisateurs restent sur BLUE**
- Les **nouveaux utilisateurs vont sur GREEN**
- Aucune reconnexion, aucune coupure audio

### 4. Finalisation
- BLUE atteint 0 utilisateur
- BLUE est arrêté
- GREEN est la seule instance en production

---

## Gestion du SIGTERM (obligatoire)
Toute instance doit gérer un arrêt propre :

- Passage automatique en mode `drain`
- Refus des nouvelles sessions
- Attente de la fin des sessions actives

Le timeout maximal est configurable (ex : 30–60 secondes).

---

## Ce qui NE se passe PAS
- Pas de migration de session
- Pas de reconnexion Discord
- Pas de double audio
- Pas de coupure vocale

---

## Avantages
- Zéro downtime utilisateur
- Déploiements possibles à tout moment
- Compatible Docker / GitHub Actions
- Évolutif (peut aller vers Kubernetes plus tard)

---

## Résumé
- 1 bot Discord
- 2 instances techniques
- 1 seule connectée à Discord
- Drainage progressif des utilisateurs

**Résultat : déploiement totalement transparent pour les utilisateurs.**
