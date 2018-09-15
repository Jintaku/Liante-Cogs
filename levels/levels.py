from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context
from random import randint
from datetime import datetime
import discord
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
        self.bot = bot
        self.config = Config.get_conf(self, 4712468135468475)
        default_guild = {
            self.XP_GOAL_BASE: 100,
            self.XP_GAIN_FACTOR: 0.01,
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

    async def on_message(self, message: discord.Message):
        # ignore bots, dms, and red commands
        if not await self._is_valid_message(message):
            return

        member = message.author
        guild = message.guild
        channel = message.channel

        guild_config = await self._get_guild_config(guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        message_count = await member_data.get_raw(self.MESSAGE_COUNT)
        await member_data.set_raw(self.MESSAGE_COUNT, value=message_count + 1)

        last_trigger = await member_data.get_raw(self.LAST_TRIGGER)
        curr_time = time.time()
        cooldown = await guild_config.get_raw(self.COOLDOWN)

        if curr_time - last_trigger <= cooldown:
            return

        old_role = await member_data.get_raw(self.ROLE_NAME)

        level_up = await self._process_xp(guild_config=guild_config,
                                          member_data=member_data,
                                          member=member)

        if level_up and await self.config.guild(guild).make_announcements():
            level = await member_data.get_raw(self.LEVEL)
            new_role = await member_data.get_raw(self.ROLE_NAME)
            message_variables = {
                "mention": member.mention,
                "username": member.display_name,
                "level": level,
                "oldrole": old_role,
                "newrole": new_role
            }
            level_up_message = (await guild_config.get_raw(self.LEVEL_UP_MESSAGE)).format(**message_variables)
            if old_role != new_role:
                level_up_message += (await guild_config.get_raw(self.ROLE_CHANGE_MESSAGE)).format(**message_variables)
            if level_up_message != "":
                await channel.send(level_up_message)

    async def _is_valid_message(self, message: discord.Message):
        if message.author.bot:
            return False

        if not message.guild:
            return False

        guild_config = await self._get_guild_config(message.guild)
        if not await guild_config.get_raw(self.ACTIVE):
            return False

        channel_config = await self._get_channel_config(message.channel)
        if await channel_config.get_raw(self.IGNORED_CHANNEL):
            return False

        prefixes = await Config.get_core_conf().prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return False

        return True

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # this should handle any nickname and username changes
        if before.display_name == after.display_name:
            return

        guild = before.guild
        guild_config = self.config.guild(guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=before)

        await member_data.set_raw(self.USERNAME, value=after.display_name)

    async def _get_channel_config(self, channel: discord.TextChannel):
        """
        The channel config helps determine if a channel should be ignored.
        """
        return self.config.channel(channel)

    async def _get_guild_config(self, guild: discord.Guild):
        """
        Each guild gets a collection and a first document containing the guild's data
        """
        return self.config.guild(guild)

    async def _get_member_data(self, **kwargs):
        """
        Each member is represented by a document inside the guild's collection
        """
        guild_config = kwargs[self.GUILD_CONFIG]
        member = kwargs[self.MEMBER]
        member_data = self.config.member(member)

        if await member_data.get_raw(self.MEMBER_ID) == self.DEFAULT_ID:
            new_member = {
                self.MEMBER_ID: str(member.id),
                self.USERNAME: member.display_name,
                self.ROLE_NAME: self.DEFAULT_ROLE,
                self.EXP: 0,
                self.LEVEL: 0,
                self.GOAL: await guild_config.xp_goal_base(),
                self.LAST_TRIGGER: 0,
                self.MESSAGE_COUNT: 0,
                self.MESSAGE_WITH_XP: 0
            }
            for k, v in new_member.items():
                await member_data.set_raw(k, value=v)

        return member_data

    async def _get_roles(self, guild: discord.Guild):
        """
        This gets all the configured auto-roles for a given guild.
        """
        return await (await self._get_guild_config(guild)).get_raw(self.GUILD_ROLES)

    async def _get_members(self, guild: discord.Guild = None):
        """
        This gets all the members that have been active and therefore added to the database.
        """
        return await self.config.all_members(guild)

    async def _process_xp(self, **kwargs):
        """
        _xp-logic-label:
        XP logic explanation
        ====================

        Based on `Link Mathematics of XP <http://onlyagame.typepad.com/only_a_game/2006/08/mathematics_of_.html>`_
        and `Link Mee6 documentation <http://mee6.github.io/Mee6-documentation/levelxp/>`_ I picked Mee6' polynomial
        formula and added a small xp factor depending on the member's level to make up for the difference between
        the basic progression ratio and the total progression ratio.

        This would normally be achieved by increasing xp rewards based on the task's difficulty. Since the task
        is the same all the time in Discord, e.i. sending messages, this is the workaround I picked. It basically
        translates into similar difficulty at low levels but reachable high levels.
        """
        guild_config = kwargs[self.GUILD_CONFIG]
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]

        xp_min = await guild_config.get_raw(self.XP_MIN)
        xp_max = await guild_config.get_raw(self.XP_MAX)
        xp_gain_factor = await guild_config.get_raw(self.XP_GAIN_FACTOR)
        xp_gain = randint(xp_min, xp_max)
        message_xp = xp_gain + int(xp_gain * xp_gain_factor * (await member_data.get_raw(self.LEVEL)))
        curr_xp = await member_data.get_raw(self.EXP)

        await member_data.set_raw(self.EXP, value=curr_xp + message_xp)
        await member_data.set_raw(self.LAST_TRIGGER, value=time.time())

        message_with_xp = await member_data.get_raw(self.MESSAGE_WITH_XP)
        await member_data.set_raw(self.MESSAGE_WITH_XP, value=message_with_xp + 1)

        if await member_data.get_raw(self.EXP) >= await member_data.get_raw(self.GOAL):
            await self._level_up(member_data=member_data,
                                 member=member)
            return True
        return False

    async def _level_up(self, **kwargs):
        # Separated for admin commands implementation
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]

        await self._level_xp(member_data=member_data)
        await self._level_update(member_data=member_data,
                                 member=member)
        await self._level_goal(member_data=member_data)

    async def _level_xp(self, **kwargs):
        member_data = kwargs[self.MEMBER_DATA]

        curr_xp = await member_data.get_raw(self.EXP)
        goal = await member_data.get_raw(self.GOAL)
        await member_data.set_raw(self.EXP, value=curr_xp - goal)

    async def _level_update(self, **kwargs):
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]

        curr_level = await member_data.get_raw(self.LEVEL)
        await member_data.set_raw(self.LEVEL, value=curr_level + 1)
        await self._level_role(member_data=member_data, member=member)

    async def _level_role(self, **kwargs):
        """
        Checks if the member gets a role by leveling up
        """
        member_data = kwargs[self.MEMBER_DATA]
        member: discord.Member = kwargs[self.MEMBER]
        guild_config = await self._get_guild_config(member.guild)
        guild_roles = await guild_config.get_raw(self.GUILD_ROLES)
        autoroles = []
        level = await member_data.get_raw(self.LEVEL)
        role_name = await member_data.get_raw(self.ROLE_NAME)

        if len(guild_roles) == 0:
            return

        for role in guild_roles:
            autoroles.append(discord.utils.find(lambda r: str(r.id) == role[self.ROLE_ID], member.guild.roles))

        async def _assign_role(index):
            _new_role = autoroles[index]
            for _member_role in member.roles:
                if _member_role in autoroles:
                    await member.remove_roles(_member_role, reason="level up")
            await member.add_roles(_new_role, reason="level up")
            _new_role = guild_roles[index][self.ROLE_NAME]
            await member_data.set_raw(self.ROLE_NAME, value=_new_role)

        if level < guild_roles[0][self.LEVEL] and role_name != self.DEFAULT_ROLE:
            for member_role in member.roles:
                if member_role in autoroles:
                    await member.remove_roles(member_role, reason="levels lost")
            await member_data.set_raw(self.ROLE_NAME, value=self.DEFAULT_ROLE)

        i = 0
        while i < len(guild_roles) - 1:
            if guild_roles[i][self.LEVEL] <= level < guild_roles[i + 1][self.LEVEL]:
                if role_name != guild_roles[i][self.ROLE_NAME]:
                    await _assign_role(i)
                break
            i += 1

        i = -1
        if guild_roles[i][self.LEVEL] <= level and role_name != guild_roles[i][self.ROLE_NAME]:
            await _assign_role(i)

    async def _level_goal(self, **kwargs):
        # 5 * lvl**2 + 50 * lvl + 100 see :this:`xp-logic-label` for more info.
        member_data = kwargs[self.MEMBER_DATA]

        level = await member_data.get_raw(self.LEVEL)
        goal = 5 * level ** 2 + 50 * level + 100
        await member_data.set_raw(self.GOAL, value=goal)

    async def _give_xp(self, **kwargs):
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]
        xp = kwargs[self.EXP]

        exp = await member_data.get_raw(self.EXP)
        exp += xp
        await member_data.set_raw(self.EXP, value=exp)

        count = 0
        goal = await member_data.get_raw(self.GOAL)
        while exp >= goal:
            await self._level_up(member_data=member_data,
                                 member=member)
            count += 1
            exp = await member_data.get_raw(self.EXP)
            goal = await member_data.get_raw(self.GOAL)
        return count

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
        embed.add_field(name="XP", value=current_exp, inline=True)
        embed.add_field(name="Goal", value=next_goal, inline=True)
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

        embed = discord.Embed(title="{:-^75}".format("**Leaderboard**"))
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.set_thumbnail(url=top_member.avatar_url)
        embed.timestamp = datetime.utcnow()

        i = 0
        while i < leaderboard_max and i < len(all_members):
            last_digits = int(str(i)[-2:])
            suffix = None
            if last_digits not in [10, 11, 12]:
                if last_digits % 10 == 0:
                    suffix = "st"
                elif last_digits % 10 == 1:
                    suffix = "nd"
                elif last_digits % 10 == 2:
                    suffix = "rd"

            if suffix is None:
                suffix = "th"

            member = all_members[i]
            member_list += "{0}{1}. <@!{2}>\t**lvl**: {3}\n".format(i + 1, suffix, member[self.MEMBER_ID],
                                                                    member[self.LEVEL])
            i += 1

        try:
            embed.description = member_list
            await ctx.send(embed=embed)
        except discord.errors.HTTPException:
            await ctx.send("The list is too long. Please set a lower limit with `!la config set leaderboard_max`")

    @checks.admin_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.group(aliases=["la"])
    async def lvladmin(self, ctx: Context):
        """Admin commands."""
        pass

    @lvladmin.group()
    async def guild(self, ctx: Context):
        """Guild options"""
        pass

    @guild.group()
    async def roles(self, ctx: Context):
        """Autoroles options"""
        pass

    @roles.command(name="list")
    async def roles_list(self, ctx: Context):
        """Shows all configured roles"""
        guild_roles = await self._get_roles(ctx.guild)
        embed = discord.Embed(title="Configured Roles:")
        for role in guild_roles:
            embed.add_field(name="Level {0} - {1}".format(role[self.LEVEL], role[self.ROLE_NAME]),
                            value="{}".format(role[self.DESCRIPTION]),
                            inline=False)

        if not embed.fields:
            embed.description = "No autoroles have been defined in this Guild yet."

        embed.set_footer(text="use !la guild roles add <role> <level> [description] to add more")

        await ctx.send(embed=embed)

    @roles.command(name="add")
    async def roles_add(self, ctx: Context, new_role: discord.Role, level: int, *, description=None):
        """
        Adds a new automatic role

        The roles are by default non-cumulative. Cumulative roles are not yet implemented

        Use quotation marks and case sensitive role name in case it can't be mentioned
        """
        role_id = str(new_role.id)
        role_name = new_role.name
        guild_config = await self._get_guild_config(ctx.guild)
        guild_roles = await self._get_roles(ctx.guild)

        for role in guild_roles:
            if role[self.ROLE_ID] == role_id or role[self.LEVEL] == level:
                await ctx.send("**{0}** has already been assigned to level {1}!".format(role[self.ROLE_NAME],
                                                                                        role[self.LEVEL]))
                return

        if description is None:
            description = self.DEFAULT_DESC
        role_config = {
            self.ROLE_ID: role_id,
            self.ROLE_NAME: role_name,
            self.LEVEL: level,
            self.DESCRIPTION: description
        }

        guild_roles.append(role_config)
        guild_roles.sort(key=lambda k: k[self.LEVEL])

        await guild_config.set_raw(self.GUILD_ROLES, value=guild_roles)
        await ctx.send("{0} will be automatically earned at level {1}".format(new_role.name, level))

    @roles.command(name="remove", aliases=["rm"])
    async def roles_remove(self, ctx: Context, old_role: discord.Role):
        """
        Removes a previously set up automatic role

        Use quotation marks and case sensitive role name in case it can't be mentioned
        """
        role_id = str(old_role.id)
        guild_config = await self._get_guild_config(ctx.guild)
        guild_roles = await self._get_roles(ctx.guild)

        for role in guild_roles:
            if role_id == role[self.ROLE_ID]:
                guild_roles.remove(role)
                await guild_config.set_raw(self.GUILD_ROLES, value=guild_roles)
                await ctx.send("The role {} has been removed".format(role[self.ROLE_NAME]))
                return

        await ctx.send("Role not found in database")

    @guild.command(name="reset")
    async def guild_reset(self, ctx: Context):
        """
        Deletes ***all*** stored data of the guild.

        This doesn't ask for confirmation and deletes the whole player database
        """
        await self.config.clear_all_members(ctx.guild)
        await ctx.send("The guild's data has been wiped.")

    @guild.command(name="levelboard", aliases=["lb", "lvlboard"])
    async def admin_leaderboard(self, ctx: Context):
        """
        Display a leaderboard with the top 20 members of the guild

        this one contains a xpmsgs / msgs column for statistics. Msgs is the total amount of messages sent by a member
        and xpmsgs is the amount of those messages sent off cooldown and awarded xp. It helps when tuning the cooldown
        and xp settings.
        """
        guild_config = await self._get_guild_config(ctx.guild)
        leaderboard_max = await guild_config.get_raw(self.LEADERBOARD_MAX)
        guild_members = await self._get_members(ctx.guild)
        all_members = guild_members.values()
        if len(all_members) == 0:
            await ctx.send("No member activity registered.")
            return

        all_members = sorted(all_members, key=lambda u: (u[self.LEVEL], u[self.EXP]), reverse=True)
        top_member = discord.utils.find(lambda m: m.display_name == all_members[0][self.USERNAME], ctx.guild.members)
        member_list = ""

        embed = discord.Embed(title="{:-^75}".format("**Leaderboard**"))
        embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon_url)
        embed.set_thumbnail(url=top_member.avatar_url)
        embed.timestamp = datetime.utcnow()

        i = 0
        while i < leaderboard_max and i < len(all_members):
            last_digits = int(str(i)[-2:])
            suffix = None
            if last_digits not in [10, 11, 12]:
                if last_digits % 10 == 0:
                    suffix = "st"
                elif last_digits % 10 == 1:
                    suffix = "nd"
                elif last_digits % 10 == 2:
                    suffix = "rd"

            if suffix is None:
                suffix = "th"

            member = all_members[i]
            member_list += "{0}{1}. <@!{2}>\t**lvl**: {3}\t**msgs**: {4}/{5}\n".format(i + 1,
                                                                                       suffix,
                                                                                       member[self.MEMBER_ID],
                                                                                       member[self.LEVEL],
                                                                                       member[self.MESSAGE_WITH_XP],
                                                                                       member[self.MESSAGE_COUNT])
            i += 1

        try:
            embed.description = member_list
            await ctx.send(embed=embed)
        except discord.errors.HTTPException:
            await ctx.send("The list is too long. Please set a lower limit with `!la config set leaderboard_max`")

    @guild.command(name="channelignore", aliases=["chignore", "ci"])
    async def channel_ignore(self, ctx: Context, channel: discord.TextChannel = None):
        """
        Toggles a channel being ignored.

        channel: The channel you want to toggle. If none given, the current channel will be taken.
        """
        if channel is None:
            channel = ctx.channel

        channel_config = await self._get_channel_config(channel)

        if not await channel_config.get_raw(self.IGNORED_CHANNEL):
            await channel_config.set_raw(self.IGNORED_CHANNEL, value=True)
            await ctx.send("Channel {0.mention} will now be ignored.".format(channel))
        else:
            await channel_config.set_raw(self.IGNORED_CHANNEL, value=False)
            await ctx.send("Channel {0.mention} no longer being ignored".format(channel))

    @lvladmin.group()
    async def member(self, ctx: Context):
        """Member options"""
        pass

    @member.command(name="reset")
    async def member_reset(self, ctx: Context, member: discord.Member):
        """
        Deletes ***all*** stored data of a member.

        At the moment this command does not ask for confirmation, so use it carefully.

        member: Mention the member whose data you want to delete.
        """
        member_data = self.config.member(member)
        if await member_data.get_raw(self.MEMBER_ID) == self.DEFAULT_ID:
            await ctx.send("No data for {} has been found".format(member.mention))
            return

        await self.config.member(member).clear()
        await ctx.send("Data for {} has been deleted!".format(member.mention))

    @member.command(name="setlevel", aliases=["lvl", "level"])
    async def set_level(self, ctx: Context, member: discord.Member, level: int):
        """
        Changes the level of a member.

        member: Mention the member to which you want to change the level.

        level: The new member level.
        """

        guild_config = await self._get_guild_config(ctx.guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        await member_data.set_raw(self.LEVEL, value=level)
        await self._level_role(member_data=member_data, member=member)
        await self._level_goal(member_data=member_data)
        await ctx.send("Level of {0} has been changed to {1}".format(member.mention, level))

    @member.command(name="givexp", aliases=["xp"])
    async def give_xp(self, ctx: Context, member: discord.Member, xp: int, *, reason: str = None):
        """
        Gives xp to a member

        the new level and role will be calculated and assigned automatically

        member: mention the member to whom you want to award xp

        xp: the amount to xp you want to give them

        reason: if there's a particular reason why they deserve it
        """
        guild_config = await self._get_guild_config(ctx.guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        count = await self._give_xp(member_data=member_data, member=member, exp=xp)

        if reason is not None:
            reason = " for " + reason
        else:
            reason = ""
        await ctx.send("{0.mention} has received {1} xp{2}!".format(member, xp, reason))

        if count != 0:
            lvl = await member_data.get_raw(self.LEVEL)
            levels = "level" if count == 1 else "levels"
            await ctx.send("{0} {1} were earned by that. New shiny level: {2}".format(count, levels, lvl))

    @lvladmin.group(name="config")
    async def configuration(self, ctx: Context):
        """Configuration options"""
        pass

    @configuration.command(name="reset")
    async def config_reset(self, ctx: Context):
        """
        Reset **all** configuration to defaults

        this doesn't ask for confirmation and does not affect the player database
        """
        await self.config.guild(ctx.guild).clear()
        await ctx.send("Configuration defaults have been restored")

    @configuration.group(name="set")
    async def config_set(self, ctx: Context):
        """Change config values"""
        pass

    @config_set.command(name="goal")
    async def set_xp_goal_base(self, ctx: Context, value: int):
        """
        Base goal xp - default: 100

        This is the xp needed to reach level 1. Subsequent goals are measured with the current level's value.
        """
        await self.config.guild(ctx.guild).set_raw(self.XP_GOAL_BASE, value=value)
        await ctx.send("XP goal base value updated")

    @config_set.command(name="gainfactor", aliases=["gf"])
    async def set_xp_gain_factor(self, ctx: Context, value: float):
        """
        Increases the xp reward - default: 0.01

        XP gained += XP gained * lvl * this factor
        """
        await self.config.guild(ctx.guild).set_raw(self.XP_GAIN_FACTOR, value=value)
        await ctx.send("XP gain factor value updated")

    @config_set.command(name="minxp")
    async def set_xp_min(self, ctx: Context, value: int):
        """
        Minimum xp per message - default: 15

        Note that the real minimum is this * lvl * gain factor
        """
        await self.config.guild(ctx.guild).set_raw(self.XP_MIN, value=value)
        await ctx.send("Minimum xp per message value updated")

    @config_set.command(name="maxxp")
    async def set_xp_max(self, ctx: Context, value: int):
        """
        Maximum xp per message - default: 25

        Note that the real maximum is this * lvl * gain factor
        """
        await self.config.guild(ctx.guild).set_raw(self.XP_MAX, value=value)
        await ctx.send("Maximum xp per message value updated")

    @config_set.command(name="cooldown", aliases=["cd"])
    async def set_cooldown(self, ctx: Context, value: int):
        """
        Time between xp awards - default: 60

        In seconds
        """
        await self.config.guild(ctx.guild).set_raw(self.COOLDOWN, value=value)
        await ctx.send("XP cooldown value updated")

    @config_set.command(name="leaderboard_max", aliases=["lb_max"])
    async def set_leaderboard_max(self, ctx: Context, value: int):
        """
        Max amount of entries on the leaderboard - default: 20
        """
        await self.config.guild(ctx.guild).set_raw(self.LEADERBOARD_MAX, value=value)
        await ctx.send("Leaderboard's max entries updated")

    @config_set.command(name="mode", enabled=False, hidden=True)
    async def set_role_mode(self, ctx: Context, value: bool):
        """
        Not yet implemented

        Determines if old roles should be removed when a new one is gained by leveling up. Set False to keep them.

        ***this has not yet been implemented***
        """
        await self.config.guild(ctx.guild).set_raw(self.SINGLE_ROLE, value=value)
        await ctx.send("Role mode value updated")

    @config_set.command(name="announce")
    async def set_make_announcements(self, ctx: Context, value: bool):
        """
        Public announcements when leveling up - default: True

        If true, the bot will announce publicly when someone levels up
        """
        await self.config.guild(ctx.guild).set_raw(self.MAKE_ANNOUNCEMENTS, value=value)
        value = "enabled" if await self.config.guild(ctx.guild).make_announcements() else "disabled"
        await ctx.send("Public announcements are now {}".format(value))

    @config_set.command(name="active")
    async def set_active(self, ctx: Context, value: bool):
        """
        Register xp and monitor messages  - default: True

        If true, the bot will keep record of messages for xp and leveling purposes. Otherwise it will only listen to
        commands
        """
        await self.config.guild(ctx.guild).set_raw(self.ACTIVE, value=value)
        value = "enabled" if await self.config.guild(ctx.guild).active() else "disabled"
        await ctx.send("XP tracking is now {}".format(value))

    @config_set.command(name="lvlmessage")
    async def set_level_message(self, ctx: Context, *, message=None):
        """
        Message to display when leveling up

        This message will be displayed when someone levels up if announcements are enabled. To leave the message
        empty just set it to "none": `!la config set lvlmessage none`

        The possible variables are:
        {mention}: mentions the user
        {username}: displays the username without mentioning
        {level}: the level that was just reached
        {oldrole}: the role of the user before leveling up
        {newrole}: the role of the user after leveling up

        Note that {oldrole} and {newrole} may be the same if no role was awarded and will always default to
        "No level roles" if no roles have been set up for this guild. For finer control, use the `rolemessage`.

        Example: Congratulations {mention}, you're now level {level}.
        """
        if message is None:
            return

        if message == "none":
            message = ""
        await self.config.guild(ctx.guild).set_raw(self.LEVEL_UP_MESSAGE, value=message)
        if message == "":
            await ctx.send("No message will be sent when leveling up")
        else:
            await ctx.send("Level-up message updated")

    @config_set.command(name="rolemessage")
    async def set_role_message(self, ctx: Context, *, message=None):
        """
        Message to display when awarding roles

        This message will be displayed when someone gets a role through leveling up if announcements are enabled.
        The message will be appended to the `lvlmessage` if it's configured or displayed on its own otherwise.
        To leave the message empty just set it to "none": `!la config set rolemessage none`

        The possible variables are:
        {mention}: mentions the user
        {username}: displays the username without mentioning
        {level}: the level that was just reached
        {oldrole}: the role of the user before leveling up
        {newrole}: the role of the user after leveling up

        Note that {oldrole} and {newrole} will always default to "No level roles" if no roles have been set up for this
        guild.

        Example: Your days as {oldrole} are over. Your new role is {newrole}.
        """
        if message is None:
            return

        if message == "none":
            message = ""
        await self.config.guild(ctx.guild).set_raw(self.ROLE_CHANGE_MESSAGE, value=message)
        if message == "":
            await ctx.send("No message will be sent when earning a new role")
        else:
            await ctx.send("New role message updated")

    @configuration.group(name="get")
    async def config_get(self, ctx: Context):
        """Check current configuration"""
        pass

    @config_get.command(name="goal")
    async def get_xp_goal_base(self, ctx: Context):
        """
        Base goal xp

        This is the xp needed to reach level 1. Subsequent goals are measured with the current level's value.
        """
        value = await self.config.guild(ctx.guild).get_raw(self.XP_GOAL_BASE)
        await ctx.send("XP goal base: {}".format(value))

    @config_get.command(name="gainfactor", aliases=["gf"])
    async def get_xp_gain_factor(self, ctx: Context):
        """
        Increases the xp reward

        XP gained += XP gained * lvl * this factor
        """
        value = await self.config.guild(ctx.guild).get_raw(self.XP_GAIN_FACTOR)
        await ctx.send("XP gain factor: {}".format(value))

    @config_get.command(name="minxp")
    async def get_xp_min(self, ctx: Context):
        """
        Minimum xp per message

        Note that the real minimum is this * lvl * gain factor
        """
        value = await self.config.guild(ctx.guild).get_raw(self.XP_MIN)
        await ctx.send("Minimum xp per message: {}".format(value))

    @config_get.command(name="maxxp")
    async def get_xp_max(self, ctx: Context):
        """
        Maximum xp per message

        Note that the real maximum is this * lvl * gain factor
        """
        value = await self.config.guild(ctx.guild).get_raw(self.XP_MAX)
        await ctx.send("Maximum xp per message: {}".format(value))

    @config_get.command(name="cooldown", aliases=["cd"])
    async def get_cooldown(self, ctx: Context):
        """
        Time between xp awards

        In seconds
        """
        value = await self.config.guild(ctx.guild).get_raw(self.COOLDOWN)
        await ctx.send("XP cooldown: {}".format(value))

    @config_get.command(name="leaderboard_max", aliases=["lb_max"])
    async def get_leaderboard_max(self, ctx: Context):
        """
        Max amount of entries on the leaderboard
        """
        value = await self.config.guild(ctx.guild).get_raw(self.LEADERBOARD_MAX)
        await ctx.send("Leaderboard's max entries: {}".format(value))

    @config_get.command(name="mode", enabled=False, hidden=True)
    async def get_role_mode(self, ctx: Context):
        """
        Not yet implemented

        Determines if old roles should be removed when a new one is gained by leveling up. Set False to keep them.

        ***this has not yet been implemented***
        """
        value = "single" if await self.config.guild(ctx.guild).get_raw(self.SINGLE_ROLE) else "multi"
        await ctx.send("The role mode is set to: {}-role".format(value))

    @config_get.command(name="announce")
    async def get_make_announcements(self, ctx: Context):
        """
        Public announcements when leveling up

        If true, the bot will announce publicly when someone levels up
        """
        value = "enabled" if await self.config.guild(ctx.guild).get_raw(self.MAKE_ANNOUNCEMENTS) else "disabled"
        await ctx.send("Public announcements are {}".format(value))

    @config_get.command(name="active")
    async def get_active(self, ctx: Context):
        """
        Register xp and monitor messages

        If true, the bot will keep record of messages for xp and leveling purposes. Otherwise it will only listen to
        commands
        """
        value = "enabled" if await self.config.guild(ctx.guild).get_raw(self.ACTIVE) else "disabled"
        await ctx.send("XP tracking is {}".format(value))

    @config_get.command(name="lvlmessage")
    async def get_level_message(self, ctx: Context):
        """
        Message to display when leveling up

        This message will be displayed when someone levels up if announcements are enabled. To leave the message
        empty just set it to "none": `!la config set lvlmessage none`

        The possible variables are:
        {mention}: mentions the user
        {username}: displays the username without mentioning
        {level}: the level that was just reached
        {oldrole}: the role of the user before leveling up
        {newrole}: the role of the user after leveling up

        Note that {oldrole} and {newrole} may be the same if no role was awarded and will always default to
        "No level roles" if no roles have been set up for this guild. For finer control, use the `rolemessage`.

        Example: Congratulations {mention}, you're now level {level}.
        """
        message = await self.config.guild(ctx.guild).get_raw(self.LEVEL_UP_MESSAGE)
        await ctx.send(message)

    @config_get.command(name="rolemessage")
    async def get_role_message(self, ctx: Context):
        """
        Message to display when awarding roles

        This message will be displayed when someone gets a role through leveling up if announcements are enabled.
        The message will be appended to the `lvlmessage` if it's configured or displayed on its own otherwise.
        To leave the message empty just set it to "none": `!la config set rolemessage none`

        The possible variables are:
        {mention}: mentions the user
        {username}: displays the username without mentioning
        {level}: the level that was just reached
        {oldrole}: the role of the user before leveling up
        {newrole}: the role of the user after leveling up

        Note that {oldrole} and {newrole} will always default to "No level roles" if no roles have been set up for this
        guild.

        Example: Your days as {oldrole} are over. Your new role is {newrole}.
        """
        message = await self.config.guild(ctx.guild).get_raw(self.ROLE_CHANGE_MESSAGE)
        await ctx.send(message)
