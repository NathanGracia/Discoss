import json
import asyncio
from collections import deque
from pathlib import Path

from aiohttp import web, WSMsgType

from cogs.music import Song


class WebServer:
    def __init__(self, music_cog, password: str, port: int = 3000):
        self.music_cog = music_cog
        self.password = password
        self.port = port
        self.app = web.Application()
        self.authed_ws: set[web.WebSocketResponse] = set()

    async def start(self):
        self.app.router.add_get("/", self._handle_home)
        self.app.router.add_get("/dashboard", self._handle_dashboard)
        self.app.router.add_get("/catjam.gif", self._handle_catjam)
        self.app.router.add_get("/ws", self._handle_ws)
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", self.port)
        await site.start()
        print(f"Web interface running on http://0.0.0.0:{self.port}")

    # ── State ─────────────────────────────────────────────────────────────────

    def _build_guild_state(self, guild, player, vc) -> dict:
        current_data = None
        if player and player.current:
            current_data = {
                "title": player.current.title,
                "duration": player.current.duration,
                "webpage_url": player.current.webpage_url,
                "elapsed": player.elapsed,
            }

        return {
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count,
            "current": current_data,
            "queue": [
                {
                    "title": s.title,
                    "duration": s.duration,
                    "webpage_url": s.webpage_url,
                }
                for s in list(player.queue if player else [])
            ],
            "is_playing": bool(vc and vc.is_playing()),
            "is_paused": bool(vc and vc.is_paused()),
            "volume": int(player.volume * 100) if player else 50,
            "loop": player.loop if player else False,
        }

    def _build_state(self) -> dict:
        guilds = []
        for g in self.music_cog.bot.guilds:
            player = self.music_cog.players.get(g.id)
            vc = g.voice_client
            guilds.append(self._build_guild_state(g, player, vc))
        return {"guilds": guilds}

    async def broadcast_state(self):
        if not self.authed_ws:
            return
        msg = json.dumps({"type": "state", "data": self._build_state()})
        dead = set()
        for ws in list(self.authed_ws):
            try:
                await ws.send_str(msg)
            except Exception:
                dead.add(ws)
        self.authed_ws -= dead

    # ── HTTP handlers ─────────────────────────────────────────────────────────

    async def _handle_catjam(self, request):
        return web.FileResponse(Path(__file__).parent.parent / "catjam.gif")

    async def _handle_home(self, request):
        return web.FileResponse(Path(__file__).parent / "home.html")

    async def _handle_dashboard(self, request):
        return web.FileResponse(Path(__file__).parent / "dashboard.html")

    async def _handle_ws(self, request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        authed = False

        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                except json.JSONDecodeError:
                    continue

                action = data.get("action")

                if not authed:
                    if action == "auth":
                        if data.get("password") == self.password:
                            authed = True
                            self.authed_ws.add(ws)
                            await ws.send_str(json.dumps({"type": "auth", "ok": True}))
                            await self.broadcast_state()
                        else:
                            await ws.send_str(json.dumps({"type": "auth", "ok": False}))
                            await ws.close()
                            break
                    continue

                await self._handle_action(ws, data)

            elif msg.type in (WSMsgType.ERROR, WSMsgType.CLOSE):
                break

        self.authed_ws.discard(ws)
        return ws

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _resolve_guild(self, data: dict):
        """Return (guild, player, vc) from guild_id in data, or first active guild."""
        guild_id = data.get("guild_id")
        if guild_id:
            guild = self.music_cog.bot.get_guild(int(guild_id))
            if guild:
                player = self.music_cog.get_player(guild.id)
                return guild, player, guild.voice_client
        # Fallback: first guild with a voice client
        for g in self.music_cog.bot.guilds:
            if g.voice_client:
                return g, self.music_cog.get_player(g.id), g.voice_client
        return None, None, None

    # ── Action dispatcher ─────────────────────────────────────────────────────

    async def _handle_action(self, ws, data: dict):
        action = data.get("action")
        guild, player, vc = self._resolve_guild(data)

        if action == "skip":
            if vc and vc.is_playing():
                vc.stop()

        elif action == "pause":
            if vc and vc.is_playing() and player:
                player.on_pause()
                vc.pause()
                await self.broadcast_state()

        elif action == "resume":
            if vc and vc.is_paused() and player:
                player.on_resume()
                vc.resume()
                await self.broadcast_state()

        elif action == "stop":
            if guild and vc and player:
                player.queue.clear()
                player.current = None
                player.started_at = None
                player._pause_start = None
                await vc.disconnect()
                await self.broadcast_state()

        elif action == "volume":
            if player:
                level = max(0, min(100, int(data.get("level", 50))))
                player.volume = level / 100
                if vc and vc.source:
                    vc.source.volume = player.volume
                await self.broadcast_state()

        elif action == "loop":
            if player:
                player.loop = not player.loop
                await self.broadcast_state()

        elif action == "reorder":
            if player:
                queue_list = list(player.queue)
                from_idx = int(data.get("from", 0))
                to_idx = int(data.get("to", 0))
                if 0 <= from_idx < len(queue_list) and 0 <= to_idx < len(queue_list):
                    song = queue_list.pop(from_idx)
                    queue_list.insert(to_idx, song)
                    player.queue = deque(queue_list)
                await self.broadcast_state()

        elif action == "remove":
            if player:
                queue_list = list(player.queue)
                idx = int(data.get("index", 0))
                if 0 <= idx < len(queue_list):
                    queue_list.pop(idx)
                    player.queue = deque(queue_list)
                await self.broadcast_state()

        elif action == "play":
            query = data.get("query", "").strip()
            if not query:
                return

            try:
                songs = await Song.from_url(query, self.music_cog.bot.loop)
            except Exception as e:
                await ws.send_str(json.dumps({"type": "error", "message": str(e)}))
                return

            if not guild:
                guilds = self.music_cog.bot.guilds
                if not guilds:
                    await ws.send_str(json.dumps({"type": "error", "message": "Bot not in any server."}))
                    return
                guild = guilds[0]
                player = self.music_cog.get_player(guild.id)
                vc = guild.voice_client

            for song in songs:
                player.queue.append(song)

            if vc and not vc.is_playing() and not vc.is_paused():
                channel = guild.system_channel or next(
                    (c for c in guild.text_channels if c.permissions_for(guild.me).send_messages),
                    None,
                )
                asyncio.ensure_future(self.music_cog.play_next(guild, channel))
            else:
                await self.broadcast_state()
