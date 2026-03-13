# Discoss

Bot Discord de musique avec interface web de télécommande.

## Architecture

```
Ton PC (IP résidentielle)
├── python bot.py          → se connecte à Discord + joue YouTube
└── aiohttp :3000          → dashboard web local
        │
        └── cloudflared tunnel
                │
                └── discoss.nathangracia.com   (accessible publiquement)
```

Le bot tourne **en local** pour garder une IP résidentielle — indispensable pour que YouTube fonctionne. Le dashboard est exposé via **Cloudflare Tunnel** (gratuit, sans port forwarding ni VPS).

## Prérequis

- Python 3.11+
- [FFmpeg](https://ffmpeg.org/download.html) dans le PATH
- [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) pour exposer le dashboard

## Installation

```bash
git clone https://github.com/NathanGracia/Discoss.git
cd Discoss
pip install -r requirements.txt
cp .env.example .env   # puis remplir les variables
```

## Configuration `.env`

```env
DISCORD_TOKEN=...
WEB_PASSWORD=ton_mot_de_passe
WEB_PORT=3000
```

## Lancement

**Windows :**
```
start.bat
```

**Manuel :**
```bash
python bot.py
```

Le bot affiche :
```
Web interface running on http://0.0.0.0:3000
Bot ready: Discoss#xxxx
```

## Cloudflare Tunnel (exposition publique)

1. Installer `cloudflared` et se connecter :
```bash
cloudflared tunnel login
cloudflared tunnel create discoss
```

2. Créer `~/.cloudflared/config.yml` :
```yaml
tunnel: <ton-tunnel-id>
credentials-file: /Users/<user>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: discoss.nathangracia.com
    service: http://localhost:3000
  - service: http_status:404
```

3. Ajouter le CNAME dans Cloudflare DNS :
```
discoss.nathangracia.com → <tunnel-id>.cfargotunnel.com
```

4. Lancer le tunnel (dans un terminal séparé) :
```bash
cloudflared tunnel run discoss
```

Ou en service Windows (démarre automatiquement au boot) :
```bash
cloudflared service install
```

## Commandes Discord

| Commande | Description |
|---|---|
| `/play <query>` | URL ou recherche YouTube |
| `/skip` | Passer la chanson |
| `/pause` / `/resume` | Pause / reprendre |
| `/stop` | Arrêter et déconnecter |
| `/queue` | Afficher la file |
| `/nowplaying` | Chanson en cours |
| `/volume <0-100>` | Régler le volume |
| `/loop` | Activer/désactiver la boucle |
| `/clear` | Vider la file |

## Interface web

- **Accueil** : `http://localhost:3000` (ou `discoss.nathangracia.com`)
- **Dashboard** : `/dashboard` — protégé par `WEB_PASSWORD`
- Sélecteur de serveur si le bot est sur plusieurs serveurs
- Contrôles : pause, skip, stop, loop, volume, file d'attente drag & drop

## Structure

```
Discoss/
├── bot.py              # Point d'entrée
├── cogs/
│   └── music.py        # Commandes Discord + lecteur audio
├── web/
│   ├── server.py       # Serveur aiohttp + WebSocket
│   ├── home.html       # Page d'accueil
│   └── dashboard.html  # Interface de contrôle
├── catjam.gif          # Logo
├── cookies.txt         # Cookies YouTube (optionnel, améliore la fiabilité)
├── start.bat           # Lancement Windows
└── .env
```
