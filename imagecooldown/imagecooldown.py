from redbot.core import commands, Config, checks
from redbot.core.commands import Context
import discord
import time

try:
    from redbot.core.commands import Cog
except ImportError:
    Cog = object


class ImageCooldown(Cog):
    """

    """

    ROLE_WHITELIST = "role_whitelist"
    MEMBER_WHITELIST = "member_whitelist"
    MEMBER_LAST_ATTACHMENT = "member_last_attachment"
    CHANNEL_WHITELIST = "channel_whitelist"
    COOLDOWN = "cooldown"
    ATTACHMENT_LIMIT = "attachment_limit"
    ACTIVE = "active"

    def __init__(self):
        self.config = Config.get_conf(self, 4712468135468477)
        default_guild = {
            self.ROLE_WHITELIST: [],
            self.MEMBER_WHITELIST: [],
            self.CHANNEL_WHITELIST: [],
            self.MEMBER_LAST_ATTACHMENT: {},
            self.COOLDOWN: 30,
            self.ATTACHMENT_LIMIT: 5,
            self.ACTIVE: True
        }

        self.config.register_guild(**default_guild, force_registration=True)

    async def on_message(self, message: discord.Message):
        if message.guild is None:
            return

        author = message.author
        if author.bot:
            return

        guild = message.guild
        guild_config = self.config.guild(guild)
        if len(message.attachments) == 0 or not (await guild_config.get_raw(self.ACTIVE)):
            return

        channel = message.channel
        channel_whitelist = await guild_config.get_raw(self.CHANNEL_WHITELIST)
        if str(channel.id) not in channel_whitelist:
            return

        author_roles = author.roles
        author_id = str(author.id)
        role_whitelist = await guild_config.get_raw(self.ROLE_WHITELIST)
        member_whitelist = await guild_config.get_raw(self.MEMBER_WHITELIST)

        if author_id in member_whitelist:
            return

        for role in author_roles:
            if str(role.id) in role_whitelist:
                return

        curr_time = time.time()
        cooldown = await guild_config.get_raw(self.COOLDOWN)
        last_attachment = 0
        try:
            last_attachment = (await guild_config.get_raw(self.MEMBER_LAST_ATTACHMENT))[str(author.id)]
        except KeyError:
            await guild_config.set_raw(self.MEMBER_LAST_ATTACHMENT, author_id, value=curr_time)

        await message.channel.send(last_attachment)
        await message.channel.send(curr_time)
        await message.channel.send(curr_time - last_attachment)

        on_cooldown = curr_time - last_attachment <= cooldown
        too_long = len(message.attachments) > (await guild_config.get_raw(self.ATTACHMENT_LIMIT))

        await message.channel.send(on_cooldown)
        await message.channel.send(too_long)

        if on_cooldown or too_long:
            await message.delete()
            await message.channel.send("image spam")
        else:
            await guild_config.set_raw(self.MEMBER_LAST_ATTACHMENT, author_id, value=curr_time)

    @checks.admin()
    @commands.guild_only()
    @commands.group(name="image_cooldown", aliases=["ic"])
    async def image_cooldown(self, ctx: Context):
        pass

    @image_cooldown.command(name="toggle")
    async def toggle(self, ctx: Context):
        guild = ctx.guild
        guild_config = self.config.guild(guild)
        value = await guild_config.get_raw(self.ACTIVE)
        value = not value
        value_str = "enabled" if value else "disabled"
        await guild_config.set_raw(self.ACTIVE, value=value)
        await ctx.send("Image Cooldown is now {} for this server".format(value_str))

    @image_cooldown.command(name="cooldown", aliases=["cd"])
    async def cooldown(self, ctx: Context, cooldown: int):
        guild_config = self.config.guild(ctx.guild)
        await guild_config.set_raw(self.COOLDOWN, value=cooldown)
        await ctx.send("Cooldown set to {}".format(cooldown))

    @image_cooldown.group(name="whitelist", aliases=["wl"])
    async def whitelist(self, ctx: Context):
        pass

    @whitelist.group(name="add")
    async def whitelist_add(self, ctx: Context):
        pass

    @whitelist_add.command(name="member")
    async def whitelist_add_member(self, ctx: Context, member: discord.Member):
        member_id = str(member.id)
        guild_config = self.config.guild(ctx.guild)
        member_whitelist = await guild_config.get_raw(self.MEMBER_WHITELIST)

        if member_id not in member_whitelist:
            member_whitelist.append(member_id)
            await guild_config.set_raw(self.MEMBER_WHITELIST, value=member_whitelist)
            await ctx.send("{0.display_name}#{0.discriminator} was added to the whitelist.".format(member))

    @whitelist_add.command(name="role")
    async def whitelist_add_role(self, ctx: Context, role: discord.Role):
        role_id = str(role.id)
        guild_config = self.config.guild(ctx.guild)
        role_whitelist = await guild_config.get_raw(self.ROLE_WHITELIST)

        if role_id not in role_whitelist:
            role_whitelist.append(role_id)
            await guild_config.set_raw(self.ROLE_WHITELIST, value=role_whitelist)
            await ctx.send("{0.name} was added to the whitelist.".format(role))

    @whitelist_add.command(name="channel")
    async def whitelist_add_member(self, ctx: Context, channel: discord.TextChannel):
        channel_id = str(channel.id)
        guild_config = self.config.guild(ctx.guild)
        channel_whitelist = await guild_config.get_raw(self.CHANNEL_WHITELIST)

        if channel_id not in channel_whitelist:
            channel_whitelist.append(channel_id)
            await guild_config.set_raw(self.CHANNEL_WHITELIST, value=channel_whitelist)
            await ctx.send("{0.name} was added to the whitelist.".format(channel))

    @whitelist.group(name="remove")
    async def whitelist_remove(self, ctx: Context):
        pass

    @whitelist_remove.command(name="member")
    async def whitelist_remove_member(self, ctx: Context, member: discord.Member):
        member_id = member.id
        guild_config = self.config.guild(ctx.guild)
        member_whitelist = await guild_config.get_raw(self.MEMBER_WHITELIST)

        try:
            member_whitelist.remove(member_id)
            await guild_config.set_raw(self.MEMBER_WHITELIST, value=member_whitelist)
            await ctx.send("{0.display_name}#{0.discriminator} was removed from the whitelist".format(member))
        except ValueError:
            await ctx.send("{0.display_name}#{0.discriminator} was not found in the whitelist".format(member))

    @whitelist_remove.command(name="role")
    async def whitelist_remove_role(self, ctx: Context, role: discord.Role):
        role_id = role.id
        guild_config = self.config.guild(ctx.guild)
        role_whitelist = await guild_config.get_raw(self.ROLE_WHITELIST)

        try:
            role_whitelist.remove(role_id)
            await guild_config.set_raw(self.ROLE_WHITELIST, value=role_whitelist)
            await ctx.send("{0.name} was removed from the whitelist".format(role))
        except ValueError:
            await ctx.send("{0.name} was not found in the whitelist".format(role))

    @whitelist_remove.command(name="channel")
    async def whitelist_remove_channel(self, ctx: Context, channel: discord.TextChannel):
        channel_id = channel.id
        guild_config = self.config.guild(ctx.guild)
        channel_whitelist = await guild_config.get_raw(self.CHANNEL_WHITELIST)

        try:
            channel_whitelist.remove(channel_id)
            await guild_config.set_raw(self.CHANNEL_WHITELIST, value=channel_whitelist)
            await ctx.send("{0.name} was removed from the whitelist".format(channel))
        except ValueError:
            await ctx.send("{0.name} was not found in the whitelist".format(channel))
