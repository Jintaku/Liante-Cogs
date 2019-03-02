from redbot.core import commands, Config, checks
from redbot.core.bot import Red
from redbot.core.commands import Context
from random import randint
from datetime import datetime
import discord
import time
import logging

log = logging.getLogger("X")  # Thanks to Sinbad for the example code for logging
log.setLevel(logging.DEBUG)

console = logging.StreamHandler()

if logging.getLogger("red").isEnabledFor(logging.DEBUG):
    console.setLevel(logging.DEBUG)
else:
    console.setLevel(logging.INFO)
log.addHandler(console)

class X:

    async def on_message(self, message: discord.Message):

        # Checks if bots, dms, and red commands
        if not await self._is_valid_message(message):
            return

        # Gets configuration data and circumstancial data
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

        # Checks difference between last message and new message and the cooldown
        if curr_time - last_trigger <= cooldown:
            return

        old_role = await member_data.get_raw(self.ROLE_NAME)

        # Process XP then returns True or False to trigger next phase
        level_up = await self._process_xp(guild_config=guild_config,
                                          member_data=member_data,
                                          member=member)

        # Checks if level_up is True and if it's supposed to send announcements then does it
        if level_up and await self.config.guild(guild).make_announcements():

            # Debug log if it fails at any point
            log.debug("Send level up announcement!")

            # Get member data
            level = await member_data.get_raw(self.LEVEL)
            new_role = await member_data.get_raw(self.ROLE_NAME)

            # Message variables for custom messages
            message_variables = {
                "mention": member.mention,
                "username": member.display_name,
                "level": level,
                "oldrole": old_role,
                "newrole": new_role
            }

            # Builds message from custom message
            level_up_message = (await guild_config.get_raw(self.LEVEL_UP_MESSAGE)).format(**message_variables)

            # If old and new roles are different then send it
            if old_role != new_role:
                level_up_message += (await guild_config.get_raw(self.ROLE_CHANGE_MESSAGE)).format(**message_variables)

            # If custom message is not empty, send it
            if level_up_message != "":
                embed = discord.Embed()
                embed.set_author(name=member.display_name + " leveled up!")
                embed.description = level_up_message
                await channel.send(embed=embed)

    async def _is_valid_message(self, message: discord.Message): # Checks if message is a user message

        # If bot
        if message.author.bot:
            return False

        # If private
        if not message.guild:
            return False

        # If XP tracking is off
        guild_config = await self._get_guild_config(message.guild)
        if not await guild_config.get_raw(self.ACTIVE):
            return False

        # If channel is ignored
        channel_config = await self._get_channel_config(message.channel)
        if await channel_config.get_raw(self.IGNORED_CHANNEL):
            return False

        # If message starts by prefix (to ignore red command)
        prefixes = await Config.get_core_conf().prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return False

        # Else True
        return True

    async def on_member_update(self, before: discord.Member, after: discord.Member):

        # Handles nickname and username changes
        if before.display_name == after.display_name:
            return

        # Get data
        guild = before.guild
        guild_config = self.config.guild(guild)
        member_data = await self._get_member_data(guild_config=guild_config, member=before)

        # Set new username
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
        # Get circumstancial data
        guild_config = kwargs[self.GUILD_CONFIG]
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]

        # Get configuration data
        xp_min = await guild_config.get_raw(self.XP_MIN)
        xp_max = await guild_config.get_raw(self.XP_MAX)
        xp_gain_factor = await guild_config.get_raw(self.XP_GAIN_FACTOR)
        xp_gain = randint(xp_min, xp_max)
        message_xp = xp_gain + int(xp_gain_factor * (await member_data.get_raw(self.LEVEL)))
        curr_xp = await member_data.get_raw(self.EXP)

        # Get member data
        await member_data.set_raw(self.EXP, value=curr_xp + message_xp)
        await member_data.set_raw(self.LAST_TRIGGER, value=time.time())

        # Get message XP
        message_with_xp = await member_data.get_raw(self.MESSAGE_WITH_XP)
        await member_data.set_raw(self.MESSAGE_WITH_XP, value=message_with_xp + 1)

        # If XP is higher than goal, return True for level up message
        if await member_data.get_raw(self.EXP) >= await member_data.get_raw(self.GOAL):
            log.debug("Leveled up!")
            await self._level_up(member_data=member_data, member=member)
            return True

        # Return False to not have level up message
        return False

    async def _level_up(self, **kwargs):
        # Separated for admin commands implementation
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]

        # Calculates left over XP from leveling and set XP
        await self._level_xp(member_data=member_data)

        # Updates level and sets it
        await self._level_update(member_data=member_data, member=member)

        # Calculates goal and sets it
        await self._level_goal(member_data=member_data)

    async def _level_xp(self, **kwargs):
        # Get member data
        member_data = kwargs[self.MEMBER_DATA]

        # Calculates left over from leveling
        curr_xp = await member_data.get_raw(self.EXP)
        goal = await member_data.get_raw(self.GOAL)

        # Set new XP
        await member_data.set_raw(self.EXP, value=curr_xp - goal)

    async def _level_update(self, **kwargs):
        # Get member data
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]

        # Get current level
        curr_level = await member_data.get_raw(self.LEVEL)

        # Set new level
        await member_data.set_raw(self.LEVEL, value=curr_level + 1)
        await self._level_role(member_data=member_data, member=member)

    async def _level_role(self, **kwargs):
        """
        Checks if the member gets a role by leveling up
        """
        # Get data
        member_data = kwargs[self.MEMBER_DATA]
        member: discord.Member = kwargs[self.MEMBER]
        guild_config = await self._get_guild_config(member.guild)
        guild_roles = await guild_config.get_raw(self.GUILD_ROLES)

        # Set variable to append to
        autoroles = []

        # Get level and roles
        level = await member_data.get_raw(self.LEVEL)
        role_name = await member_data.get_raw(self.ROLE_NAME)

        # If no roles
        if len(guild_roles) == 0:
            return

        # Loop through guild_roles and append to autoroles
        for role in guild_roles:
            autoroles.append(discord.utils.find(lambda r: str(r.id) == role[self.ROLE_ID], member.guild.roles))

        # Create function for _assign_role
        async def _assign_role(index):

            # Set new role
            _new_role = autoroles[index]

            # Try to assign it
            try:
                # Loop between roles of member to check if they're in autoroles and remove them
                for _member_role in member.roles:

                    # If role is in autoroles, remove it
                    if _member_role in autoroles:
                        await member.remove_roles(_member_role, reason="level up")

                # Add new role
                await member.add_roles(_new_role, reason="level up")

                # Get new role
                _new_role = guild_roles[index][self.ROLE_NAME]

                # Set new role data
                await member_data.set_raw(self.ROLE_NAME, value=_new_role)

            # If it fails, log it
            except:
                log.debug("Permissions denied for role assignement")

        # If level is smaller than guild_roles level and role isn't default
        if level < guild_roles[0][self.LEVEL] and role_name != self.DEFAULT_ROLE:

            # Try to remove it
            try:

                # Loop between roles of member to check if they're in autoroles and remove them
                for member_role in member.roles:

                    # If role is in autoroles, remove it
                    if member_role in autoroles:
                        await member.remove_roles(member_role, reason="levels lost")

                # Set new role data
                await member_data.set_raw(self.ROLE_NAME, value=self.DEFAULT_ROLE)

            # If it fails, log it
            except:
                log.debug("Permissions denied for role removal")

        # Loop with pairs of old role and next_role
        for i, (role, next_role) in enumerate(zip(guild_roles, guild_roles[1:] + [None])):

            # Log loop number, current role, level and next role
            log.debug(f'Loop : {i} | Current role : {role[self.LEVEL]} | Level: {level} | Next role : {next_role and next_role[self.LEVEL]}')

            # If there is next_role, and level is greater than role and smaller than next_role, assign it
            if next_role and role[self.LEVEL] <= level < next_role[self.LEVEL] and role_name != role[self.ROLE_NAME]:
                await _assign_role(i)

            # If no next_role and level is greater than role and role is not current role name, assign it
            if not next_role and role[self.LEVEL] <= level and role_name != role[self.ROLE_NAME]:
                await _assign_role(i)


    async def _level_goal(self, **kwargs):
        # Get member data
        member_data = kwargs[self.MEMBER_DATA]

        # Get level data
        level = await member_data.get_raw(self.LEVEL)

        # Calculate goal
        goal = 5 * level ** 2 + 50 * level + 100

        # Set new goal
        await member_data.set_raw(self.GOAL, value=goal)

    async def _give_xp(self, **kwargs):

        # Get member and xp data
        member_data = kwargs[self.MEMBER_DATA]
        member = kwargs[self.MEMBER]
        xp = kwargs[self.EXP]

        # Calculate XP and set XP
        exp = await member_data.get_raw(self.EXP)
        exp += xp
        await member_data.set_raw(self.EXP, value=exp)

        # Set count to count
        count = 0

        # Get goal
        goal = await member_data.get_raw(self.GOAL)

        # While XP is greater than goal, count and level_up
        while exp >= goal:
            await self._level_up(member_data=member_data, member=member)
            count += 1
            exp = await member_data.get_raw(self.EXP)
            goal = await member_data.get_raw(self.GOAL)

        # Return count for message
        return count
