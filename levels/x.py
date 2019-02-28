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
            log.debug("Send level up announcement!")
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
        message_xp = xp_gain + int(xp_gain_factor * (await member_data.get_raw(self.LEVEL)))
        curr_xp = await member_data.get_raw(self.EXP)

        await member_data.set_raw(self.EXP, value=curr_xp + message_xp)
        await member_data.set_raw(self.LAST_TRIGGER, value=time.time())

        message_with_xp = await member_data.get_raw(self.MESSAGE_WITH_XP)
        await member_data.set_raw(self.MESSAGE_WITH_XP, value=message_with_xp + 1)

        if await member_data.get_raw(self.EXP) >= await member_data.get_raw(self.GOAL):
            log.debug("Leveled up!")
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
            try:
                for _member_role in member.roles:
                    if _member_role in autoroles:
                        await member.remove_roles(_member_role, reason="level up")
                await member.add_roles(_new_role, reason="level up")
                _new_role = guild_roles[index][self.ROLE_NAME]
                await member_data.set_raw(self.ROLE_NAME, value=_new_role)
            except:
                log.debug("Permissions denied for role")

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
