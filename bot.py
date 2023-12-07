import discord
from discord.ext import commands
from discord import Embed
from config import TOKEN
from config import EMOTE
from config import REPORT_CHANNEL
from config import EMBED_COLOR

intents = discord.Intents.all()  # Use .all() to enable all intents
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.event
async def on_reaction_add(reaction, user):
    if reaction.emoji.id == EMOTE and user != bot.user:
        channel = bot.get_channel(REPORT_CHANNEL)
        #await channel.send(f"{user.name} reacted with your custom emoji!")

        # create Embed message
        embed = Embed(title=f"Reported Message in #{reaction.message.channel.name}", color=EMBED_COLOR)
        embed.add_field(name="User", value=user.name, inline=False)
        embed.add_field(name="MSG Content", value=reaction.message.content, inline=False)
        embed.add_field(name="Go to Message", value=f"[Link to Message]({reaction.message.jump_url})", inline=False)

        await channel.send(embed=embed)


@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('pong')

bot.run(TOKEN)
