from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context
from random import randint
import discord
import motor.motor_asyncio
import bson
import time


class Levels:
    """
    A leveling system for Red.
    """
    __author__ = "Liante#0216"

    # Constants for data access
    XP_GOAL_BASE = "xp_goal_base"
    XP_GAIN_FACTOR = "xp_gain_factor"
    XP_MIN = "xp_min"
    XP_MAX = "xp_max"
    COOLDOWN = "cooldown"
    SINGLE_ROLE = "single_role"
    AUTOROLES = "autoroles"

    ROLE_ID = "role_id"
    ROLE_NAME = "role_name"
    DESCRIPTION = "description"
    DEFAULT_DESC = "No description given."

    USER_ID = "user_id"
    USERNAME = "username"
    EXP = "exp"
    LEVEL = "level"
    GOAL = "goal"
    LAST_TRIGGER = "last_trigger"

    GUILD_ID = "guild_id"
    GUILD_NAME = "guild_name"

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, 4712468135468475)
        default_guild = {
            self.XP_GOAL_BASE: 100,
            self.XP_GAIN_FACTOR: 0.01,
            self.XP_MIN: 15,
            self.XP_MAX: 25,
            self.COOLDOWN: 60,
            self.SINGLE_ROLE: True,
            self.AUTOROLES: []
        }

        self.config.register_guild(**default_guild, force_registration=True)

        self.client = motor.motor_asyncio.AsyncIOMotorClient()
        self.levels_db = self.client.levels

    async def on_message(self, message):
        # ignore bots, dms, and red commands
        if message.author.bot:
            return

        if not message.guild:
            return

        prefixes = await Config.get_core_conf().prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return

        user = message.author
        guild = message.guild
        channel = message.channel

        guild_conf = self.config.guild(guild)
        guild_coll = await self._get_guild_coll(guild)
        user_data = await self._get_user_data(guild_conf, guild_coll, user)

        last_trigger = user_data[self.LAST_TRIGGER]
        curr_time = time.time()
        cooldown = await guild_conf.cooldown()

        if curr_time - last_trigger <= cooldown:
            return

        level_up = await self._process_xp(guild_conf, guild_coll, user_data)
        if level_up:
            await channel.send("Congratulations {0}, you're now level {1}".format(user.mention, user_data[self.LEVEL]))

    async def _get_guild_coll(self, guild: discord.Guild):
        """
        Each guild gets a collection and a first document containing the guild's data
        """
        guild_coll = self.levels_db[str(guild.id)]
        if await guild_coll.find_one({self.GUILD_ID: guild.id}) is None:
            guild_data = {self.GUILD_ID: bson.Int64(guild.id),
                          self.GUILD_NAME: guild.name}
            await guild_coll.insert_one(guild_data)
        return guild_coll

    async def _get_user_data(self, guild_conf, guild_coll, user: discord.Member):
        """
        Each user is represented by a document inside the guild's collection
        """
        user_data = await guild_coll.find_one({self.USER_ID: user.id})
        if user_data is None:
            user_data = {self.USER_ID: bson.Int64(user.id),
                         self.USERNAME: user.display_name,
                         self.EXP: 0,
                         self.LEVEL: 0,
                         self.GOAL: await guild_conf.xp_goal_base(),
                         self.LAST_TRIGGER: time.time()}
            await guild_coll.insert_one(user_data)
            await self._process_xp(guild_conf, guild_coll, user_data)
        return user_data

    async def _process_xp(self, guild_conf, guild_coll, user_data):
        """
        _xp-logic-label:
        XP logic explanation
        ====================

        Based on `Link Mathematics of XP <http://onlyagame.typepad.com/only_a_game/2006/08/mathematics_of_.html>`_
        and `Link Mee6 documentation <http://mee6.github.io/Mee6-documentation/levelxp/>`_ I picked Mee6' polynomial
        formula and added a small xp factor depending on the user's level to make up for the difference between
        the basic progression ratio and the total progression ratio.

        This would normally be achieved by increasing xp rewards based on the task's difficulty. Since the task
        is the same all the time in Discord, e.i. sending messages, this is the workaround I picked. It basically
        translates into similar difficulty at low levels but reachable high levels.
        """
        xp_min = await guild_conf.xp_min()
        xp_max = await guild_conf.xp_max()
        xp_gain_factor = await guild_conf.xp_gain_factor()
        xp_gain = randint(xp_min, xp_max)
        message_xp = xp_gain + int(xp_gain * xp_gain_factor * user_data[self.LEVEL])

        user_data[self.EXP] = user_data[self.EXP] + message_xp
        await guild_coll.update_one({self.USER_ID: user_data[self.USER_ID]},
                                    {"$set": {self.EXP: user_data[self.EXP]}})
        await guild_coll.update_one({self.USER_ID: user_data[self.USER_ID]},
                                    {"$set": {self.LAST_TRIGGER: time.time()}})

        if user_data[self.EXP] >= user_data[self.GOAL]:
            await self._level_up(guild_coll, user_data)
            return True
        return False

    async def _level_up(self, guild_coll, user_data):
        # Separated for admin commands implementation
        await self._level_xp(guild_coll, user_data)
        await self._level_update(guild_coll, user_data)
        await self._level_goal(guild_coll, user_data)

    async def _level_xp(self, guild_coll, user_data):
        user_data[self.EXP] = user_data[self.EXP] - user_data[self.GOAL]
        await guild_coll.update_one({self.USER_ID: user_data[self.USER_ID]},
                                    {"$set": {self.EXP: user_data[self.EXP]}})

    async def _level_update(self, guild_coll, user_data):
        user_data[self.LEVEL] = user_data[self.LEVEL] + 1
        await guild_coll.update_one({self.USER_ID: user_data[self.USER_ID]},
                                    {"$set": {self.LEVEL: user_data[self.LEVEL]}})

    async def _level_goal(self, guild_coll, user_data):
        # 5 * lvl**2 + 50 * lvl + 100 see :this:`xp-logic-label` for more info.
        user_data[self.GOAL] = 5 * user_data[self.LEVEL] ** 2 + 50 * user_data[self.LEVEL] + 100
        await guild_coll.update_one({self.USER_ID: user_data[self.USER_ID]},
                                    {"$set": {self.GOAL: user_data[self.GOAL]}})

    @commands.guild_only()
    @commands.command()
    async def xp(self, ctx: Context, user: discord.Member = None):
        """
        Displays your current xp.

        Mention someone to know theirs.
        """
        if user is None:
            user = ctx.author
        guild = ctx.guild
        guild_id = str(guild.id)
        user_id = user.id
        user_data = await self.levels_db[guild_id].find_one({self.USER_ID: user_id})
        current_exp = user_data[self.EXP]
        next_goal = user_data[self.GOAL]
        await ctx.send("{0}'s info:\nxp: {1}; goal: {2}; needed: {3}".format(user.mention,
                                                                             current_exp,
                                                                             next_goal,
                                                                             next_goal - current_exp))

    @commands.command(aliases=["lvl"])
    async def level(self, ctx: Context, user: discord.Member = None):
        """
        Displays your current level.

        Mention someone to know theirs.
        """
        if user is None:
            user = ctx.author
        if user.bot:
            await ctx.send("Bots can't play levels =(")
            return

        guild = ctx.guild
        guild_id = str(guild.id)
        user_id = user.id
        user_data = await self.levels_db[guild_id].find_one({self.USER_ID: user_id})
        if user_data is None:
            await ctx.send("User not registered in the database")
            return

        current_lvl = user_data[self.LEVEL]
        await ctx.send("{0}'s current level is: {1}".format(user.mention, current_lvl))

    @checks.admin()
    @commands.guild_only()
    @commands.group(aliases=["la"], autohelp=True)
    async def lvladmin(self, ctx: Context):
        """Admin commands."""
        pass

    @lvladmin.group(autohelp=True)
    async def guild(self, ctx: Context):
        """Guild options"""
        pass

    @guild.group(autohelp=True)
    async def roles(self, ctx: Context):
        """Autoroles options"""
        pass

    @roles.command(name="list")
    async def roles_list(self, ctx: Context):
        """Shows all configured roles"""
        roles = await self.config.guild(ctx.guild).autoroles()
        embed = discord.Embed(title="Configured Roles:")
        for role in roles:
            embed.add_field(name="Level {0} - {1}".format(role[self.LEVEL], role[self.ROLE_NAME]),
                            value="{}".format(role[self.DESCRIPTION]),
                            inline=False)

        if not embed.fields:
            embed.description = "No autoroles have been defined in this Guild yet."

        embed.set_footer(text="use !la guild roles add <role> <level> [description] to add more")

        await ctx.send(embed=embed)

    @roles.command(name="add")
    async def roles_add(self, ctx: Context, role: discord.Role, level: int, *, description=None):
        """
        Adds a new automatic role

        The roles are by default non-cumulative. Change the mode with [p]la config set mode [True|False]
        """
        role_id = role.id
        role_name = role.name
        if description is None:
            description = self.DEFAULT_DESC
        role_config = {
            self.ROLE_ID: role_id,
            self.ROLE_NAME: role_name,
            self.LEVEL: level,
            self.DESCRIPTION: description
        }
        autoroles: list = await self.config.guild(ctx.guild).autoroles()
        autoroles.append(role_config)
        sorted_roles = sorted(autoroles, key=lambda k: k[self.LEVEL])
        await self.config.guild(ctx.guild).autoroles.set(sorted_roles)
        await ctx.send("{0} will be automatically earned at level {1}".format(role.name, level))

    @guild.command(name="reset")
    async def guild_reset(self, ctx: Context):
        """Deletes ***all*** stored data of the guild."""
        guild_coll = self.levels_db[str(ctx.message.guild.id)]
        await guild_coll.drop()

    @lvladmin.group(autohelp=True)
    async def user(self, ctx: Context):
        """User options"""
        pass

    @user.command(name="reset")
    async def user_reset(self, ctx: Context, user: discord.Member):
        """
        Deletes ***all*** stored data of a user.

        user: Mention the user whose data you want to delete.
        """
        guild_coll = self.levels_db[str(ctx.message.guild.id)]
        await guild_coll.delete_one({self.USER_ID: user.id})
        await ctx.send("Data for {} has been deleted!".format(user.mention))

    @user.group(name="set", autohelp=True)
    async def user_set(self, ctx: Context):
        """Edit user data."""
        pass

    @user_set.command(name="level", aliases=["lvl"])
    async def set_level(self, ctx: Context, user: discord.Member, level: int):
        """
        Changes the level of a user.

        user: Mention the user to which you want to change the level.

        level: The new user level.
        """

        guild_coll = self.levels_db[str(ctx.message.guild.id)]
        user_data = await guild_coll.find_one({self.USER_ID: user.id})
        if user_data is None:
            await ctx.send("No data found for {}".format(user.mention))
            return

        user_data[self.LEVEL] = level

        await guild_coll.update_one({self.USER_ID: user_data[self.USER_ID]},
                                    {"$set": {self.LEVEL: user_data[self.LEVEL]}})
        await self._level_goal(guild_coll, user_data)
        await ctx.send("Level of {0} has been changed to {1}".format(user.mention, level))

    @lvladmin.group(name="config", autohelp=True)
    async def configuration(self, ctx: Context):
        """Configuration options"""
        pass

    @configuration.command(name="reset")
    async def config_reset(self, ctx: Context):
        """Reset all configuration to defaults"""
        await self.config.guild(ctx.guild).clear()
        await ctx.send("Configuration defaults have been restored")

    @configuration.group(name="set", autohelp=True)
    async def config_set(self, ctx: Context):
        """Change config values"""
        pass

    @config_set.command(name="goal")
    async def set_xp_goal_base(self, ctx: Context, new_value: int):
        """
        Base goal xp

        This is the xp needed to reach level 1. Subsequent goals are measured with the current level's value.
        """
        await self.config.guild(ctx.guild).xp_goal_base.set(new_value)
        await ctx.send("XP goal base value updated")

    @config_set.command(name="gainfactor", aliases=["gf"])
    async def set_xp_gain_factor(self, ctx: Context, new_value: float):
        """
        Increases the xp reward

        XP gained += XP gained * lvl * this factor
        """
        await self.config.guild(ctx.guild).xp_gain_factor.set(new_value)
        await ctx.send("XP gain factor value updated")

    @config_set.command(name="minxp")
    async def set_xp_min(self, ctx: Context, new_value: int):
        """
        Minimum xp per message

        Note that the real minimum is this * lvl * gain factor
        """
        await self.config.guild(ctx.guild).xp_min.set(new_value)
        await ctx.send("Minimum xp per message value updated")

    @config_set.command(name="maxxp")
    async def set_xp_max(self, ctx: Context, new_value: int):
        """
        Maximum xp per message

        Note that the real maximum is this * lvl * gain factor
        """
        await self.config.guild(ctx.guild).xp_max.set(new_value)
        await ctx.send("Maximum xp per message value updated")

    @config_set.command(name="cooldown")
    async def set_cooldown(self, ctx: Context, new_value: int):
        """
        Time between xp awards

        In seconds
        """
        await self.config.guild(ctx.guild).cooldown.set(new_value)
        await ctx.send("XP cooldown value updated")

    @config_set.command(name="mode")
    async def set_role_mode(self, ctx: Context, new_value: bool):
        """
        Autoroles handling

        Determines if old roles should be removed when a new one is gained by leveling up. Set False to keep them.
        """
        await self.config.guild(ctx.guild).single_role.set(new_value)
        await ctx.send("Role mode value updated")

    @configuration.group(name="get", autohelp=True)
    async def config_get(self, ctx: Context):
        """Check current configuration"""
        pass

    @config_get.command(name="goal")
    async def get_xp_goal_base(self, ctx: Context):
        """
        Base goal xp

        This is the xp needed to reach level 1. Subsequent goals are measured with the current level's value.
        """
        value = await self.config.guild(ctx.guild).xp_goal_base()
        await ctx.send("XP goal base: {}".format(value))

    @config_get.command(name="gainfactor", aliases=["gf"])
    async def get_xp_gain_factor(self, ctx: Context):
        """
        Increases the xp reward

        XP gained += XP gained * lvl * this factor
        """
        value = await self.config.guild(ctx.guild).xp_gain_factor()
        await ctx.send("XP gain factor: {}".format(value))

    @config_get.command(name="minxp")
    async def get_xp_min(self, ctx: Context):
        """
        Minimum xp per message

        Note that the real minimum is this * lvl * gain factor
        """
        value = await self.config.guild(ctx.guild).xp_min()
        await ctx.send("Minimum xp per message: {}".format(value))

    @config_get.command(name="maxxp")
    async def get_xp_max(self, ctx: Context):
        """
        Maximum xp per message

        Note that the real maximum is this * lvl * gain factor
        """
        value = await self.config.guild(ctx.guild).xp_max()
        await ctx.send("Maximum xp per message: {}".format(value))

    @config_get.command(name="cooldown")
    async def get_cooldown(self, ctx: Context):
        """
        Time between xp awards

        In seconds
        """
        value = await self.config.guild(ctx.guild).cooldown()
        await ctx.send("XP cooldown: {}".format(value))

    @config_get.command(name="mode")
    async def get_role_mode(self, ctx: Context):
        """
        Autoroles handling

        Determines if old roles should be removed when a new one is gained by leveling up. Set False to keep them.
        """
        value = "single" if await self.config.guild(ctx.guild).single_role() else "multi"
        await ctx.send("The role mode is set to: {}-role".format(value))
