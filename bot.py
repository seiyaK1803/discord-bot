import discord
from discord.ext import commands
from discord import app_commands
from discord import Embed
from config import TOKEN, EMOTE, REPORT_CHANNEL, EMBED_COLOR

intents = discord.Intents.all()  # Use .all() to enable all intents
bot = commands.Bot(command_prefix='gh!', intents=intents, help_command=None)

# define embed buttons
class embedView(discord.ui.View):
    def __init__(self, message_id, callback):
        super().__init__()
        self.message_id = message_id
        self.callback = callback
    
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.delete()

        if self.callback:
            self.callback(self.message_id)

# Dictionary to track reported messages, report counts, and users who have reported
reported_messages = {}

# remove associated report data from the dictionary
def remove_report_data(message_id):
    if message_id in reported_messages:
        del reported_messages[message_id]

# main reaction response
@bot.event
async def on_reaction_add(reaction, user):
    if reaction.emoji.id == EMOTE and user != bot.user:
        channel = bot.get_channel(REPORT_CHANNEL)
        message_id = reaction.message.id

        # Check if the message has already been reported
        if message_id in reported_messages:
            report_data = reported_messages[message_id]
            count = report_data["count"]
            reported_users = report_data["reported_users"]
            report_message_id = report_data["report_message_id"]
            
            # Check if the user has already reported the message
            if user.id not in reported_users:
                reported_users.append(user.id)
                count += 1

                # Update the existing report message
                report_message = await channel.fetch_message(report_message_id)

                # Create Embed message with updated report count and all reporting users
                embed = Embed(
                    title=f"Reported Message in #{reaction.message.channel.name}",
                    color=EMBED_COLOR,
                )
                embed.add_field(name="Report Count", value=count, inline=False)
                embed.add_field(name="Reported by", value=','.join([f"<@{user_id}>" for user_id in reported_users]), inline=False)
                embed.add_field(name="MSG Content", value=reaction.message.content, inline=False)
                embed.add_field(name="Go to Message", value=f"[Link to Message]({reaction.message.jump_url})", inline=False)

                await report_message.edit(embed=embed)
        else:
            # Create a unique ID for the report message
            report_message_id = f'report_{message_id}_{user.id}'
            reported_messages[message_id] = {
                "count": 1,
                "reported_users": [user.id],
                "report_message_id": report_message_id
            }
            count = 1
            reported_users = reported_messages[message_id]["reported_users"]

            # Create Embed message with report count and all reporting users
            embed = Embed(
                title=f"Reported Message in #{reaction.message.channel.name}",
                color=EMBED_COLOR,
            )
            embed.add_field(name="Report Count", value=count, inline=False)
            embed.add_field(name="Reported by", value=','.join([f"<@{user_id}>" for user_id in reported_users]), inline=False)
            embed.add_field(name="MSG Content", value=reaction.message.content, inline=False)
            embed.add_field(name="Go to Message", value=f"[Link to Message]({reaction.message.jump_url})", inline=False)

            view = embedView(message_id, remove_report_data)
            view.message = await channel.send(embed=embed, view=view)

            # Update the report message ID in the dictionary
            reported_messages[message_id]["report_message_id"] = view.message.id

        # Remove the user's reaction
        await reaction.remove(user)
        # React with the bot
        await reaction.message.add_reaction(reaction.emoji)


# slash commands
@bot.tree.command(name='reaction_block', description='block a user from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionBlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.send_message(f'TODO block {user}')

@bot.tree.command(name='reaction_unblock', description='unblock a user from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionUnlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.send_message(f'TODO unblock {user}')

@bot.tree.command(name='reaction_blocklist', description='list all blocked users')
@app_commands.default_permissions(administrator=True)
async def reactionBlocklist(ctx: discord.interactions.Interaction):
    await ctx.response.send_message('TODO display a blocklist i guess?')

# startup routine
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name}')

bot.run(TOKEN)
