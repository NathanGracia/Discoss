# Discoss

Bot Discord de musique avec interface web de télécommande. Joue YouTube dans les salons vocaux Discord et se contrôle depuis un dashboard web accessible partout.

---

## Comment ça marche

### Vue d'ensemble

```
                        INTERNET
                            │
              ┌─────────────▼─────────────┐
              │   discoss.nathangracia.com  │  ← les utilisateurs
              │      (Cloudflare DNS)       │
              └─────────────┬─────────────┘
                            │ HTTPS chiffré
              ┌─────────────▼─────────────┐
              │     Cloudflare Tunnel      │  ← proxy gratuit,
              │       (cloudflared)        │    pas de VPS
              └─────────────┬─────────────┘
                            │ HTTP local
              ┌─────────────▼─────────────┐
              │         Ton PC             │
              │                           │
              │  ┌─────────────────────┐  │
              │  │    python bot.py    │  │
              │  │                     │  │
              │  │  ┌───────────────┐  │  │
              │  │  │  Discord Bot  │  │  │  → salons vocaux Discord
              │  │  │  (discord.py) │  │  │
              │  │  └───────────────┘  │  │
              │  │                     │  │
              │  │  ┌───────────────┐  │  │
              │  │  │  Web Server   │  │  │  → dashboard :3000
              │  │  │   (aiohttp)   │  │  │
              │  │  └───────────────┘  │  │
              │  └─────────────────────┘  │
              └───────────────────────────┘
```

### Pourquoi le bot tourne en local et pas sur un VPS ?

YouTube bloque activement les IP des datacenters (AWS, OVH, Hetzner…). Même avec des cookies valides, la lecture échoue sur un serveur cloud. En faisant tourner le bot sur ton PC, YouTube voit une **IP résidentielle** normale et laisse passer.

### Le flux de lecture

1. Tu lances `/play <url>` dans Discord
2. Le bot résout l'URL via **yt-dlp** (récupère le stream audio)
3. **FFmpeg** décode et transmet l'audio en temps réel dans le salon vocal
4. Le **serveur web** notifie le dashboard via **WebSocket** de chaque changement d'état

### Le dashboard web

Le dashboard communique avec le bot via une connexion **WebSocket persistante** (`/ws`). Quand tu appuies sur "Skip" :

```
Navigateur → WebSocket → aiohttp server → discord.py → Discord
                                    ↓
Navigateur ← WebSocket ← aiohttp server  (état mis à jour)
```

L'état est poussé par le bot à chaque événement (nouvelle chanson, pause, volume…), pas en polling. Le dashboard est donc toujours synchronisé en temps réel.

### Cloudflare Tunnel

Cloudflare Tunnel (`cloudflared`) crée un tunnel chiffré entre ton PC et les serveurs Cloudflare, sans ouvrir de port sur ta box. Cloudflare reçoit les requêtes HTTPS sur `discoss.nathangracia.com` et les fait suivre à ton `localhost:3000`.

```
Visiteur → cloudflare.com → tunnel chiffré → ton PC :3000
```

Avantages :
- Pas de port forwarding sur le routeur
- HTTPS automatique (certificat géré par Cloudflare)
- Pas de VPS à payer
- L'IP de ton PC n'est jamais exposée

---

## Installation

### 1. Prérequis

