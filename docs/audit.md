# Audit fonctionnel CozyBot — Synthèse

5 explorations parallèles ont couvert : audio, stats/gamification, APIs, frontends, infra. Vérifié par échantillonnage (URL frontend identique prod/dev, noms conteneurs hardcodés dans compose — tout est confirmé).

## Critiques (à corriger en priorité)

### Données & persistance
- **Race conditions CouchDB** — `utils/storage/couchdb_client.py:88-110` lit `_rev` puis écrit sans retry sur conflit. Writes concurrentes (bot + API publique + Live API) peuvent se perdre silencieusement. C'est probablement la cause n°1 des « incohérences » que tu observes.
- **Perte de temps d'écoute au crash** — `main.py:196-227`. `guild_voice_time[guild_id][0]` (start_time) n'est jamais rafraîchi en base pendant la session. Crash = tout ce qui est après la dernière sauvegarde périodique (jusqu'à 10 min) est perdu.
- **Double-comptage de points** — `finalize_current_sound()` + `periodic_backup` peuvent tourner en chevauchement sans lock (`gamification.py:444-480` vs `main.py:390-411`). Résultat : mêmes secondes créditées 2 fois, streak bonus appliqué deux fois.
- **Cap 30 min silencieux** — `main.py:299-303` et `gamification.py:394-397`. Un utilisateur qui écoute 2 h voit seulement 30 min comptées. Pas de warning cohérent → stats qui « gèlent » inexplicablement pour tes gros listeners.

### Infra / déploiement
- **Dépendances hardcodées dans `docker-compose.yml:138-140`** — `cozy-public-api`, `cozy-live-bot`, `cozy-couchdb` en dur alors que `CONTAINER_NAME` / `API_CONTAINER_NAME` sont paramétrables ailleurs. Si on touche un de ces noms, status-api part en healthcheck failure en cascade.
- **`depends_on: service_started`** (compose:147) pour uptime-kuma au lieu de `service_healthy` → status-api peut démarrer contre un Kuma non prêt.
- **`DEV_CODE_MOUNT` dangereux** — compose:42. Si la var pointe vers un dossier host en prod, elle écrase `/app` incluant les deps Python. Guard-rail absent.

### Frontend
- **`environment.ts == environment.prod.ts`** — les deux pointent vers `https://api.cozybot.online/api/public`. Impossible de dev localement sans éditer les sources (risque de commit accidentel).
- **Fuites RxJS** — `web/src/app/pages/cozybot/cozybot.component.ts:325-565`. Trois `interval()` + `.subscribe()` sans `takeUntil` ni async pipe. Après ~30 min d'onglet ouvert : CPU qui monte, freezes.

## Majeurs

### Bot
- **Type incohérent `member.id`** — `base_sound.py:136, 446` passe tantôt `int`, tantôt `str`. Le tracking côté gamification (qui utilise `str(id)` comme clé) rate une partie des sessions.
- **Duplication d'état audio en 3 endroits** — `guild_states['current_sound']`, `global_playing_states`, `global_current_sounds`. Aucune sync → désync quasi systématique après reconnexion.
- **Watchdog de lecture sans verrou global** — `main.py:577-626` peut lancer `restart_audio_loop` pendant qu'un `stop_sound` s'exécute dans un autre cog.
- **Achievement "category completion" jamais déclenché** — `gamification.py:737-782` compare des noms de fichiers bruts (`rain00.mp3`) contre des clés normalisées par `normalize_sound_name()`. Le match échoue toujours.
- **Usernames jamais rafraîchis** — `update_username` n'a pas de logique de détection de changement. Les profils/leaderboards affichent des anciens noms.

### API
- **Endpoints `audio/save-state` et `audio/restore-state` dupliqués** entre `live_api/app.py` et `api/routes/audio_restore.py` avec deux instances globales `bot_instance` différentes → risque de désync.
- **500 pour tout** — admin.py, stats.py, top_users.py. User introuvable renvoie 500 au lieu de 404. Input invalide → 500 au lieu de 422. Frontend ne peut pas réagir proprement.
- **Stacktrace dans la réponse HTTP** — `admin.py:186` (et similaires) : `detail=f"Error modifying points: {str(e)}"`. Fuite d'info interne.
- **Pas de validation Pydantic** sur `points`, `seconds` dans `PointsRequest`/`TimeRequest` → accepte `-2147483648`.
- **`/api/public/admin/debug/all-data`** dump complet des utilisateurs, non paginé, non throttlé.
- **CORS avec IP publique en dur** — `api/app.py:70-83` contient `http://90.60.191.159:8000`.

### Infra
- **Password/token sans defaults** — `COUCHDB_PASSWORD`, `DISCORD_BOT_TOKEN` sans validation de présence au boot → CouchDB démarre en rejetant toutes les requêtes sans erreur explicite côté bot.
- **`deploy.sh` avale les erreurs** — pipelines `... | grep | grep` + `PIPESTATUS[0]`, et `stop 2>/dev/null || true`. Un déploiement peut « réussir » en silence malgré un build cassé.
- **`migrate_to_couchdb.py`** catch HTTP 409 sans merge → relancer la migration laisse des docs partiels.

## Mineurs

- **Timezone/DST** — `datetime.now()` partout, streaks comparés via strings `%Y-%m-%d`. Cas limite autour de minuit + DST = incréments manqués ou doublés.
- **Pas de GC** — users/guilds supprimés côté Discord restent indéfiniment en CouchDB.
- **Healthchecks laxistes** — CouchDB `/_up` renvoie 200 même si la DB refuse les writes (perms). Root `/health` des APIs renvoie toujours 200 sans vérifier `bot.is_ready()`.
- **Route wildcard Angular** — redirige vers `/cozybot` au lieu de 404 → liens brisés invisibles.
- **Polling status-page sans timeout** — `setInterval(updateStatus, 10000)` sans abort du fetch précédent → requêtes qui s'empilent quand le réseau ralentit.
- **Nettoyage 12h** — `clean_corrupted_data()` n'est appelé qu'au startup. Downtime > 12h = sessions à finaliser silencieusement jetées.

## Ordre recommandé

Si tu veux attaquer, les trois leviers qui réduiront le plus les « incohérences » observées :
1. **Ajouter retry + merge sur les writes CouchDB** (couchdb_client) — supprime la classe n°1 de perte de données.
2. **Unifier l'état audio** (un seul dict par guild, ou un manager) + un lock par guild autour de start/stop/restart — supprime le double-comptage de points et l'audio dupliqué.
3. **Normaliser les types `user_id` en `str` partout** à l'entrée publique, une fois — supprime les sessions qui s'évaporent.
