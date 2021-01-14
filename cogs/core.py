import sys
import traceback
from datetime import datetime, timedelta

import discord
from discord.ext import commands

from Bot import logchanbot
from utils import EmbedPaginator


class Core(commands.Cog):
    """Houses core commands & listeners for the bot"""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(usage="uptime", description="Tells how long the bot has been running.")
    async def uptime(self, ctx):
        uptime_seconds = round((datetime.now() - self.bot.start_time).total_seconds())
        await ctx.send(f"Current Uptime: {'{:0>8}'.format(str(timedelta(seconds=uptime_seconds)))}")

    @commands.command(usage="rolecount [role]", description="Counts the number of people who have a role, If no role is specified it counts everyone.")
    async def rolecount(self, ctx, *, role: discord.Role = None):
        if not role:
            name = " the server"
            nmembers = ctx.guild.member_count
            color = discord.Color.gold()
        else:
            name = role.name
            nmembers = len(role.members)
            color = role.color
        embed = discord.Embed(color=color).add_field(name=f"Members in {name}", value=f"{nmembers:,}")
        await ctx.send(embed=embed)

    @commands.bot_has_permissions(add_reactions=True)
    @commands.command(usage="help [command/cog]",
                      aliases=["h"], description="Shows the help menu or information for a specific command or cog when specified.")
    async def help(self, ctx, *, opt: str = None):
        if opt:
            cog = self.bot.get_cog(opt.capitalize())
            if not cog:
                command = self.bot.get_command(opt.lower())
                if not command:
                    return await ctx.send(
                        embed=discord.Embed(description=f"That command/cog does not exist. Use `{ctx.prefix}help` to see all the commands.",
                                            color=discord.Color.red(), ))

                embed = discord.Embed(title=command.name, description=command.description, colour=discord.Color.blue())
                usage = "\n".join([ctx.prefix + x.strip() for x in command.usage.split("\n")])
                embed.add_field(name="Usage", value=f"```{usage}```", inline=False)
                if len(command.aliases) > 1:
                    embed.add_field(name="Aliases", value=f"`{'`, `'.join(command.aliases)}`")
                elif len(command.aliases) > 0:
                    embed.add_field(name="Alias", value=f"`{command.aliases[0]}`")
                return await ctx.send(embed=embed)
            cog_commands = cog.get_commands()
            embed = discord.Embed(title=opt.capitalize(), description=f"{cog.description}\n\n`<>` Indicates a required argument.\n"
                                                                      "`[]` Indicates an optional argument.\n", color=discord.Color.blue(), )
            embed.set_author(name=f"{self.bot.user.name} Help Menu", icon_url=self.bot.user.avatar_url)
            embed.set_thumbnail(url=self.bot.user.avatar_url)
            embed.set_footer(
                text=f"Use {ctx.prefix}help <command> for more information on a command.")
            for cmd in cog_commands:
                if cmd.hidden is False:
                    name = ctx.prefix + cmd.usage
                    if len(cmd.aliases) > 1:
                        name += f" | Aliases – `{'`, `'.join([ctx.prefix + a for a in cmd.aliases])}`"
                    elif len(cmd.aliases) > 0:
                        name += f" | Alias – {ctx.prefix + cmd.aliases[0]}"
                    embed.add_field(name=name, value=cmd.description, inline=False)
            return await ctx.send(embed=embed)

        all_pages = []
        page = discord.Embed(title=f"{self.bot.user.name} Help Menu",
                             description="Thank you for using MoonTipBot!",
                             color=discord.Color.blue(), )
        page.add_field(name="About the bot",
                       value="This bot was built to enable convenient tipping of MOONS within discord!", inline=False, )
        page.add_field(name="Getting Started",
                       value=f"For a full list of commands, see `{ctx.prefix}help`. Browse through the various commands to get comfortable with using "
                             f"them, and do `{ctx.prefix}help <command>` for more info on specific commands!", inline=False, )
        page.set_thumbnail(url=self.bot.user.avatar_url)
        page.set_footer(text="Use the reactions to flip pages.")
        all_pages.append(page)
        for _, cog_name in enumerate(sorted(self.bot.cogs)):
            if cog_name in ["Owner", "Admin"]:
                continue
            cog = self.bot.get_cog(cog_name)
            cog_commands = cog.get_commands()
            if len(cog_commands) == 0:
                continue
            page = discord.Embed(title=cog_name, description=f"{cog.description}\n\n`<>` Indicates a required argument.\n"
                                                             "`[]` Indicates an optional argument.\n",
                                 color=discord.Color.blue(), )
            page.set_author(name=f"{self.bot.user.name} Help Menu", icon_url=self.bot.user.avatar_url)
            page.set_thumbnail(url=self.bot.user.avatar_url)
            page.set_footer(text=f"Use the reactions to flip pages | Use {ctx.prefix}help <command> for more information on a command.")
            for cmd in cog_commands:
                if cmd.hidden is False:
                    name = ctx.prefix + cmd.usage
                    if len(cmd.aliases) > 1:
                        name += f" | Aliases – `{'`, `'.join([ctx.prefix + a for a in cmd.aliases])}`"
                    elif len(cmd.aliases) > 0:
                        name += f" | Alias – `{ctx.prefix + cmd.aliases[0]}`"
                    page.add_field(name=name, value=cmd.description, inline=False)
            all_pages.append(page)
        paginator = EmbedPaginator(self.bot, ctx, all_pages)
        await paginator.paginate()

    @commands.command(name='commands', usage="commands", description="View a full list of all available commands.",
                      aliases=["cmd"])
    async def commandlist(self, ctx):
        embed = discord.Embed(title="Command List", description="A full list of all available commands.\n", color=discord.Color.teal())
        for _, cog_name in enumerate(sorted(self.bot.cogs)):
            if cog_name in ["Owner", "Admin"]:
                continue
            cog = self.bot.get_cog(cog_name)
            cog_commands = cog.get_commands()
            if len(cog_commands) == 0:
                continue
            cmds = "```yml\n" + ", ".join([ctx.prefix + cmd.name for cmd in cog_commands]) + "```"
            embed.add_field(name=cog.qualified_name + " Commands", value=cmds, inline=False)
        await ctx.send(embed=embed)

    @commands.command(pass_context=True, usage='about', description="About MoonTipBot.")
    async def about(self, ctx):
        invite_link = "https://discordapp.com/oauth2/authorize?client_id=" + str(self.bot.user.id) + "&scope=bot"
        botdetails = discord.Embed(title='About Me', description='Basic ERC Tipping Bot', timestamp=datetime.utcnow(), colour=7047495)
        botdetails.add_field(name='Invite Me:', value=f'[Invite TipBot]({invite_link})', inline=True)
        botdetails.add_field(name='Servers I am in:', value=str(len(self.bot.guilds)), inline=True)
        botdetails.set_footer(text='Made in Python3.8 with discord.py library!', icon_url='http://findicons.com/files/icons/2804/plex/512/python.png')
        botdetails.set_author(name=self.bot.user.name, icon_url=self.bot.user.avatar_url)
        try:
            await ctx.send(embed=botdetails)
        except Exception as e:
            await ctx.send(embed=botdetails)
            traceback.print_exc(file=sys.stdout)
            await logchanbot(traceback.format_exc())

    @commands.command(pass_context=True, usage='invite', aliases=['inviteme'], description="Invite link of bot to your server.")
    async def invite(self, ctx):
        invite_link = "https://discordapp.com/oauth2/authorize?client_id=" + str(self.bot.user.id) + "&scope=bot"
        await ctx.send('**[INVITE LINK]**\n'
                       f'{invite_link}')


def setup(bot):
    bot.add_cog(Core(bot))
