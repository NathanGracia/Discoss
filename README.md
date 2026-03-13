# Discoss

Bot Discord de musique avec interface web de télécommande.

## Fonctionnalités

- Lecture YouTube (vidéos, playlists, recherche)
- File d'attente avec boucle, volume, skip, pause/resume
- Interface web temps réel via WebSocket (aiohttp)
- Drag & drop pour réordonner la file
- Ajout de musique depuis l'interface web

## Installation

```bash
pip install -r requirements.txt
```

FFmpeg doit être installé et disponible dans le PATH.

## Configuration

Copier `.env.example` en `.env` et remplir :

```env
DISCORD_TOKEN=...
WEB_PASSWORD=ton_mot_de_passe
WEB_PORT=3000
```

## Lancement

```bash
python bot.py
```

Le bot démarre et affiche :
```
Web interface running on http://0.0.0.0:3000
Bot ready: Discoss#xxxx
```

## Commandes Discord

| Commande | Description |
|---|---|
| `/play <query>` | Lecture d'une URL ou recherche YouTube |
| `/skip` | Passer la chanson courante |
| `/pause` / `/resume` | Pause / reprendre |
| `/stop` | Arrêter et déconnecter |
| `/queue` | Afficher la file |
| `/nowplaying` | Chanson en cours |
| `/volume <0-100>` | Régler le volume |
| `/loop` | Activer/désactiver la boucle |
| `/clear` | Vider la file |

## Interface web

Accessible sur `http://localhost:3000`. Protégée par mot de passe (`WEB_PASSWORD`).

- Panneau gauche : chanson en cours, barre de progression, contrôles
- Panneau droit : ajout de chanson, file avec drag & drop

## Structure

```
discoss/
├── bot.py              # Point d'entrée
├── cogs/
│   └── music.py        # Cog Discord (commandes + lecteur)
├── web/
│   ├── server.py       # Serveur aiohttp + WebSocket
│   └── index.html      # Interface web (vanilla JS)
├── cookies.txt         # Cookies YouTube (optionnel)
├── .env
└── requirements.txt
```
