import discord
from discord.ext import commands
from discord import app_commands
from discord import Embed
from statistics import median
from config import TOKEN, EMOTE, REPORT_CHANNEL, EMBED_COLOR, MIN_SCORE_THRESHOLD

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
        super().__init__(timeout=None)
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

# DM confirmation on Report Close
async def send_useful_confirmation(message_id):
    reporting_users = reported_messages[message_id].get("reported_users", [])
    for user_id in reporting_users:
        reporting_user = bot.get_user(user_id)
        if reporting_user:
            embed_title = "Report Closed"
            embed_description = "Your report was acknowledged by the moderators. Thank you for your help in making the community a better place!"
            confirmation_embed = Embed(
                title=embed_title,
                description=embed_description,
                color=0x00FF00 # green
            )
            await reporting_user.send(embed=confirmation_embed)

async def send_not_useful_confirmation(message_id):
    reporting_users = reported_messages[message_id].get("reported_users", [])
    for user_id in reporting_users:
        reporting_user = bot.get_user(user_id)
        if reporting_user:
            user_data = scores_collection.find_one({"_id": user_id})
            negative_score_warning = ""
            if user_data and user_data["score"] < 0:
                negative_score_warning = f"Abuse of the system may result in reporting privileges being taken away. You have {user_data['score'] - MIN_SCORE_THRESHOLD + 1} strikes left."
            embed_title = "Report Closed"
            embed_description = (f"Your report was reviewed. However, the moderators have declined to take action on this situation. This could happen for various reasons such as the report being suspected as a troll, witchhunt/bullying, or otherwise. Please contact ModMail <@{1059468645249589369}> if you believe there is a mistake. {negative_score_warning}")
            confirmation_embed = Embed(
                title=embed_title,
                description=embed_description,
                color=0xFF0000 # red
            )
            await reporting_user.send(embed=confirmation_embed)


# remove associated report data from the dictionary
async def remove_report_data(message_id, useful=False):
    if message_id in reported_messages:
        report_data = reported_messages[message_id]
        reported_users = report_data.get("reported_users", [])
        channel_id = report_data.get("channel_id")

        for user_id in reported_users:
            await update_scores(user_id, useful)

        # Remove the bot's reaction from the reported message
        if channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                report_message = await channel.fetch_message(message_id)
                await report_message.clear_reaction(bot.get_emoji(EMOTE))

        if useful:
            await send_useful_confirmation(message_id)
        else:
            await send_not_useful_confirmation(message_id)

        del reported_messages[message_id]

# update score in database
async def update_scores(user_id, useful=True):
    user_data = scores_collection.find_one({"_id": user_id})
    if not user_data:
        scores_collection.insert_one({"_id": user_id, "score": 0})
    
    increment = 1 if useful else -1
    scores_collection.update_one({"_id": user_id}, {"$inc": {"score": increment}})
    
# calculate median score and determine color
def calculate_color(scores):
    median_score = median(scores)
    if median_score >= 0:
        # Calculate gradient between green and white based on the median score
        r = int(255 * (1 - median_score / 10))
        g = 255
        b = int(255 * (1 - median_score / 10))
        return (r << 16) + (g << 8) + b
    else:
        # gradient between white and red
        r = 255
        g = int(255 * (1 + median_score / abs(MIN_SCORE_THRESHOLD)))
        b = int(255 * (1 + median_score / abs(MIN_SCORE_THRESHOLD)))
        return (r << 16) + (g << 8) + b
        
