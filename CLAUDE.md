# Discoss — contexte pour Claude

## Architecture

- `bot.py` : point d'entrée, instancie le bot Discord et le `WebServer`, connecte `broadcast_cb`
- `cogs/music.py` : toute la logique musicale — `Song`, `GuildPlayer`, `MusicCog`
- `web/server.py` : serveur aiohttp, WebSocket, dispatch des actions web
- `web/index.html` : interface web single-file (vanilla JS, pas de build)

## Points clés

### play_next
Signature : `play_next(guild, channel)` — ne prend PAS d'`Interaction`.
Le web server l'appelle directement avec un objet `guild` Discord.

### broadcast_cb
`MusicCog.broadcast_cb` est une coroutine async assignée par `bot.py` après démarrage du serveur.
`_broadcast()` est thread-safe : utilise `create_task` depuis un contexte async, `run_coroutine_threadsafe` depuis le callback `after()` de discord.py (thread séparé).

### GuildPlayer.elapsed
Propriété calculée. `on_pause()` / `on_resume()` ajustent `started_at` pour que `time.time() - started_at` reste correct même après des pauses.

### Auth WebSocket
Premier message obligatoirement `{action:"auth", password:"..."}`. Connexion fermée si mauvais mot de passe. Toutes les connexions authentifiées sont dans `WebServer.authed_ws`.

## Conventions

- Pas de base de données — tout est en mémoire, état perdu au redémarrage
- Un seul serveur Discord actif à la fois (web server cible le premier guild avec un voice client)
- `cookies.txt` à la racine pour contourner les restrictions YouTube (optionnel)
- Python 3.11+

## Variables d'environnement

| Variable | Description |
|---|---|
| `DISCORD_TOKEN` | Token du bot Discord |
| `WEB_PASSWORD` | Mot de passe de l'interface web |
| `WEB_PORT` | Port HTTP (défaut : 3000) |

## Commandes utiles

```bash
python bot.py          # lancer le bot
python -m pip install -r requirements.txt
```
