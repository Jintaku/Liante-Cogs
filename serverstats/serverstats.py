from datetime import date, datetime, timedelta
from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.config import Group
import asyncio
import discord

try:
    from redbot.core.commands import Cog
except ImportError:
    Cog = object


class ServerStats(Cog):
    """
    Simple message and voice statistics.
    """

    __author__ = "Liante#0216"
    __version__ = "0.0.1"

    def __init__(self, red_bot):
        self.config = Config.get_conf(self, 4712468135468476)
        self.bot: Red = red_bot

        default_global = {
            "last_update": str(date.today())
        }

        default_guild = {
            "text_day": [0, 0, 0],
            "text_month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "text_total": [0],
            "voice_day": [0, 0, 0],
            "voice_month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "voice_total": [0],
            "enabled": True
        }

        default_member = {
            "text_day": [0, 0, 0],
            "text_month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "text_total": [0],
            "voice_day": [0, 0, 0],
            "voice_month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "voice_total": [0]
        }

        default_channel = {
            "text_day": [0, 0, 0],
            "text_month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "text_total": [0],
            "voice_day": [0, 0, 0],
            "voice_month": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
            "voice_total": [0],
            "ignored": False
        }

        self.config.register_global(**default_global, force_registration=True)
        self.config.register_guild(**default_guild, force_registration=True)
        self.config.register_member(**default_member, force_registration=True)
        self.config.register_channel(**default_channel, force_registration=True)

        self.current_month = datetime.now().month - 1

        loop = self.bot.loop
        self.timer: asyncio.Task = loop.create_task(self.__db_register_loop())

    async def __db_register_loop(self):
        print(await self.config.last_update())
        print(date.today())
        if (await self.config.last_update()) != str(date.today()):
            await self.__db_register()
        while True:
            sleep_time = await self.get_seconds_until_midnight()
            hours = int(sleep_time / 3600)
            minutes = int((sleep_time % 3600) / 60)
            seconds = int((sleep_time % 3600) % 60)
            print("time until next registration: {}:{}:{}".format(hours, minutes, seconds))
            await asyncio.sleep(sleep_time)
            await self.__db_register()
            print("database registration completed")

    async def __db_register(self):
        """Register global data to the db"""
        month = datetime.now().month - 1
        is_new_month = month != self.current_month

        for guild in self.bot.guilds:
            await self.__register_guild(guild)
            await self.__register_channels(guild)
            await self.__register_members(guild)

        if is_new_month:
            self.current_month = month

        await self.config.last_update.set(str(date.today()))
        return

    async def __register_guild(self, guild: discord.Guild):
        guild_config = self.config.guild(guild)
        await self.__update_db_group(guild_config)
        return

    async def __register_channels(self, guild: discord.Guild):
        for channel in guild.channels:
            await self.__update_db_group(self.config.channel(channel))
        return

    async def __register_members(self, guild: discord.Guild):
        for member in guild.members:
            await self.__update_db_group(self.config.member(member))
        return

    async def __update_db_group(self, config_group: Group):
        text_value = (await config_group.text_day())[-1]
        voice_value = (await config_group.voice_day())[-1]

        # update daily
        async with config_group.text_day() as text_day, config_group.voice_day() as voice_day:
            text_day.append(0)
            del text_day[0]
            voice_day.append(0)
            del voice_day[0]

        # update monthly
        # TODO: prevent adding more after a year
        async with config_group.text_month() as text_month, config_group.voice_month() as voice_month:
            text_month[self.current_month] += text_value
            voice_month[self.current_month] += voice_value

        # update totals
        async with config_group.text_total() as text_total, config_group.voice_total() as voice_total:
            text_total[0] += text_value
            voice_total[0] += voice_value

    @staticmethod
    async def get_seconds_until_midnight():
        """Get time until midnight in seconds"""
        tomorrow = datetime.now() + timedelta(days=1)
        midnight = datetime(year=tomorrow.year, month=tomorrow.month, day=tomorrow.day,
                            hour=0, minute=0, second=0)
        return (midnight - datetime.now()).seconds

    async def on_message(self, message: discord.Message):
        author = message.author
        if author.bot:
            return

        guild = message.guild
        if not await self.config.guild(guild).enabled():
            return

        channel = message.channel
        if type(channel) is not discord.TextChannel or await self.config.channel(channel).ignored():
            return

        prefixes = await Config.get_core_conf().prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return

        async with self.config.guild(guild).text_day() as text_day:
            text_day[-1] += 1

        async with self.config.member(author).text_day() as text_day:
            text_day[-1] += 1

        async with self.config.channel(channel).text_day() as text_day:
            text_day[-1] += 1

    @checks.admin_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.group(aliases=["stats"])
    async def serverstats(self, ctx: Context):
        ...

    @serverstats.command(hidden=True)
    async def register_stats(self, ctx: Context):
        await self.__db_register()
        await ctx.send("database registered manually")

    @serverstats.group(hidden=True)
    async def autoregister(self, ctx: Context):
        ...

    @autoregister.command(name="stop")
    async def autoregister_stop(self, ctx: Context):
        self.timer.cancel()
        await ctx.send("timer stopped")

    @autoregister.command(name="start")
    async def autoregister_start(self, ctx: Context):
        self.timer: asyncio.Task = asyncio.create_task(self.__db_register())
        await ctx.send("timer started")

    @serverstats.group(name="guild")
    async def guild_stats(self, ctx: Context):
        ...

    @guild_stats.command(name="text_day")
    async def guild_text_day(self, ctx: Context):
        guild = ctx.guild
        message = "today's messages: {}".format((await self.config.guild(guild).text_day())[-1])
        await ctx.send(message)

    def __unload(self):
        self.timer.cancel()
