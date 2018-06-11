from redbot.core import commands
import motor.motor_asyncio
import bson


class Levels:

    def __init__(self, bot):
        self.bot = bot
        self.client = motor.motor_asyncio.AsyncIOMotorClient()
        self.levelsdb = self.client.levels

        self.xp_gain = 10
        self.xp_needed = 100

    async def on_message(self, message):
        if message.author.bot:
            return

        prefixes = await self.bot.db.prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return

        user = message.author
        guild = message.guild
        channel = message.channel
        username = user.display_name
        guildcoll = await self._get_guild_coll(guild)
        userdata = await self._get_user_data(guildcoll, user)

        await guildcoll.update_one({"userid": userdata["userid"]}, {"$set": {"exp": userdata["exp"] + self.xp_gain}})
        userdata = await self._get_user_data(guildcoll, user)
        if userdata["exp"] >= self.xp_needed:
            await self._level_up(guildcoll, userdata, channel)

    @commands.group(autohelp=True)
    async def levels(self, ctx):
        pass

    @levels.command()
    async def resetdb(self, ctx):
        guild = self.levelsdb[str(ctx.message.guild.id)]
        await guild.drop()

    @levels.command()
    async def exp(self, ctx):
        guild = ctx.guild
        guildid = str(guild.id)
        userid = ctx.author.id
        current_exp = (await self.levelsdb[guildid].find_one({"userid": userid}))["exp"]
        await ctx.send("Your current experience is: {}".format(current_exp))

    async def _get_user_data(self, guildcoll, user):
        userdata = await guildcoll.find_one({"userid": user.id})
        if userdata is None:
            userdata = {"userid": bson.Int64(user.id),
                        "username": user.display_name,
                        "exp": 0,
                        "level": 0,
                        "last_message": ""}
            await guildcoll.insert_one(userdata)
        return userdata

    async def _get_guild_coll(self, guild):
        guildcoll = self.levelsdb[str(guild.id)]
        if await guildcoll.find_one({"guildid": guild.id}) is None:
            guilddata = {"guildid": bson.Int64(guild.id),
                         "guildname": guild.name}
            await guildcoll.insert_one(guilddata)
        return guildcoll

    async def _level_up(self, guildcoll, userdata, channel):
        await guildcoll.update_one({"userid": userdata["userid"]}, {"$set": {"level": userdata["level"] + 1}})
        await guildcoll.update_one({"userid": userdata["userid"]}, {"$set": {"exp": userdata["exp"] - self.xp_needed}})
        await channel.send("level up!")