# main reaction response
@bot.event
async def on_raw_reaction_add(payload):
    user = bot.get_user(payload.user_id)

    if hasattr(payload.emoji, 'id') and payload.emoji.id == EMOTE and user != bot.user:
        # check the user's score in the database
        user_data = scores_collection.find_one({"_id": user.id })
        message_channel = bot.get_channel(payload.channel_id)
        message_id = payload.message_id
        reacted_message = await message_channel.fetch_message(message_id)

        if not user_data or (user_data["score"] >= MIN_SCORE_THRESHOLD):
            channel = bot.get_channel(REPORT_CHANNEL)

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

                    scores = [scores_collection.find_one({"_id": user_id}).get("score", 0) for user_id in reported_users]
                    color = calculate_color(scores)
                    # Create Embed message with updated report count and all reporting users
                    embed = Embed(
                        title=f"Reported Message in #{reacted_message.channel.name}",
                        color=color,
                    )
                    embed.add_field(name="Report Count", value=count, inline=False)
                    embed.add_field(name="Reported by", value=','.join([f"<@{user_id}>" for user_id in reported_users]), inline=False)
                    embed.add_field(name="Content", value=reacted_message.content, inline=False)
                    embed.add_field(name="Go to Message", value=f"[Link to Message]({reacted_message.jump_url})", inline=False)

                    await report_message.edit(embed=embed)

                    confirmation_embed = Embed(title="Report Confirmation",
                                               description=f"Thank you for reporting [this message]({reacted_message.jump_url}). We will review your report as soon as possible. Feel free to send a ModMail <@{1059468645249589369}> if you have any further concerns.",
                                               color=EMBED_COLOR)
                    await user.send(embed=confirmation_embed)
            else:
                # Create a unique ID for the report message
                report_message_id = f'report_{message_id}_{user.id}'
                reported_messages[message_id] = {
                    "count": 1,
                    "reported_users": [user.id],
                    "report_message_id": report_message_id,
                    "channel_id": reacted_message.channel.id
                }
                count = 1
                reported_users = reported_messages[message_id]["reported_users"]
                scores = [scores_collection.find_one({"_id": user_id}).get("score", 0) for user_id in reported_users]
                color = calculate_color(scores)
                # Create Embed message with report count and all reporting users
                embed = Embed(
                    title=f"Reported Message in #{reacted_message.channel.name}",
                    color=color,
                )
                embed.add_field(name="Report Count", value=count, inline=False)
                embed.add_field(name="Reported by", value=','.join([f"<@{user_id}>" for user_id in reported_users]), inline=False)
                embed.add_field(name="Content", value=reacted_message.content, inline=False)
                embed.add_field(name="Go to Message", value=f"[Link to Message]({reacted_message.jump_url})", inline=False)

                view = embedView(message_id, remove_report_data)
                view.message = await channel.send(embed=embed, view=view)

                # Update the report message ID in the dictionary
                reported_messages[message_id]["report_message_id"] = view.message.id

                confirmation_embed = Embed(title="Report Confirmation",
                                           description=f"Thank you for reporting [this message]({reacted_message.jump_url}). We will review your report as soon as possible. Feel free to send a ModMail <@{1059468645249589369}> if you have any further concerns.",
                                           color=EMBED_COLOR)
                await user.send(embed=confirmation_embed)

            # React with the bot
            await reacted_message.add_reaction(payload.emoji)

        # Remove the user's reaction
        await reacted_message.remove_reaction(payload.emoji, user)
        
