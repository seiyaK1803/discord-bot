import discord
from discord.ext import commands
from discord import Embed
from config import TOKEN
from config import EMOTE
from config import REPORT_CHANNEL
from config import EMBED_COLOR

intents = discord.Intents.all()  # Use .all() to enable all intents
bot = commands.Bot(command_prefix='!', intents=intents)

# define embed buttons
class embedView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.message = None
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.delete()

# main reaction response
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

        view = embedView()
        view.message = await channel.send(embed=embed, view=view)

        # remove the user's reaction
        await reaction.remove(user)
        # react with the bot
        await reaction.message.add_reaction(reaction.emoji)


# slash commands
@bot.tree.command(name='reaction_block', description='block a user from reaction')
async def reactionBlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.send_message(f'TODO block {user}')

@bot.tree.command(name='reaction_unblock', description='unblock a user from reaction')
async def reactionUnlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.send_message(f'TODO unblock {user}')

@bot.tree.command(name='reaction_blocklist', description='list all blocked users')
async def reactionBlocklist(ctx: discord.interactions.Interaction):
    await ctx.response.send_message('TODO display a blocklist i guess?')

# other commands (TODO delete these)
@bot.command(name='ping')
async def ping(ctx):
    await ctx.send('pong')

# startup routine
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name}')

bot.run(TOKEN)
