import discord
from discord.ext import commands


class PublicRole:
    """A class to hold the Role-Keyword-Emoji configuration"""

    def __init__(self, role, keyword, emoji):
        self.role = role
        self.keyword = keyword
        self.emoji = emoji


class Autoroles:
    """This should allow users to auto assign roles by reacting to a message or using commands."""

    def __init__(self, bot):
        self.bot = bot
        self.emoji = None
        self.public_roles = []
        self.role_messages = {}

    @commands.command()
    async def liantest(self, ctx):
        await ctx.send("it works!")

    @commands.command()
    async def secondtest(self, ctx):
        await ctx.send("this works too")

    @commands.command(name="setemoji")
    async def set_emoji(self, ctx, emoji:discord.Emoji):
        await ctx.send("setting emoji to {}".format(emoji))
        self.emoji = emoji

    @commands.command(name="checkemoji")
    async def check_emoji(self, ctx):
        if self.emoji:
            await ctx.send("the current emoji is {}".format(self.emoji))
        else:
            await ctx.send("no emoji has been set")

    @commands.group()
    async def autorole(self, ctx):
        pass

    @autorole.command()
    async def add(self, ctx, role_name, keyword="", emoji:discord.Emoji=None):
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role:
            public_role = PublicRole(role, keyword, emoji)
            self.public_roles.append(public_role)
        else:
            await ctx.send("There is no such role")

    @autorole.command(name="makemessage")
    async def make_role_message(self, ctx, *roles):
        options = []
        for role in self.public_roles:
            if role.role.name in roles:
                options.append(role)
            else:
                await ctx.send("{} has not yet been registered".format(role))

        message = ""
        for option in options:
            if message:
                message += "\n"
            message += "react to {0.emoji} to get the role {0.role}".format(option)

        sent_message = await ctx.send(message)

        for option in options:
            await sent_message.add_reaction(option.emoji)
        self.role_messages[sent_message.id] = options

    async def on_reaction_add(self, reaction, user):
        if not user.bot:
            if reaction.message.id in self.role_messages:
                for role in self.role_messages[reaction.message.id]:
                    if role.emoji is reaction.emoji:
                        await user.add_roles(role.role)

    async def on_reaction_remove(self, reaction, user):
        if not user.bot:
            if reaction.message.id in self.role_messages:
                for role in self.role_messages[reaction.message.id]:
                    if role.emoji is reaction.emoji:
                        await user.remove_roles(role.role)
