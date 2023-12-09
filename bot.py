import discord
from discord.ext import commands
from discord import app_commands
from discord import Embed
from config import TOKEN, EMOTE, REPORT_CHANNEL, EMBED_COLOR, MIN_SCORE_THRESHOLD

import pymongo
from pymongo import MongoClient
from config import MONGODB_CLUSTER

cluster = MongoClient(MONGODB_CLUSTER)
db = cluster["userID"]
scores_collection = db["reactScore"]

intents = discord.Intents.all()  # Use .all() to enable all intents
bot = commands.Bot(command_prefix='gh!', intents=intents, help_command=None)

# define embed buttons
class embedView(discord.ui.View):
    def __init__(self, message_id, callback):
        super().__init__()
        self.message_id = message_id
        self.callback = callback
    
    @discord.ui.button(label="Useful", style=discord.ButtonStyle.success)
    async def useful(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.delete()
        if self.callback:
            await self.callback(self.message_id, useful=True)

    @discord.ui.button(label="Not Useful", style=discord.ButtonStyle.danger)
    async def not_useful(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.delete()
        if self.callback:
            await self.callback(self.message_id, useful=False)

# Dictionary to track reported messages, report counts, and users who have reported
reported_messages = {}

# remove associated report data from the dictionary
async def remove_report_data(message_id, useful=False):
    if message_id in reported_messages:
        report_data = reported_messages[message_id]
        reported_users = report_data.get("reported_users", [])

        for user_id in reported_users:
            await update_scores(user_id, useful)

        del reported_messages[message_id]

# update score in database
async def update_scores(user_id, useful=True):
    user_data = scores_collection.find_one({"_id": user_id})
    if not user_data:
        scores_collection.insert_one({"_id": user_id, "score": 0})
    
    increment = 1 if useful else -1
    scores_collection.update_one({"_id": user_id}, {"$inc": {"score": increment}})
    

# main reaction response
@bot.event
async def on_reaction_add(reaction, user):
    if hasattr(reaction.emoji, 'id') and reaction.emoji.id == EMOTE and user != bot.user:
        # check the user's score in the database
        user_data = scores_collection.find_one({"_id": user.id })

        if not user_data or (user_data["score"] >= MIN_SCORE_THRESHOLD):
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
                    embed.add_field(name="Content", value=reaction.message.content, inline=False)
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
                embed.add_field(name="Content", value=reaction.message.content, inline=False)
                embed.add_field(name="Go to Message", value=f"[Link to Message]({reaction.message.jump_url})", inline=False)

                view = embedView(message_id, remove_report_data)
                view.message = await channel.send(embed=embed, view=view)

                # Update the report message ID in the dictionary
                reported_messages[message_id]["report_message_id"] = view.message.id
        
            # React with the bot
            await reaction.message.add_reaction(reaction.emoji)

        # Remove the user's reaction
        await reaction.remove(user)
        


# slash commands
@bot.tree.command(name='reaction_block', description='block a user from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionBlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    if not user_data:
        scores_collection.insert({"_id": user.id, "score": MIN_SCORE_THRESHOLD - 1})
    else:
        scores_collection.update_one({"_id": user.id}, {"$set": {"score": MIN_SCORE_THRESHOLD - 1}})
    await ctx.followup.send(f'{user.display_name} has been blocked from reactions.')

@bot.tree.command(name='reaction_unblock', description='unblock a user from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionUnlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    if not user_data:
        scores_collection.insert({"_id": user.id, "score": 0})
    else:
        scores_collection.update_one({"_id": user.id}, {"$set": {"score": 0}})
    await ctx.followup.send(f'{user.display_name} has been unblocked from reactions.')

@bot.tree.command(name='reaction_check', description='chck if a user is blocked from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionCheck(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    if not user_data or user_data["score"] >= MIN_SCORE_THRESHOLD:
        await ctx.followup.send(f'{user.display_name} is allowed to react. score={user_data["score"]}')
    else:
        await ctx.followup.send(f'{user.display_name} is blocked from reactions. score={user_data["score"]}')

@bot.tree.command(name='reaction_blocklist', description='list all blocked users')
@app_commands.default_permissions(administrator=True)
async def reactionBlocklist(ctx: discord.interactions.Interaction):
    await ctx.response.defer()

    blocked_users = scores_collection.find({"score": {"$lt": MIN_SCORE_THRESHOLD}})
    embed = discord.Embed(title="Block List", color=EMBED_COLOR)

    for user_data in blocked_users:
        user_id = user_data["_id"]
        username = bot.get_user(user_id).display_name if bot.get_user(user_id) else f"Unknown User ({user_id})"
        blocklist_text = f"{username} (User ID: {user_id})"
        embed.add_field(name="Blocked User", value=blocklist_text, inline=False)

    await ctx.followup.send(embed=embed)


# startup routine
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name}')

bot.run(TOKEN)
