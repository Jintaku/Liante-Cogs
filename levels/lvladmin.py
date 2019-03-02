from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context
from random import randint
from datetime import datetime
import discord
import time
import logging

log = logging.getLogger("lvladmin")  # Thanks to Sinbad for the example code for logging
log.setLevel(logging.DEBUG)

console = logging.StreamHandler()

if logging.getLogger("red").isEnabledFor(logging.DEBUG):
    console.setLevel(logging.DEBUG)
else:
    console.setLevel(logging.INFO)
log.addHandler(console)

class Lvladmin:

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

        # Get roles data
        guild_roles = await self._get_roles(ctx.guild)

        # Start building embed
        embed = discord.Embed(title="Configured Roles:")

        # Loop create fields for roles
        for role in guild_roles:
            embed.add_field(name="Level {0} - {1}".format(role[self.LEVEL], role[self.ROLE_NAME]),
                            value="{}".format(role[self.DESCRIPTION]), inline=False)

        # If no fields aka no roles, say it
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
        # Set name and ID based on positional data
        role_id = str(new_role.id)
        role_name = new_role.name

        # Get role data
        guild_config = await self._get_guild_config(ctx.guild)
        guild_roles = await self._get_roles(ctx.guild)

        # Loop roles to find if any already exist
        for role in guild_roles:
            if role[self.ROLE_ID] == role_id or role[self.LEVEL] == level:
                await ctx.send("**{0}** has already been assigned to level {1}!".format(role[self.ROLE_NAME], role[self.LEVEL]))
                return

        # If description is not specified, default description
        if description is None:
            description = self.DEFAULT_DESC

        # Set up new role
        role_config = {
            self.ROLE_ID: role_id,
            self.ROLE_NAME: role_name,
            self.LEVEL: level,
            self.DESCRIPTION: description
        }

        # Append it and sort it
        guild_roles.append(role_config)
        guild_roles.sort(key=lambda k: k[self.LEVEL])

        # Set it and send message to notify of success
        await guild_config.set_raw(self.GUILD_ROLES, value=guild_roles)
        await ctx.send("{0} will be automatically earned at level {1}".format(new_role.name, level))

    @roles.command(name="remove", aliases=["rm"])
    async def roles_remove(self, ctx: Context, old_role: discord.Role):
        """
        Removes a previously set up automatic role

        Use quotation marks and case sensitive role name in case it can't be mentioned
        """
        # Get ID from positional data
        role_id = str(old_role.id)

        # Get configuration and role data
        guild_config = await self._get_guild_config(ctx.guild)
        guild_roles = await self._get_roles(ctx.guild)

        # Loop through roles and checks if role is in them then removes it
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
        # Clear every user in guild
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
        # Get configuration and member data
        guild_config = await self._get_guild_config(ctx.guild)
        leaderboard_max = await guild_config.get_raw(self.LEADERBOARD_MAX)
        guild_members = await self._get_members(ctx.guild)
        all_members = guild_members.values()

        # Checks if there is any members
        if len(all_members) == 0:
            await ctx.send("No member activity registered.")
            return

        # Sorts members in order with level and XP
        all_members = sorted(all_members, key=lambda u: (u[self.LEVEL], u[self.EXP]), reverse=True)
        top_member = discord.utils.find(lambda m: m.display_name == all_members[0][self.USERNAME], ctx.guild.members)
        member_list = ""

        # Build Embed
        embed = discord.Embed()
        embed.set_author(name=ctx.guild.name + " Leaderboard")
        embed.set_thumbnail(url=ctx.guild.icon_url)

        # Loop to create member_list
        for i in range(0, len(all_members[:leaderboard_max])):
            member = all_members[i]
            member_list += "\n#{number} <@!{ID}> - Level : {LVL} - Messages : {XP}/{COUNT}".format(number=i+1, ID=member[self.MEMBER_ID], LVL=member[self.LEVEL], XP=member[self.MESSAGE_WITH_XP], COUNT=member[self.MESSAGE_COUNT])

        # Try to set and send the embed and tells user if it excepts
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

        # If channel is not specified, use current channel
        if channel is None:
            channel = ctx.channel

        # Get channel config
        channel_config = await self._get_channel_config(channel)

        # Checks config if already ignored or not and reacts based on that
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
        # Get member data
        member_data = self.config.member(member)

        # Checks if ID is 000000000 and says it has no data if so
        if await member_data.get_raw(self.MEMBER_ID) == self.DEFAULT_ID:
            await ctx.send("No data for {} has been found".format(member.mention))
            return

        # Else it deletes the data
        await self.config.member(member).clear()
        await ctx.send("Data for {} has been deleted!".format(member.mention))

    @member.command(name="setlevel", aliases=["lvl", "level"])
    async def set_level(self, ctx: Context, member: discord.Member, level: int):
        """
        Changes the level of a member. (Sets their XP to 0 to avoid issues)

        member: Mention the member to which you want to change the level.

        level: The new member level.
        """

        # Get guild data and member data
        guild_config = await self._get_guild_config(ctx.guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        # Sets level and XP
        await member_data.set_raw(self.LEVEL, value=level)
        await member_data.set_raw(self.EXP, value=0)

        # Checks role and goal then send message
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

        # Get guild config and member data
        guild_config = await self._get_guild_config(ctx.guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=member)

        # Give XP and set count which is level
        count = await self._give_xp(member_data=member_data, member=member, exp=xp)

        # If reason is set, add for to reason
        if reason is not None:
            reason = " for " + reason

        # Else make it empty
        else:
            reason = ""

        # Send message
        await ctx.send("{0.mention} has received {1} xp{2}!".format(member, xp, reason))

        # If count isn't 0, send message to tell user they leveled up
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
        # Clear config defaults
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
        # Set XP Goal base
        await self.config.guild(ctx.guild).set_raw(self.XP_GOAL_BASE, value=value)
        await ctx.send("XP goal base value updated")

    @config_set.command(name="gainfactor", aliases=["gf"])
    async def set_xp_gain_factor(self, ctx: Context, value: float):
        """
        Increases the xp reward - default: 0.1

        XP gained += lvl * this factor
        """
        # Set XP Gain factor
        await self.config.guild(ctx.guild).set_raw(self.XP_GAIN_FACTOR, value=value)
        await ctx.send("XP gain factor value updated")

    @config_set.command(name="minxp")
    async def set_xp_min(self, ctx: Context, value: int):
        """
        Minimum xp per message - default: 15

        Note that the real minimum is this * lvl * gain factor
        """
        # Set XP min
        await self.config.guild(ctx.guild).set_raw(self.XP_MIN, value=value)
        await ctx.send("Minimum xp per message value updated")

    @config_set.command(name="maxxp")
    async def set_xp_max(self, ctx: Context, value: int):
        """
        Maximum xp per message - default: 25

        Note that the real maximum is this * lvl * gain factor
        """
        # Set XP max
        await self.config.guild(ctx.guild).set_raw(self.XP_MAX, value=value)
        await ctx.send("Maximum xp per message value updated")

    @config_set.command(name="cooldown", aliases=["cd"])
    async def set_cooldown(self, ctx: Context, value: int):
        """
        Time between xp awards - default: 60

        In seconds
        """
        # Set XP cooldown
        await self.config.guild(ctx.guild).set_raw(self.COOLDOWN, value=value)
        await ctx.send("XP cooldown value updated")

    @config_set.command(name="leaderboard_max", aliases=["lb_max"])
    async def set_leaderboard_max(self, ctx: Context, value: int):
        """
        Max amount of entries on the leaderboard - default: 20
        """
        # Set Leaderboard entries max
        await self.config.guild(ctx.guild).set_raw(self.LEADERBOARD_MAX, value=value)
        await ctx.send("Leaderboard's max entries updated")

    @config_set.command(name="mode", enabled=False, hidden=True)
    async def set_role_mode(self, ctx: Context, value: bool):
        """
        Not yet implemented

        Determines if old roles should be removed when a new one is gained by leveling up. Set False to keep them.

        ***this has not yet been implemented***
        """
        # TODO : Set single role configuration
        await self.config.guild(ctx.guild).set_raw(self.SINGLE_ROLE, value=value)
        await ctx.send("Role mode value updated")

    @config_set.command(name="announce")
    async def set_make_announcements(self, ctx: Context, value: bool):
        """
        Public announcements when leveling up - default: True

        If true, the bot will announce publicly when someone levels up
        """
        # Set announcement status toggle
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
        # Set active or not toggle
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

        # If message is none, return
        if message is None:
            return

        # If message is "none", make it empty
        if message == "none":
            message = ""

        # Set message
        await self.config.guild(ctx.guild).set_raw(self.LEVEL_UP_MESSAGE, value=message)

        # If empty, tell no message will be sent
        if message == "":
            await ctx.send("No message will be sent when leveling up")

        # Else tell it was updated
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

        # If message is none, return
        if message is None:
            return

        # If message is "none", make it empty
        if message == "none":
            message = ""

        # Set message
        await self.config.guild(ctx.guild).set_raw(self.ROLE_CHANGE_MESSAGE, value=message)

        # If empty, tell no message will be sent
        if message == "":
            await ctx.send("No message will be sent when earning a new role")

        # Else tell it was updated
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
        # Get XP goal base
        value = await self.config.guild(ctx.guild).get_raw(self.XP_GOAL_BASE)
        await ctx.send("XP goal base: {}".format(value))

    @config_get.command(name="gainfactor", aliases=["gf"])
    async def get_xp_gain_factor(self, ctx: Context):
        """
        Increases the xp reward

        XP gained += lvl * this factor
        """
        # Get XP gain reward
        value = await self.config.guild(ctx.guild).get_raw(self.XP_GAIN_FACTOR)
        await ctx.send("XP gain factor: {}".format(value))

    @config_get.command(name="minxp")
    async def get_xp_min(self, ctx: Context):
        """
        Minimum xp per message

        Note that the real minimum is this * lvl * gain factor
        """
        # Get XP min
        value = await self.config.guild(ctx.guild).get_raw(self.XP_MIN)
        await ctx.send("Minimum xp per message: {}".format(value))

    @config_get.command(name="maxxp")
    async def get_xp_max(self, ctx: Context):
        """
        Maximum xp per message

        Note that the real maximum is this * lvl * gain factor
        """
        # Get XP max
        value = await self.config.guild(ctx.guild).get_raw(self.XP_MAX)
        await ctx.send("Maximum xp per message: {}".format(value))

    @config_get.command(name="cooldown", aliases=["cd"])
    async def get_cooldown(self, ctx: Context):
        """
        Time between xp awards

        In seconds
        """
        # Get cooldown
        value = await self.config.guild(ctx.guild).get_raw(self.COOLDOWN)
        await ctx.send("XP cooldown: {}".format(value))

    @config_get.command(name="leaderboard_max", aliases=["lb_max"])
    async def get_leaderboard_max(self, ctx: Context):
        """
        Max amount of entries on the leaderboard
        """
        # Get leaderboard max
        value = await self.config.guild(ctx.guild).get_raw(self.LEADERBOARD_MAX)
        await ctx.send("Leaderboard's max entries: {}".format(value))

    @config_get.command(name="mode", enabled=False, hidden=True)
    async def get_role_mode(self, ctx: Context):
        """
        Not yet implemented

        Determines if old roles should be removed when a new one is gained by leveling up. Set False to keep them.

        ***this has not yet been implemented***
        """
        # TODO : Get single role configuration
        value = "single" if await self.config.guild(ctx.guild).get_raw(self.SINGLE_ROLE) else "multi"
        await ctx.send("The role mode is set to: {}-role".format(value))

    @config_get.command(name="announce")
    async def get_make_announcements(self, ctx: Context):
        """
        Public announcements when leveling up

        If true, the bot will announce publicly when someone levels up
        """
        # Get announcements status
        value = "enabled" if await self.config.guild(ctx.guild).get_raw(self.MAKE_ANNOUNCEMENTS) else "disabled"
        await ctx.send("Public announcements are {}".format(value))

    @config_get.command(name="active")
    async def get_active(self, ctx: Context):
        """
        Register xp and monitor messages

        If true, the bot will keep record of messages for xp and leveling purposes. Otherwise it will only listen to
        commands
        """
        # Get active or not status
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
        # Get level up message
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
        # Get role message
        message = await self.config.guild(ctx.guild).get_raw(self.ROLE_CHANGE_MESSAGE)
        await ctx.send(message)
