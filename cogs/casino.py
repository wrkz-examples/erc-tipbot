import discord
from discord.ext import commands

import utils
from cogs.Minigames.coinflip import Coinflip


class Casino(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(usage="coinflip <member> [bet]", aliases=['cf'], description="Bet against someone in a classic 50/50.")
    async def coinflip(self, ctx, member: utils.MemberLookupConverter, bet: int):
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass

        if ctx.author.id in self.bot.players_in_game:
            return await ctx.send("You're already in a game! "
                                  "Finish that game or wait for it to expire to start a new one.", delete_after=10)
        if member.id in self.bot.players_in_game:
            return await ctx.send(f"{member.mention} is in a game. Wait for them to finish their game before starting a new one!",
                                  delete_after=10)

        if member.bot or member == ctx.author:
            raise commands.BadArgument('Cannot play a game against that member.')
        if bet > 0:
            balance1 = 0  # TODO: Get player1's MOON balance - old code: await sql.get_casino_player(self.bot.pool, ctx.author.id)
            if balance1 < bet:
                return await ctx.send(f"You don't have enough credits! Available balance: {balance1}")

            balance2 = 0  # TODO: Get player2's MOON balance - old code:await sql.get_casino_player(self.bot.pool, member.id)
            if balance2 < bet:
                return await ctx.send(f"{member.display_name} doesn't have enough credits to play.")

            game = Coinflip(ctx, self.bot, bet, balance1, member)
            self.bot.players_in_game.append(ctx.author.id)
            await game.play()

            if member.id in self.bot.players_in_game:
                self.bot.players_in_game.remove(member.id)
            self.bot.players_in_game.remove(ctx.author.id)
        else:
            await ctx.send("You have to place a bet higher than 0!")


def setup(bot):
    bot.add_cog(Casino(bot))
