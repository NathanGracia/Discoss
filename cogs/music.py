import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp
import asyncio
import time
import os
from collections import deque

_cookies_file = os.path.join(os.path.dirname(__file__), "..", "cookies.txt")
_cookies_file = os.path.normpath(_cookies_file) if os.path.exists(_cookies_file) else None

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": False,
    "extract_flat": "in_playlist",
    "extractor_args": {"youtube": {"player_client": ["android"]}},
    **({"cookiefile": _cookies_file} if _cookies_file else {}),
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -ar 48000 -ac 2",
}


class Song:
    def __init__(self, url: str, title: str, duration: int, webpage_url: str):
        self.url = url          # stream URL
        self.title = title
        self.duration = duration
        self.webpage_url = webpage_url

    @classmethod
    async def from_url(cls, query: str, loop: asyncio.AbstractEventLoop, limit: int = 100) -> list["Song"]:
        """Resolve a YouTube URL or search query into a list of Song objects."""
        opts = {**YTDL_OPTIONS, "noplaylist": False, "playlistend": limit}

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(query, download=False)
                if "entries" in info:
                    return info["entries"]
                return [info]

        entries = await loop.run_in_executor(None, _extract)
        songs = []
        for entry in entries:
            if entry is None:
                continue
            # For flat playlist entries, we only have the ID — stream URL resolved later
            songs.append(cls(
                url=entry.get("url") or f"https://www.youtube.com/watch?v={entry['id']}",
                title=entry.get("title", "Unknown"),
                duration=entry.get("duration", 0),
                webpage_url=entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry['id']}",
            ))
        return songs

    @classmethod
    async def resolve_stream(cls, song: "Song", loop: asyncio.AbstractEventLoop) -> str:
        """Get the actual stream URL for a song (needed for flat playlist entries)."""
        opts = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extractor_args": {"youtube": {"player_client": ["android"]}},
        }

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(song.webpage_url, download=False)
                return info.get("url")

        return await loop.run_in_executor(None, _extract)

    def format_duration(self) -> str:
        if not self.duration:
            return "??:??"
        m, s = divmod(int(self.duration), 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"


class GuildPlayer:
    def __init__(self):
        self.queue: deque[Song] = deque()
        self.current: Song | None = None
        self.loop: bool = False
        self.volume: float = 0.5
        self.started_at: float | None = None
        self._pause_start: float | None = None

    @property
    def elapsed(self) -> float:
        if self.started_at is None:
            return 0.0
        if self._pause_start is not None:
            return self._pause_start - self.started_at
        return time.time() - self.started_at

    def on_pause(self):
        if self.started_at is not None and self._pause_start is None:
            self._pause_start = time.time()

    def on_resume(self):
        if self._pause_start is not None:
            self.started_at += time.time() - self._pause_start
            self._pause_start = None


class MusicCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}
        self.broadcast_cb = None  # set by web server after init

    def get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer()
        return self.players[guild_id]

    def _broadcast(self):
        """Fire-and-forget broadcast to web clients."""
        if not self.broadcast_cb:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast_cb())
        except RuntimeError:
            asyncio.run_coroutine_threadsafe(self.broadcast_cb(), self.bot.loop)

    async def play_next(self, guild: discord.Guild, channel: discord.abc.Messageable):
        player = self.get_player(guild.id)
        vc = guild.voice_client

        if not vc:
            return

        if player.loop and player.current:
            player.queue.appendleft(player.current)

        if not player.queue:
            player.current = None
            player.started_at = None
            player._pause_start = None
            self._broadcast()
            await asyncio.sleep(180)
            if not player.queue and vc.is_connected():
                await vc.disconnect()
            return

        song = player.queue.popleft()
        player.current = song

        # Resolve actual stream URL if needed
        stream_url = song.url
        if "youtube.com/watch" in song.url or "youtu.be" in song.url:
            try:
                stream_url = await Song.resolve_stream(song, self.bot.loop)
            except Exception:
                pass

        source = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
        source = discord.PCMVolumeTransformer(source, volume=player.volume)

        player.started_at = time.time()
        player._pause_start = None
        self._broadcast()

        def after(error):
            if error:
                print(f"Player error: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(guild, channel), self.bot.loop)

        vc.play(source, after=after)

    def _now_playing_embed(self, song: Song, queue_size: int) -> discord.Embed:
        embed = discord.Embed(
            title="Now playing",
            description=f"[{song.title}]({song.webpage_url})",
            color=discord.Color.blurple(),
        )
        embed.add_field(name="Duration", value=song.format_duration())
        embed.add_field(name="In queue", value=str(queue_size))
        return embed

    # ── /play ────────────────────────────────────────────────────────────────

    @app_commands.command(name="play", description="Play a YouTube video, playlist, or search query")
    @app_commands.describe(
        query="YouTube URL, playlist URL, or search terms",
        limit="Max songs to load from a playlist (default 100, max 500)",
    )
    async def play(self, interaction: discord.Interaction, query: str, limit: int = 100):
        await interaction.response.defer(ephemeral=True)

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel.", ephemeral=True)
            return

        limit = max(1, min(limit, 500))

        vc = interaction.guild.voice_client
        if vc is None:
            vc = await interaction.user.voice.channel.connect()
        elif vc.channel != interaction.user.voice.channel:
            await vc.move_to(interaction.user.voice.channel)

        player = self.get_player(interaction.guild_id)

        try:
            songs = await Song.from_url(query, self.bot.loop, limit=limit)
        except Exception as e:
            await interaction.followup.send(f"Error fetching audio: {e}", ephemeral=True)
            return

        for song in songs:
            player.queue.append(song)

        if len(songs) == 1:
            msg = f"Added to queue: **{songs[0].title}**"
        else:
            msg = f"Added **{len(songs)}** songs to queue."

        await interaction.followup.send(msg, ephemeral=True)
        self._broadcast()

        if not vc.is_playing() and not vc.is_paused():
            await self.play_next(interaction.guild, interaction.channel)

    # ── /skip ────────────────────────────────────────────────────────────────

    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        vc.stop()
        self._broadcast()
        await interaction.response.send_message("Skipped.", ephemeral=True)

    # ── /pause / /resume ─────────────────────────────────────────────────────

    @app_commands.command(name="pause", description="Pause playback")
    async def pause(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_playing():
            player = self.get_player(interaction.guild_id)
            player.on_pause()
            vc.pause()
            self._broadcast()
            await interaction.response.send_message("Paused.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback")
    async def resume(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc and vc.is_paused():
            player = self.get_player(interaction.guild_id)
            player.on_resume()
            vc.resume()
            self._broadcast()
            await interaction.response.send_message("Resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Not paused.", ephemeral=True)

    # ── /stop ────────────────────────────────────────────────────────────────

    @app_commands.command(name="stop", description="Stop playback and disconnect")
    async def stop(self, interaction: discord.Interaction):
        vc = interaction.guild.voice_client
        if vc:
            player = self.get_player(interaction.guild_id)
            player.queue.clear()
            player.current = None
            player.started_at = None
            player._pause_start = None
            await vc.disconnect()
            self._broadcast()
            await interaction.response.send_message("Stopped and disconnected.", ephemeral=True)
        else:
            await interaction.response.send_message("Not connected.", ephemeral=True)

    # ── /queue ───────────────────────────────────────────────────────────────

    @app_commands.command(name="queue", description="Show the current queue")
    async def queue(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild_id)

        embed = discord.Embed(title="Queue", color=discord.Color.blurple())

        if player.current:
            embed.add_field(
                name="Now playing",
                value=f"[{player.current.title}]({player.current.webpage_url}) `{player.current.format_duration()}`",
                inline=False,
            )

        if player.queue:
            lines = []
            for i, song in enumerate(list(player.queue)[:15], 1):
                lines.append(f"`{i}.` [{song.title}]({song.webpage_url}) `{song.format_duration()}`")
            if len(player.queue) > 15:
                lines.append(f"... and {len(player.queue) - 15} more")
            embed.add_field(name="Up next", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Up next", value="Queue is empty.", inline=False)

        embed.set_footer(text=f"Loop: {'on' if player.loop else 'off'} | Volume: {int(player.volume * 100)}%")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /nowplaying ──────────────────────────────────────────────────────────

    @app_commands.command(name="nowplaying", description="Show the current song")
    async def nowplaying(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild_id)
        if not player.current:
            await interaction.response.send_message("Nothing is playing.", ephemeral=True)
            return
        embed = self._now_playing_embed(player.current, len(player.queue))
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /volume ──────────────────────────────────────────────────────────────

    @app_commands.command(name="volume", description="Set volume (0–100)")
    @app_commands.describe(level="Volume level between 0 and 100")
    async def volume(self, interaction: discord.Interaction, level: int):
        if not 0 <= level <= 100:
            await interaction.response.send_message("Volume must be between 0 and 100.", ephemeral=True)
            return
        player = self.get_player(interaction.guild_id)
        player.volume = level / 100
        vc = interaction.guild.voice_client
        if vc and vc.source:
            vc.source.volume = player.volume
        self._broadcast()
        await interaction.response.send_message(f"Volume set to {level}%.", ephemeral=True)

    # ── /loop ────────────────────────────────────────────────────────────────

    @app_commands.command(name="loop", description="Toggle queue loop")
    async def loop_cmd(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild_id)
        player.loop = not player.loop
        self._broadcast()
        await interaction.response.send_message(f"Loop {'enabled' if player.loop else 'disabled'}.", ephemeral=True)

    # ── /clear ───────────────────────────────────────────────────────────────

    @app_commands.command(name="clear", description="Clear the queue")
    async def clear(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild_id)
        player.queue.clear()
        self._broadcast()
        await interaction.response.send_message("Queue cleared.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