# application command
@bot.tree.context_menu(name='Report Message')
async def report(ctx: discord.Interaction, message: discord.Message):
    user = ctx.user
    message_channel = ctx.channel

    # Check if user's score is in the database
    user_data = scores_collection.find_one({"_id": user.id})
    
    if not user_data or (user_data["score"] >= MIN_SCORE_THRESHOLD):
        channel = bot.get_channel(REPORT_CHANNEL)
        # check if this message has already been reported
        if message.id in reported_messages:
            report_data = reported_messages[message.id]
            count = report_data["count"]
            reported_users = report_data["reported_users"]
            report_message_id = report_data["report_message_id"]

            # check if the user has already reported the message
            if user.id not in reported_users:
                reported_users.append(user.id)
                count += 1

                # update the existing report message
                report_message = await channel.fetch_message(report_message_id)

                scores = [scores_collection.find_one({"_id": user_id}).get("score", 0) for user_id in reported_users]
                color = calculate_color(scores)

                # Create Embed message with updated report count and all reporting users
                embed = Embed(
                    title=f"Reported Message in #{message.channel.name}",
                    color=color,
                )
                embed.add_field(name="Report Count", value=count, inline=False)
                embed.add_field(name="Reported by", value=','.join([f"<@{user_id}>" for user_id in reported_users]), inline=False)
                embed.add_field(name="Content", value=message.content, inline=False)
                embed.add_field(name="Go to Message", value=f"[Link to Message]({message.jump_url})", inline=False)

                await report_message.edit(embed=embed)

                confirmation_embed = Embed(title="Report Confirmation",
                                           description=f"Thank you for reporting [this message]({message.jump_url}). We will review your report as soon as possible. Feel free to send a ModMail <@{1059468645249589369}> if you have any further concerns.",
                                           color=EMBED_COLOR)
                await user.send(embed=confirmation_embed)
        else:
            # Create a unique ID for the report message
            report_message_id = f'report_{message.id}_{user.id}'
            reported_messages[message.id] = {
                "count": 1,
                "reported_users": [user.id],
                "report_message_id": report_message_id,
                "channel_id": message_channel.id
            }
            count = 1
            reported_users = reported_messages[message.id]["reported_users"]
            scores = [scores_collection.find_one({"_id": user_id}).get("score", 0) for user_id in reported_users]
            color = calculate_color(scores)
            # Create Embed message with report count and all reporting users
            embed = Embed(
                title=f"Reported Message in #{message.channel.name}",
                color=color,
            )
            embed.add_field(name="Report Count", value=count, inline=False)
            embed.add_field(name="Reported by", value=','.join([f"<@{user_id}>" for user_id in reported_users]), inline=False)
            embed.add_field(name="Content", value=message.content, inline=False)
            embed.add_field(name="Go to Message", value=f"[Link to Message]({message.jump_url})", inline=False)

            view = embedView(message.id, remove_report_data)
            view.message = await channel.send(embed=embed, view=view)

            # Update the report message ID in the dictionary
            reported_messages[message.id]["report_message_id"] = view.message.id

            confirmation_embed = Embed(title="Report Confirmation",
                                       description=f"Thank you for reporting [this message]({message.jump_url}). We will review your report as soon as possible. Feel free to send a ModMail <@{1059468645249589369}> if you have any further concerns.",
                                       color=EMBED_COLOR)
            await user.send(embed=confirmation_embed)

            # React with the bot
            await message.add_reaction(bot.get_emoji(EMOTE))
    
    await ctx.response.send_message(f"Thank you for reporting [this message]({message.jump_url})! You should have received a DM from the bot. If you did not, or have any other concerns, please send a ModMail <@{1059468645249589369}>.", ephemeral=True)

# slash commands
@bot.tree.command(name='reaction_block', description='block a user from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionBlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    if not user_data:
        scores_collection.insert_one({"_id": user.id, "score": MIN_SCORE_THRESHOLD - 1})
    else:
        scores_collection.update_one({"_id": user.id}, {"$set": {"score": MIN_SCORE_THRESHOLD - 1}})
    await ctx.followup.send(f'{user.display_name} has been blocked from reactions.')

@bot.tree.command(name='reaction_unblock', description='unblock a user from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionUnlock(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    if not user_data:
        scores_collection.insert_one({"_id": user.id, "score": 0})
    else:
        scores_collection.update_one({"_id": user.id}, {"$set": {"score": 0}})
    await ctx.followup.send(f'{user.display_name} has been unblocked from reactions.')

@bot.tree.command(name='reaction_check', description='check if a user is blocked from reaction')
@app_commands.default_permissions(administrator=True)
async def reactionCheck(ctx: discord.interactions.Interaction, user: discord.Member):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    if not user_data or user_data["score"] >= MIN_SCORE_THRESHOLD:
        await ctx.followup.send(f'{user.display_name} is allowed to react. score={user_data["score"]}')
    else:
        await ctx.followup.send(f'{user.display_name} is blocked from reactions. score={user_data["score"]}')

@bot.tree.command(name='reaction_set', description='set user score to a value')
@app_commands.default_permissions(administrator=True)
async def reactionSet(ctx: discord.interactions.Interaction, user: discord.Member, score: int):
    await ctx.response.defer()
    user_data = scores_collection.find_one({"_id": user.id})
    prev_score = 0
    if not user_data:
        scores_collection.insert_one({"_id": user.id, "score": score})
    else:
        prev_score = user_data["score"]
        scores_collection.update_one({"_id": user.id}, {"$set": {"score": score}})
    await ctx.followup.send(f'{user.display_name} score updated from {prev_score} to {score}')

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
