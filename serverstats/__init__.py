from .serverstats import ServerStats


def setup(bot):
    bot.addCog(ServerStats())
