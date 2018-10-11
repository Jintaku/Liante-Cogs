from calendar import month_name
from datetime import date, datetime, timedelta
from discord import Guild, Member, TextChannel
from .log import LOG
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


# TODO: add documentation and docstrings
class ServerStats(Cog):
    """
    Simple message and voice statistics.
    """

    __author__ = "Liante#0216"
    __version__ = "0.0.2"

    def __init__(self, red_bot):
        self.config = Config.get_conf(self, 4712468135468476)
        self.bot: Red = red_bot

        day_list = []
        for i in range(0, 31):
            day_list.append(["", 0])
        month_list = [0] * 12
        # total is a single value represented by a list to be usable within "with" blocks
        total_list = [0]
        # for compatibility purposes

        default_global = {
            "last_update": str(date.today())
        }

        default_guild = {
            "text_day": day_list,
            "text_month": month_list,
            "text_total": total_list,
            "voice_day": day_list,
            "voice_month": month_list,
            "voice_total": total_list,
            "enabled": True
        }

        default_member = {
            "text_day": day_list,
            "text_month": month_list,
            "text_total": total_list,
            "voice_day": day_list,
            "voice_month": month_list,
            "voice_total": total_list
        }

        default_channel = {
            "text_day": day_list,
            "text_month": month_list,
            "text_total": total_list,
            "voice_day": day_list,
            "voice_month": month_list,
            "voice_total": total_list,
            "ignored": False
        }

        self.config.register_global(**default_global, force_registration=True)
        self.config.register_guild(**default_guild, force_registration=True)
        self.config.register_member(**default_member, force_registration=True)
        self.config.register_channel(**default_channel, force_registration=True)

        self.current_month = datetime.now().month - 1
        self.today = date.today()

        loop = self.bot.loop
        loop.create_task(self.__update_data_format())
        self.timer: asyncio.Task = loop.create_task(self.__db_register_loop())

    async def __update_data_format(self):
        """This should prevent compatibility issues and data loss when updating from an early version"""
        for guild in self.bot.guilds:
            sample = (await self.config.guild(guild).text_day())[0]
            if type(sample) is list:
                LOG.debug("No reformatting necessary for guild {}".format(guild.name))
                continue
            LOG.debug("Reformatting guild {}".format(guild.name))
            await self.__update_guild_format(guild)
            await self.__update_members_format(guild)
            await self.__update_channels_format(guild)

        LOG.debug("Data check complete")

    async def __update_guild_format(self, guild: Guild):
        guild_config = self.config.guild(guild)
        await self.__update_group_format(guild_config)
        return

    async def __update_members_format(self, guild: Guild):
        for channel in guild.channels:
            await self.__update_group_format(self.config.channel(channel))
        return

    async def __update_channels_format(self, guild: Guild):
        for member in guild.members:
            await self.__update_group_format(self.config.member(member))
        return

    async def __update_group_format(self, config_group: Group):
        text_day = await config_group.text_day()
        day_delta = timedelta(days=1)
        yesterday = self.today - day_delta
        day_before = yesterday - day_delta

        today_data = [str(self.today), text_day[2]]
        yesterday_data = [str(yesterday), text_day[1]]
        day_before_data = [str(day_before), text_day[0]]

        text_day = []
        for i in range(0, 31):
            text_day.append(["", 0])
        text_day[self.today.day - 1] = today_data
        text_day[yesterday.day - 1] = yesterday_data
        text_day[day_before.day - 1] = day_before_data
        await config_group.text_day.set(text_day)

    async def __db_register_loop(self):
        if (await self.config.last_update()) != str(self.today):
            await self.__db_register()
        while True:
            sleep_time = await self.get_seconds_until_midnight()
            hours = int(sleep_time / 3600)
            minutes = int((sleep_time % 3600) / 60)
            seconds = int((sleep_time % 3600) % 60)
            LOG.debug("Time until next registration: {:02}:{:02}:{:02}".format(hours, minutes, seconds))
            await asyncio.sleep(sleep_time)
            await self.__db_register()
            self.today = date.today()
            LOG.debug("Database registration completed")

    async def __db_register(self):
        """Register global data to the db"""
        month = datetime.now().month - 1
        is_new_month = month != self.current_month

        LOG.debug("Starting database registration")
        for guild in self.bot.guilds:
            await self.__register_guild(guild)
            await self.__register_channels(guild)
            await self.__register_members(guild)

        if is_new_month:
            self.current_month = month

        await self.config.last_update.set(str(self.today))
        return

    async def __register_guild(self, guild: Guild):
        guild_config = self.config.guild(guild)
        await self.__update_db_group(guild_config)
        return

    async def __register_channels(self, guild: Guild):
        for channel in guild.channels:
            await self.__update_db_group(self.config.channel(channel))
        return

    async def __register_members(self, guild: Guild):
        for member in guild.members:
            await self.__update_db_group(self.config.member(member))
        return

    async def __update_db_group(self, config_group: Group):
        text_value = (await config_group.text_day())[self.today.day - 1][1]
        voice_value = (await config_group.voice_day())[self.today.day - 1][1]

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
        if type(channel) is not TextChannel or await self.config.channel(channel).ignored():
            return

        prefixes = await Config.get_core_conf().prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return

        await self.__update_text_daily(self.config.guild(guild))
        await self.__update_text_daily(self.config.member(author))
        await self.__update_text_daily(self.config.channel(channel))

    async def __update_text_daily(self, group: Group):
        today_index = self.today.day - 1
        async with group.text_day() as text_day:
            text_day[today_index][0] = str(self.today)
            text_day[today_index][1] += 1

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

    @guild_stats.command(name="total")
    async def guild_total(self, ctx: Context):
        guild_group = self.config.guild(ctx.guild)
        data = await self.__get_text_total(guild_group)
        day = await self.__get_text_day(guild_group, 0)

        if len(day) == 2:
            data += day[1]
        return await ctx.send("Total message count for {0.name}: {1}".format(ctx.guild, data))

    @guild_stats.command(name="month")
    async def guild_month(self, ctx: Context, months_ago: int=0):
        guild_group = self.config.guild(ctx.guild)
        data = await self.__get_text_month(guild_group, months_ago)
        day = await self.__get_text_day(guild_group, 0)

        if len(data) == 1:
            message = data[0]
        else:
            if len(day) == 2:
                data[1] += day[1]
            message = "Message count for {0.name} on {1[0]}: {1[1]}".format(ctx.guild, data)

        return await ctx.send(message)

    @guild_stats.command(name="day")
    async def guild_day(self, ctx: Context, days_ago: int=0):
        guild_group = self.config.guild(ctx.guild)
        data = await self.__get_text_day(guild_group, days_ago)

        if len(data) == 1:
            message = data[0]
        else:
            message = "Message count for {0.name} on {1[0]}: {1[1]}".format(ctx.guild, data)

        return await ctx.send(message)

    @serverstats.group(name="channel")
    async def channel_stats(self, ctx: Context):
        ...

    @channel_stats.command(name="total")
    async def channel_total(self, ctx: Context, channel: TextChannel):
        channel_group = self.config.channel(channel)
        data = await self.__get_text_total(channel_group)
        day = await self.__get_text_day(channel_group, 0)

        if len(day) == 2:
            data += day[1]
        return await ctx.send("Total message count for {0.name}: {1}".format(channel, data))

    @channel_stats.command(name="month")
    async def channel_month(self, ctx: Context, channel: TextChannel, months_ago: int=0):
        channel_group = self.config.channel(channel)
        data = await self.__get_text_month(channel_group, months_ago)
        day = await self.__get_text_day(channel_group, 0)

        if len(data) == 1:
            message = data[0]
        else:
            if len(day) == 2:
                data[1] += day[1]
            message = "Message count for {0.name} on {1[0]}: {1[1]}".format(channel, data)

        return await ctx.send(message)

    @channel_stats.command(name="day")
    async def channel_day(self, ctx: Context, channel: TextChannel, days_ago: int=0):
        channel_group = self.config.channel(channel)
        data = await self.__get_text_day(channel_group, days_ago)

        if len(data) == 1:
            message = data[0]
        else:
            message = "Message count for {0.name} on {1[0]}: {1[1]}".format(channel, data)

        return await ctx.send(message)

    @serverstats.group(name="member")
    async def member_stats(self, ctx: Context):
        ...

    @member_stats.command(name="total")
    async def member_total(self, ctx: Context, member: Member):
        member_group = self.config.member(member)
        data = await self.__get_text_total(member_group)
        day = await self.__get_text_day(member_group, 0)

        if len(day) == 2:
            data += day[1]
        return await ctx.send("Total message count for {0.name}: {1}".format(member, data))

    @member_stats.command(name="month")
    async def member_month(self, ctx: Context, member: Member, months_ago: int=0):
        member_group = self.config.member(member)
        data = await self.__get_text_month(member_group, months_ago)
        day = await self.__get_text_day(member_group, 0)

        if len(data) == 1:
            message = data[0]
        else:
            if len(day) == 2:
                data[1] += day[1]
            message = "Message count for {0.name} on {1[0]}: {1[1]}".format(member, data)

        return await ctx.send(message)

    @member_stats.command(name="day")
    async def member_day(self, ctx: Context, member: Member, days_ago: int=0):
        member_group = self.config.member(member)
        data = await self.__get_text_day(member_group, days_ago)

        if len(data) == 1:
            message = data[0]
        else:
            message = "Message count for {0.name} on {1[0]}: {1[1]}".format(member, data)

        return await ctx.send(message)

    @staticmethod
    async def __get_text_total(group: Group) -> int:
        data = (await group.text_total())[0]
        return data

    async def __get_text_month(self, group: Group, months_ago: int) -> list:
        if months_ago > 11:
            return ["The requested month is too old and has already been overwritten"]

        requested_month = self.current_month - months_ago
        text = (await group.text_month())[requested_month]

        if text == 0:
            data = ["No data found for the requested month"]
        else:
            data = [month_name[requested_month+1], text]

        return data

    async def __get_text_day(self, group: Group, days_ago: int) -> list:
        if days_ago > 31:
            return ["The requested day is too old and has already been overwritten"]

        delta = timedelta(days=days_ago)
        requested_day = (self.today - delta).day - 1
        data = (await group.text_day())[requested_day]

        if data[0] == "":
            return ["No data found for the requested day"]

        return data

    def __unload(self):
        self.timer.cancel()
