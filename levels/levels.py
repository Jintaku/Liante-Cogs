from redbot.core import commands, Config, checks
from redbot.core.utils.menus import menu, commands, DEFAULT_CONTROLS
from redbot.core.bot import Red
from redbot.core.commands import Context
from random import randint
from datetime import datetime
import discord
import time
import logging
from .lvladmin import Lvladmin
from .x import X

log = logging.getLogger("levels")  # Thanks to Sinbad for the example code for logging
log.setLevel(logging.DEBUG)

console = logging.StreamHandler()

if logging.getLogger("red").isEnabledFor(logging.DEBUG):
    console.setLevel(logging.DEBUG)
else:
    console.setLevel(logging.INFO)
log.addHandler(console)

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
            self.ACTIVE: False,
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

        # If nobody mentioned, command user is the one selected
        if member is None:
            member = ctx.author

        # If a bot is mentioned, stop
        if member.bot:
            await ctx.send("Bots can't play levels =(")
            return

        # Get guild then get guild config then get member_data based on that
        guild = ctx.guild
        guild_config = self.config.guild(guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        # Build Embed and show it
        embed = await self._level_embed(ctx, member, member_data)
        await ctx.send(embed=embed)

    async def _level_embed(self, ctx: Context, member: discord.Member, member_data):
        """
        Internal method to format the level card embed
        """
        # Get member information
        current_lvl = await member_data.get_raw(self.LEVEL)
        current_exp = await member_data.get_raw(self.EXP)
        next_goal = await member_data.get_raw(self.GOAL)
        level_role = await member_data.get_raw(self.ROLE_NAME)
        username = await member_data.get_raw(self.USERNAME)

        # Build Embed based on information just queried
        embed = discord.Embed(title=username, color=member.color)

        # If highest level is not @everyone then show it
        if member.top_role.name != "@everyone":
            embed.description = member.top_role.name

        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.set_thumbnail(url=member.avatar_url)
        embed.add_field(name="Level", value=current_lvl, inline=True)
        embed.add_field(name="Role", value=level_role, inline=True)

        # Calculate percentage
        percentage = current_exp * 100 / next_goal
        log.debug(percentage)

        # Emojis for progress bar
        check_box_emoji = "\N{WHITE HEAVY CHECK MARK}"
        empty_box_emoji = "\N{BLACK LARGE SQUARE}"

        # The progress bar
        progress_bar = (check_box_emoji * int(percentage // 10)) + (empty_box_emoji * int(10 - percentage // 10))

        embed.add_field(name=f"XP ({current_exp}/{next_goal})", value=f"{progress_bar}", inline=True)

        return embed

    @commands.command(name="levelboard", aliases=["lb", "lvlboard"])
    async def leaderboard(self, ctx: Context):
        """
        Display a leaderboard of the top 20 members in the guild
        """
        # Get members data and leaderboard configuration
        guild_config = await self._get_guild_config(ctx.guild)
        leaderboard_max = await guild_config.get_raw(self.LEADERBOARD_MAX)
        guild_members = await self._get_members(ctx.guild)
        all_members = guild_members.values()

        # Get user data
        member = ctx.author
        guild = ctx.guild
        guild_config = self.config.guild(guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)
        member_lvl = await member_data.get_raw(self.LEVEL)
        member_id = await member_data.get_raw(self.MEMBER_ID)
        member_username = await member_data.get_raw(self.USERNAME)

        # If no members then don't show it
        if len(all_members) == 0:
            await ctx.send("No member activity registered.")
            return

        # Sort members by level and XP
        all_members = sorted(all_members, key=lambda u: (u[self.LEVEL], u[self.EXP]), reverse=True)
        top_member = discord.utils.find(lambda m: str(m.id) == all_members[0][self.MEMBER_ID], ctx.guild.members)

        # Set variable to be appended to
        member_list = ""
        member_list_blocks = []
        # Loop to create member_list
        for i in range(0, len(all_members)):
            member = all_members[i]
            if member[self.MEMBER_ID] == member_id:
                member_rank = i + 1
            member_list += "\n**#{number}** <@!{ID}> ({LVL})".format(number=i+1, ID=member[self.MEMBER_ID], LVL=member[self.LEVEL])
            if i + 1 % 10 == 0:
                member_list_blocks.append(member_list)
                member_list = ""
        if member_list != "":
            member_list_blocks.append(member_list)


        # Try to set and send embed and tell user if it excepts
        try:
            embeds = []
            for page in member_list_blocks:
                # Start building Embed
                embed = discord.Embed()
                embed.set_author(name=ctx.guild.name + " Leaderboard")
                embed.set_thumbnail(url=ctx.guild.icon_url)
                embed.description = page
                embed.set_footer(text=f"You're rank #{member_rank} (Level {member_lvl}), {member_username}.")
                embeds.append(embed)
            await menu(ctx, pages=embeds, controls=DEFAULT_CONTROLS, message=None, page=0, timeout=15)
        except discord.errors.HTTPException:
            await ctx.send("The list is too long. Please set a lower limit with `!la config set leaderboard_max`")

