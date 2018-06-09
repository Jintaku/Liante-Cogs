from .autoroles import Autoroles


def setup(bot):
    bot.add_cog(Autoroles(bot))
