from .tldr import Tldr


def setup(bot):
    bot.add_cog(Tldr(bot))
