from redbot.core import commands
import motor.motor_asyncio


class Levels:

    def __init__(self, bot):
        self.bot = bot
        self.client = motor.motor_asyncio.AsyncIOMotorClient()

        self.levelsdb = self.client.levels

    async def on_message(self, message):
        if message.author.bot:
            return

        prefixes = await self.bot.db.prefix()
        for prefix in prefixes:
            if message.content.startswith(prefix):
                return

        channel = message.channel
        guild = self.levelsdb[message.guild.name]
        username = message.author.display_name

        if await guild.find({"username": username}).count() == 0:
            document = {"username": username,
                        "level": 0,
                        "last_message": message.content}
            await guild.insert_one(document)
        else:
            await guild.update_one({"username": username}, {"$set": {"last_message": message.content}})
        await channel.send("success!")

    @commands.group()
    async def levels(self, ctx):
        if ctx.invoked_subcommand is None:
            ctx.send("Subcommand needed")

    @levels.command()
    async def resetdb(self, ctx):
        guild = self.levelsdb[ctx.message.guild.name]
        guild.drop()
