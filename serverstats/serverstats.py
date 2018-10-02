from redbot.core import commands, Config, bot
from redbot.core.bot import Red
from redbot.core.commands import Context
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

    GUILD_TEXT_DAY = "guild_text_day"
    GUILD_TEXT_MONTH = "guild_text_month"
    GUILD_TEXT_TOTAL = "guild_text_total"
    GUILD_VOICE_DAY = "guild_voice_day"
    GUILD_VOICE_MONTH = "guild_voice_month"
    GUILD_VOICE_TOTAL = "guild_voice_total"

    MEMBER_TEXT_DAY = "member_text_day"
    MEMBER_TEXT_TOTAL = "member_text_total"
    MEMBER_VOICE_DAY = "member_voice_day"
    MEMBER_VOICE_TOTAL = "member_voice_total"

    CHANNEL_TEXT_DAY = "channel_text_day"
    CHANNEL_TEXT_MONTH = "channel_text_month"
    CHANNEL_TEXT_TOTAL = "channel_text_total"
    CHANNEL_VOICE_DAY = "channel_voice_day"
    CHANNEL_VOICE_MONTH = "channel_voice_month"
    CHANNEL_VOICE_TOTAL = "channel_voice_total"

    def __init__(self, red_bot):
        self.config = Config.get_conf(self, 4712468135468476)
        self.bot: Red = red_bot

        default_guild = {
            self.GUILD_TEXT_DAY: 0,
            self.GUILD_TEXT_MONTH: 0,
            self.GUILD_TEXT_TOTAL: 0,
            self.GUILD_VOICE_DAY: 0,
            self.GUILD_VOICE_MONTH: 0,
            self.GUILD_VOICE_TOTAL: 0
        }

        default_member = {
            self.MEMBER_TEXT_DAY: 0,
            self.MEMBER_TEXT_TOTAL: 0,
            self.MEMBER_VOICE_DAY: 0,
            self.MEMBER_VOICE_TOTAL: 0
        }

        default_channel = {
            self.CHANNEL_TEXT_DAY: 0,
            self.CHANNEL_TEXT_MONTH: 0,
            self.CHANNEL_TEXT_TOTAL: 0,
            self.CHANNEL_VOICE_DAY: 0,
            self.CHANNEL_VOICE_MONTH: 0,
            self.CHANNEL_VOICE_TOTAL: 0
        }

        self.config.register_guild(**default_guild, force_registration=True)
        self.config.register_member(**default_member, force_registration=True)
        self.config.register_channel(**default_channel, force_registration=True)

        self.timer = asyncio.create_task(self.timer_test())

    async def timer_test(self):
        channel = self.bot.get_channel(434092671229755394)
        count = 1
        while True:
            await asyncio.sleep(5)
            await channel.send("test {}".format(count))
            count += 1

    @commands.command()
    async def stop_test(self, ctx: Context):
        self.timer.cancel()
        await ctx.send("stopped!")

    @commands.command()
    async def start_test(self, ctx: Context):
        self.timer = asyncio.create_task(self.timer_test())
        await ctx.send("started!!")

    def __unload(self):
        print("stopping test task")
        self.timer.cancel()
        print("unload successful")

    async def on_message(self, message: discord.Message):
        ...
