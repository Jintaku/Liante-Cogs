from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context
from random import randint
from datetime import datetime
import discord
import time

from .lvladmin import Lvladmin
from .x import X

BaseCog = getattr(commands, "Cog", object)

    
class Levels(BaseCog, Lvladmin, X):
    """
    A leveling system for Red.
    """
    __author__ = "Liante#0216"
    __version__ = "0.1.0"

    # Constants for data access
    XP_GOAL_BASE = "xp_goal_base"
    XP_GAIN_FACTOR = "xp_gain_factor"
    XP_MIN = "xp_min"
    XP_MAX = "xp_max"
    COOLDOWN = "cooldown"
    SINGLE_ROLE = "single_role"
    MAKE_ANNOUNCEMENTS = "make_announcements"
    ACTIVE = "active"
    LEVEL_UP_MESSAGE = "level_up_message"
    ROLE_CHANGE_MESSAGE = "role_change_message"

    ROLE_ID = "role_id"
    ROLE_NAME = "role_name"
    DESCRIPTION = "description"
    DEFAULT_DESC = "No description given."
    DEFAULT_ROLE = "No level roles"

    MEMBER_DATA = "member_data"
    MEMBER_ID = "member_id"
    DEFAULT_ID = "000000000000000000"
    USERNAME = "username"
    DEFAULT_USERNAME = "unknown"
    EXP = "exp"
    LEVEL = "level"
    GOAL = "goal"
    LAST_TRIGGER = "last_trigger"
    MESSAGE_COUNT = "message_count"
    MESSAGE_WITH_XP = "message_with_xp"

    GUILD_ROLES = "guild_roles"
    LEADERBOARD_MAX = "leaderboard_max"
    IGNORED_CHANNEL = "ignored_channel"

    GUILD_CONFIG = "guild_config"
    MEMBER = "member"

    def __init__(self, bot: Red):
        self.config = Config.get_conf(self, 4712468135468475)
        default_guild = {
            self.XP_GOAL_BASE: 100,
            self.XP_GAIN_FACTOR: 0.1,
            self.XP_MIN: 15,
            self.XP_MAX: 25,
            self.COOLDOWN: 60,
            self.SINGLE_ROLE: True,
            self.MAKE_ANNOUNCEMENTS: True,
            self.ACTIVE: True,
            self.LEADERBOARD_MAX: 20,
            self.LEVEL_UP_MESSAGE: "Congratulations {mention}, you're now level {level}. ",
            self.ROLE_CHANGE_MESSAGE: "Your days as {oldrole} are over. Your new role is {newrole}.",
            self.GUILD_ROLES: []
        }

        default_channel = {
            self.IGNORED_CHANNEL: False
        }

        default_member = {
            self.MEMBER_ID: self.DEFAULT_ID,
            self.USERNAME: self.DEFAULT_USERNAME,
            self.ROLE_NAME: self.DEFAULT_ROLE,
            self.EXP: 0,
            self.LEVEL: 0,
            self.GOAL: 100,
            self.LAST_TRIGGER: 0,
            self.MESSAGE_COUNT: 0,
            self.MESSAGE_WITH_XP: 0
        }

        self.config.register_guild(**default_guild, force_registration=True)
        self.config.register_channel(**default_channel, force_registration=True)
        self.config.register_member(**default_member, force_registration=True)

    @commands.guild_only()
    @commands.command(name="level", aliases=["lvl"])
    async def level_check(self, ctx: Context, member: discord.Member = None):
        """
        Displays your current level.

        Mention someone to know theirs.
        """
        if member is None:
            member = ctx.author
        if member.bot:
            await ctx.send("Bots can't play levels =(")
            return

        guild = ctx.guild
        guild_config = self.config.guild(guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        embed = await self._level_embed(ctx, member, member_data)
        await ctx.send(embed=embed)

    async def _level_embed(self, ctx: Context, member: discord.Member, member_data):
        """
        Internal method to format the level card embed
        """
        current_lvl = await member_data.get_raw(self.LEVEL)
        current_exp = await member_data.get_raw(self.EXP)
        next_goal = await member_data.get_raw(self.GOAL)
        level_role = await member_data.get_raw(self.ROLE_NAME)
        username = await member_data.get_raw(self.USERNAME)

        embed = discord.Embed(title=username, color=member.color)
        if member.top_role.name != "@everyone":
            embed.description = member.top_role.name
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.set_thumbnail(url=member.avatar_url)
        embed.add_field(name="Level", value=current_lvl, inline=True)
        embed.add_field(name="Role", value=level_role, inline=True)
        embed.add_field(name="Current XP", value="{} / {}".format(current_exp, next_goal), inline=True)
        embed.timestamp = datetime.utcnow()

        return embed

    @commands.command(name="levelboard", aliases=["lb", "lvlboard"])
    async def leaderboard(self, ctx: Context):
        """
        Display a leaderboard of the top 20 members in the guild
        """
        guild_config = await self._get_guild_config(ctx.guild)
        leaderboard_max = await guild_config.get_raw(self.LEADERBOARD_MAX)
        guild_members = await self._get_members(ctx.guild)
        all_members = guild_members.values()
        if len(all_members) == 0:
            await ctx.send("No member activity registered.")
            return

        all_members = sorted(all_members, key=lambda u: (u[self.LEVEL], u[self.EXP]), reverse=True)
        top_member = discord.utils.find(lambda m: str(m.id) == all_members[0][self.MEMBER_ID], ctx.guild.members)
        member_list = ""

        embed = discord.Embed()
        embed.set_author(name=ctx.guild.name + " Leaderboard")
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.timestamp = datetime.utcnow()

        i = 0
        while i < leaderboard_max and i < len(all_members):
            last_digits = int(str(i)[-2:])

            member = all_members[i]
            member_list += "#{0} <@!{1}>\t**level**: {2}\n".format(i + 1, member[self.MEMBER_ID],
                                                                    member[self.LEVEL])
            i += 1

        try:
            embed.description = member_list
            await ctx.send(embed=embed)
        except discord.errors.HTTPException:
            await ctx.send("The list is too long. Please set a lower limit with `!la config set leaderboard_max`")

