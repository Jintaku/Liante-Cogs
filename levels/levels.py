from redbot.core import commands
from redbot.core import Config
import motor.motor_asyncio
import bson
import time
from random import randint


class Levels:

    XP_GOAL_BASE = "xp_goal_base"
    XP_GAIN_FACTOR = "xp_gain_factor"
    XP_MIN = "xp_min"
    XP_MAX = "xp_max"
    COOLDOWN = "cooldown"
    AUTOROLES = "autoroles"

    USER_ID = "user_id"
    USERNAME = "username"
    EXP = "exp"
    LEVEL = "level"
    GOAL = "goal"
    LAST_TRIGGER = "last_trigger"

    GUILD_ID = "guild_id"
    GUILD_NAME = "guild_name"

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, 4712468135468475)
        default_guild = {
            self.XP_GOAL_BASE: 100,
            self.XP_GAIN_FACTOR: 0.01,
            self.XP_MIN: 15,
            self.XP_MAX: 25,
            self.COOLDOWN: 60,
            self.AUTOROLES: {}
        }

        self.config.register_guild(**default_guild, force_registration=True)

        self.client = motor.motor_asyncio.AsyncIOMotorClient()
        self.levelsdb = self.client.levels

    async def on_message(self, message):
        if message.author.bot:
            return

        prefixes = await Config.get_core_conf().prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return

        user = message.author
        guild = message.guild
        channel = message.channel

        guildconf = self.config.guild(guild)
        guildcoll = await self._get_guild_coll(guild)
        userdata = await self._get_user_data(guildconf, guildcoll, user)

        last_trigger = userdata[self.LAST_TRIGGER]
        curr_time = time.time()
        cooldown = await guildconf.cooldown()

        if curr_time - last_trigger <= cooldown:
            return

        await self._process_xp(guildconf, channel, guildcoll, userdata)

    async def _get_guild_coll(self, guild):
        guildcoll = self.levelsdb[str(guild.id)]
        if await guildcoll.find_one({self.GUILD_ID: guild.id}) is None:
            guilddata = {self.GUILD_ID: bson.Int64(guild.id),
                         self.GUILD_NAME: guild.name}
            await guildcoll.insert_one(guilddata)
        return guildcoll

    async def _get_user_data(self, guildconf, guildcoll, user):
        userdata = await guildcoll.find_one({self.USER_ID: user.id})
        if userdata is None:
            userdata = {self.USER_ID: bson.Int64(user.id),
                        self.USERNAME: user.display_name,
                        self.EXP: 0,
                        self.LEVEL: 0,
                        self.GOAL: await guildconf.xp_goal_base(),
                        self.LAST_TRIGGER: time.time()}
            await guildcoll.insert_one(userdata)
        return userdata

    async def _process_xp(self, guildconf, channel, guildcoll, userdata):
        xp_min = await guildconf.xp_min()
        xp_max = await guildconf.xp_max()
        xp_gain_factor = await guildconf.xp_gain_factor()
        xp_gain = randint(xp_min, xp_max)
        message_xp = xp_gain + int(xp_gain * xp_gain_factor)

        userdata[self.EXP] = userdata[self.EXP] + message_xp
        await guildcoll.update_one({self.USER_ID: userdata[self.USER_ID]}, {"$set": {self.EXP: userdata[self.EXP]}})
        await guildcoll.update_one({self.USER_ID: userdata[self.USER_ID]}, {"$set": {self.LAST_TRIGGER: time.time()}})

        if userdata[self.EXP] >= userdata[self.GOAL]:
            await self._level_up(guildcoll, userdata, channel)

    async def _level_up(self, guildcoll, userdata, channel):
        userdata[self.EXP] = userdata[self.EXP] - userdata[self.GOAL]
        userdata[self.LEVEL] = userdata[self.LEVEL] + 1
        userdata[self.GOAL] = 5 * userdata[self.LEVEL]**2 + 50 * userdata[self.LEVEL] + 100

        await guildcoll.update_one({self.USER_ID: userdata[self.USER_ID]}, {"$set": {self.EXP: userdata[self.EXP]}})
        await guildcoll.update_one({self.USER_ID: userdata[self.USER_ID]}, {"$set": {self.LEVEL: userdata[self.LEVEL]}})
        await guildcoll.update_one({self.USER_ID: userdata[self.USER_ID]}, {"$set": {self.GOAL: userdata[self.GOAL]}})
        await channel.send("level up!")

    @commands.command()
    async def xp(self, ctx):
        guild = ctx.guild
        guildid = str(guild.id)
        userid = ctx.author.id
        userinfo = await self.levelsdb[guildid].find_one({self.USER_ID: userid})
        current_exp = userinfo[self.EXP]
        next_goal = userinfo[self.GOAL]
        await ctx.send("Your current experience is: {}. Next goal: {}. Needed: {}".format(current_exp,
                                                                                          next_goal,
                                                                                          next_goal - current_exp))

    @commands.command()
    async def lvl(self, ctx):
        guild = ctx.guild
        guildid = str(guild.id)
        userid = ctx.author.id
        current_lvl = (await self.levelsdb[guildid].find_one({self.USER_ID: userid}))[self.LEVEL]
        await ctx.send("Your current level is: {}".format(current_lvl))

    @commands.group(aliases=["lc"], autohelp=True)
    async def lvlsconfig(self, ctx):
        pass

    @lvlsconfig.command()
    async def resetdb(self, ctx):
        guild = self.levelsdb[str(ctx.message.guild.id)]
        await guild.drop()

    @lvlsconfig.group(autohelp=True)
    async def set(self, ctx):
        pass

    @set.command(name="goal")
    async def set_xp_goal_base(self, ctx, new_value: int):
        await self.config.guild(ctx.guild).xp_goal_base.set(new_value)
        await ctx.send("XP goal base value updated")

    @set.command(name="gainfactor", aliases=["gf"])
    async def set_xp_gain_factor(self, ctx, new_value: float):
        await self.config.guild(ctx.guild).xp_gain_factor.set(new_value)
        await ctx.send("XP gain factor value updated")

    @set.command(name="minxp")
    async def set_xp_min(self, ctx, new_value: int):
        await self.config.guild(ctx.guild).xp_min.set(new_value)
        await ctx.send("Minimum xp per message value updated")

    @set.command(name="maxxp")
    async def set_xp_max(self, ctx, new_value: int):
        await self.config.guild(ctx.guild).xp_max.set(new_value)
        await ctx.send("Maximum xp per message value updated")

    @set.command(name="cooldown")
    async def set_cooldown(self, ctx, new_value: int):
        await self.config.guild(ctx.guild).cooldown.set(new_value)
        await ctx.send("XP cooldown value updated")

    @lvlsconfig.group(autohelp=True)
    async def get(self, ctx):
        pass

    @get.command(name="goal")
    async def get_xp_goal_base(self, ctx):
        value = await self.config.guild(ctx.guild).xp_goal_base()
        await ctx.send("XP goal base: {}".format(value))

    @get.command(name="gainfactor", aliases=["gf"])
    async def get_xp_gain_factor(self, ctx):
        value = await self.config.guild(ctx.guild).xp_gain_factor()
        await ctx.send("XP gain factor: {}".format(value))

    @get.command(name="minxp")
    async def get_xp_min(self, ctx):
        value = await self.config.guild(ctx.guild).xp_min()
        await ctx.send("Minimum xp per message: {}".format(value))

    @get.command(name="maxxp")
    async def get_xp_max(self, ctx):
        value = await self.config.guild(ctx.guild).xp_max()
        await ctx.send("Maximum xp per message: {}".format(value))

    @get.command(name="cooldown")
    async def get_cooldown(self, ctx):
        value = await self.config.guild(ctx.guild).cooldown()
        await ctx.send("XP cooldown: {}".format(value))