| Outil | Rôle | Lien |
|---|---|---|
| Python 3.11+ | Fait tourner le bot | [python.org](https://python.org) |
| FFmpeg | Encode l'audio pour Discord | [ffmpeg.org](https://ffmpeg.org/download.html) |
| cloudflared | Expose le dashboard publiquement | [Cloudflare Docs](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) |

Vérifier que tout est installé :
```bash
python --version    # Python 3.11+
ffmpeg -version     # ffmpeg version ...
cloudflared --version
```

### 2. Cloner le projet

```bash
git clone https://github.com/NathanGracia/Discoss.git
cd Discoss
pip install -r requirements.txt
```

### 3. Créer le bot Discord

1. Aller sur [discord.com/developers/applications](https://discord.com/developers/applications)
2. **New Application** → donner un nom
3. Onglet **Bot** → **Reset Token** → copier le token
4. Onglet **Bot** → activer **Message Content Intent** (optionnel) et **Server Members Intent**
5. Onglet **OAuth2** → URL Generator → scopes : `bot` + `applications.commands` → permissions : `Connect`, `Speak`, `Send Messages`, `Embed Links`
6. Ouvrir l'URL générée pour inviter le bot sur ton serveur

### 4. Configurer `.env`

```bash
cp .env.example .env
```

Ouvrir `.env` et remplir :

```env
DISCORD_TOKEN=ton_token_discord
WEB_PASSWORD=un_mot_de_passe_solide
WEB_PORT=3000
```

### 5. Lancer le bot

**Windows :**
```
start.bat
```

**Linux / Mac :**
```bash
python bot.py
```

Le bot doit afficher :
```
Web interface running on http://0.0.0.0:3000
Bot ready: Discoss#xxxx
```

---

## Exposition publique avec Cloudflare Tunnel

> Si tu veux accéder au dashboard depuis l'extérieur (téléphone, autre réseau…).
> Requiert un domaine géré par Cloudflare.

### 1. Connexion à Cloudflare

```bash
cloudflared tunnel login
```

Un navigateur s'ouvre, sélectionner le domaine à utiliser.

### 2. Créer le tunnel

```bash
cloudflared tunnel create discoss
```

Note le **tunnel ID** affiché (format UUID : `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`).

### 3. Créer la config

Créer le fichier `~/.cloudflared/config.yml` (Linux/Mac) ou `%USERPROFILE%\.cloudflared\config.yml` (Windows) :

```yaml
tunnel: <ton-tunnel-id>
credentials-file: /home/<user>/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: discoss.nathangracia.com
    service: http://localhost:3000
  - service: http_status:404
```

### 4. Ajouter le DNS

```bash
cloudflared tunnel route dns discoss discoss.nathangracia.com
```

Ou manuellement dans Cloudflare DNS : ajouter un enregistrement CNAME :
```
discoss → <tunnel-id>.cfargotunnel.com
```

### 5. Lancer le tunnel

```bash
cloudflared tunnel run discoss
```

Le dashboard est maintenant accessible sur `https://discoss.nathangracia.com`.

### 6. Lancer automatiquement au démarrage (optionnel)

**Windows :**
```bash
cloudflared service install
```

**Linux (systemd) :**
```bash
cloudflared service install
systemctl start cloudflared
systemctl enable cloudflared
```

---

## Utilisation

### Commandes Discord

| Commande | Description |
|---|---|
| `/play <query>` | Joue une URL YouTube, une playlist ou une recherche |
| `/skip` | Passer la chanson en cours |
| `/pause` | Mettre en pause |
| `/resume` | Reprendre la lecture |
| `/stop` | Arrêter et déconnecter le bot du salon |
| `/queue` | Afficher la file d'attente |
| `/nowplaying` | Afficher la chanson en cours |
| `/volume <0-100>` | Régler le volume |
| `/loop` | Activer / désactiver la boucle de la file |
| `/clear` | Vider la file d'attente |

### Dashboard web

Accessible sur `http://localhost:3000` (ou ton domaine Cloudflare).

- **Page d'accueil** — lien d'invitation du bot + accès au dashboard
- **Dashboard** (`/dashboard`) — protégé par le mot de passe `WEB_PASSWORD`
  - Sélecteur de serveur si le bot est sur plusieurs serveurs
  - Chanson en cours avec barre de progression en temps réel
  - Contrôles : pause, skip, stop, loop, volume
  - File d'attente : drag & drop pour réordonner, bouton supprimer par chanson
  - Ajout de chanson par URL ou recherche

---

## Cookies YouTube (optionnel)

Si YouTube refuse certaines vidéos (contenu avec âge, restrictions régionales…), exporter ses cookies depuis un navigateur connecté à YouTube et les placer dans `cookies.txt` à la racine du projet.

Extension recommandée : **Get cookies.txt LOCALLY** (Chrome/Firefox).

---

## Structure du projet

```
Discoss/
├── bot.py              # Point d'entrée — initialise le bot et le serveur web
├── cogs/
│   └── music.py        # Toute la logique musicale (commandes + lecteur)
├── web/
│   ├── server.py       # Serveur aiohttp + gestion WebSocket
│   ├── home.html       # Page d'accueil publique
│   └── dashboard.html  # Interface de contrôle (auth requise)
├── catjam.gif          # Logo
├── cookies.txt         # Cookies YouTube (optionnel, ignoré par git)
├── start.bat           # Script de lancement Windows
├── Dockerfile          # Pour référence (non recommandé, voir architecture)
└── .env                # Variables d'environnement (ignoré par git)
```
