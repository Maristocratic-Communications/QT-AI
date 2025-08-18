# Import Libraries
import discord, os, random, aiohttp, asyncio, json, base64
from discord.ext import commands
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load dotEnv and Keys
load_dotenv()
with open("config.json", "r") as f:
    config = json.load(f)

def mentionfromtoken(BOT_TOKEN):
    tokb64 = BOT_TOKEN.split(".")[0]
    botId = base64.b64decode(tokb64 + "==")
    return f"<@{int(botId)}>!"

# Load Config Keys
BOT_TOKEN = os.getenv("BOT_TOKEN")
modelURL = config["modelURL"]
Model = config["Model"]
ownerId = config["ownerId"]
botName = config["botName"]
botPrefix = config.get("botPrefix", mentionfromtoken(BOT_TOKEN))
status = config.get("status", f"use {botPrefix}help")
mainPrompt = config["mainPrompt"]
knowledge = ""
for fact in config["knowledge"]:
    knowledge = knowledge + f"{fact}\n"
likes = config["likes"]
dislikes = config["dislikes"]
appearance = config["appearance"]
responseSetup = config["responseSetup"]
errorMessage = config["errorMessage"]
stmSize = int(config["stmSize"] - 2)
imageMode = config.get("imageMode", "none")
imageModel = config.get("imageModel", None)
timezone = config.get("timezone", False)
noNSFW = config.get("noNSFW", True)
summarizeChance = config.get("summarizeChance")
freewillToggle = config.get("freewillToggle", False)
freewillReactChance = config.get("freewillReactChance", 0.05)
freewillRespondChance = config.get("freewillRespondChance", 0.03)
freewillKeywords = config.get("freewillKeywords", {})
replyChainLimit = config.get("replyChainLimit", 5)

# Enable/Disable Eval command for debugging. Probably safe to keep enabled if you own the bot.
enableEval = True

#Initialize shit
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix=botPrefix, intents=intents)
tree = bot.tree

# ensure the folders exist
os.makedirs("data", exist_ok=True)

# bot events
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{botName} QT-AI is ready (on {bot.user})')
    await bot.change_presence(activity=discord.CustomActivity(name=status))

@bot.event
async def on_message(message):
    if message.author.id == bot.user.id:
        return

    await bot.process_commands(message)
    if message.content.startswith(botPrefix):
        return

    if message.guild:
        aysmsquared = message.guild.id
    else:
        aysmsquared = message.author.id

    db = get_db(aysmsquared)
    guild_id = str(message.guild.id) if message.guild else None

    channel_id = message.channel.id
    db.setdefault("stm", {})
    db["stm"].setdefault(str(message.channel.id), [])
    if len(db["stm"][str(message.channel.id)]) > stmSize:
        db["stm"][str(message.channel.id)] = db["stm"][str(message.channel.id)][-stmSize:]
    stmcard = db["stm"][str(message.channel.id)]

    db.setdefault("ltm", [])
    ltmcard = db["ltm"]

    is_bot_mentioned = bot.user in message.mentions
    should_respond = is_bot_mentioned or (channel_id in db.get("channels", []))

    if isinstance(message.channel, discord.channel.DMChannel):
        should_respond = True

    discardFreewill = False
    if not "freewill" in db:
        if message.author.bot:
            return
        db.setdefault("freewill", {"Enabled": freewillToggle, "msgFreq": freewillRespondChance, "reactFreq": freewillReactChance, "blocked_channels": []})
        discardFreewill = True
    freewillOn = db["freewill"]["Enabled"]
    if not should_respond and freewillOn:
        freewillsettings = db["freewill"]
        if str(message.channel.id) in db["freewill"]["blocked_channels"]:
            return

        currentMsgChance = db["freewill"]["msgFreq"] or freewillRespondChance
        currentReactChance = db["freewill"]["reactFreq"] or freewillReactChance
        if not "WeighKeywords" in db["freewill"] or db["freewill"]["WeighKeywords"]:
            for word in message.content.split():
                if word.lower() in freewillKeywords and freewillKeywords[word.lower()] is not None:
                    currentMsgChance += float(freewillKeywords[word.lower()][0])
                    currentReactChance += float(freewillKeywords[word.lower()][1])

        if currentMsgChance > 1:
            currentMsgChance = 1
        if currentMsgChance < 0:
            currentMsgChance = 0

        if currentReactChance > 1:
            currentReactChance = 1
        if currentReactChance < 0:
            currentReactChance = 0

        if random.random() < currentMsgChance:
            # improv stm :grin:
            messages = [msg async for msg in message.channel.history(limit=int(stmSize/2))]
            stm = "\n".join([f"{msg.author.global_name or msg.author.name}: {msg.content}" for msg in messages])

            # ltm because yes
            ltm = ""
            for msg in ltmcard:
                ltm = ltm + f"{msg}\n"

            query = makeprompt(message, ltm, stm)
            async with message.channel.typing():
                response = await query_ollama(query)
                trimmed_response = response[:2000]
                try:
                    await message.reply(trimmed_response, allowed_mentions=discord.AllowedMentions.none())
                except Exception:
                    try:
                        await message.channel.send(trimmed_response, allowed_mentions=discord.AllowedMentions.none())
                    except Exception:
                        print(f"failed to send freewill message in #{message.channel.name} ({message.channel.id})")
        if random.random() < currentReactChance:
            # ltm because why not
            ltm = ""
            for msg in ltmcard:
                ltm = ltm + f"{msg}\n"

            unicode_pool = ["😀", "😎", "🔥", "❤️", "👍", "🎉", "😂"]

            query = (
                f"You are {botName}. {mainPrompt}\n"
                f"Here is your general knowledge:\n{knowledge}.\n"
                f"Your likes include: {likes}, and your dislikes include {dislikes}\n"
                f"Here are your long term memories: {ltm}.\n"
                f"React to this message with **either**:\n"
                f" - A custom emoji from this pool: {message.guild.emojis}\n"
                f" - A Unicode emoji, such as but not limited to these: {unicode_pool}\n"
                f"Message to react to:\n"
                f"{message.author.global_name or message.author.name}: {message.content}\n"
                f"Respond ONLY with the emoji itself. "
                f"If custom, use `<:name:id>` format. If Unicode, output the raw emoji character."
            )
            response = await query_ollama(query)

            try:
                await message.add_reaction(response)
            except Exception:
                print(f"failed to add freewill react in #{message.channel.name} ({message.channel.id})")
    if discardFreewill:
        db.pop('freewill', None)

    if should_respond:
        reply_block = ""
        ref = message.reference
        if ref is not None and ref.message_id:
            seen_ids = set()
            depth = 0
            reply_block = ""
            while ref and ref.message_id and depth < replyChainLimit:
                if ref.message_id in seen_ids:
                    break
                try:
                    replied_to = await message.channel.fetch_message(ref.message_id)
                except discord.NotFound:
                    break
                seen_ids.add(ref.message_id)
                if replied_to.author == bot.user:
                    reply_block = f"{botName}: {replied_to.content}\n" + reply_block
                else:
                    reply_block = f"{replied_to.author.global_name or replied_to.author.name}: {replied_to.content}\n" + reply_block
                ref = replied_to.reference
                depth += 1

        stmcard.append(f"{message.author.global_name or message.author.name}: {message.content}\n")
        save_db(aysmsquared, db)

    if message.author.bot:
        return

    if should_respond:
        if not nsfw_filter(message.content, noNSFW):
            return await message.channel.send("Sorry, but NSFW content isn't allowed")
        async with message.channel.typing():
            # Load LTM
            ltm = ""
            for msg in ltmcard:
                ltm = ltm + f"{msg}\n"

            stm = ""
            for msg in stmcard:
                stm = stm + f"{msg}\n"

            # Random LTM summarization
            if random.random() < summarizeChance:
                await sleepe(await bot.get_context(message))

            # Image processing
            image_block = ""
            image_urls = []
            if message.attachments:
                if imageMode == "native":
                    image_urls = [
                        a.url for a in message.attachments
                        if a.content_type and a.content_type.startswith("image/")
                    ]
                    if image_urls:
                        image_block = "\n(Images attached for context.)"
                elif imageMode == "simulated":
                    descriptions = []
                    for a in message.attachments:
                        if a.content_type and a.content_type.startswith("image/"):
                            desc = await describe_image(a.url, model=imageModel)
                            descriptions.append(desc)
                    if descriptions:
                        image_block = "\nAttached image descriptions:\n" + "\n".join(descriptions)

            # Prompt
            query = makeprompt(message, "ltm", stm, reply_block, image_block)

            # Model response
            response = await query_ollama(query, image_urls=image_urls if imageMode == "native" else None)
            trimmed_response = response[:2000]
            try:
                await message.reply(trimmed_response, allowed_mentions=discord.AllowedMentions.none())
            except Exception:
                try:
                    await message.channel.send(trimmed_response, allowed_mentions=discord.AllowedMentions.none())
                except Exception:
                    print(f"failed to send message in #{message.channel.name} ({message.channel.id})")

            # Update STM
        if image_block:
            stmcard.append(f"{image_block}\n{botName}: {trimmed_response}")
        else:
            stmcard.append(f"{botName}: {trimmed_response}")
        save_db(aysmsquared, db)

def makeprompt(message, ltm, stm, reply_block = None, image_block = None):
    if reply_block:
        replyblock2 = f"the user is replying to these messages: {reply_block}\n"
    else:
        replyblock2 = ""

    if image_block:
        imageblock2 = f"the user is replying to these messages: {image_block}\n"
    else:
        imageblock2 = ""

    if timezone:
        now = datetime.now(ZoneInfo(timezone))
        time_line = f"The current time is: {now}\n"
    else:
        time_line = ""

    user = message.author.global_name or message.author.name

    query = (
        f"You are {botName}. {mainPrompt}\n"
        f"Here is your general knowledge:\n{knowledge}.\n"
        f"You look like {appearance}\n"
        f"Your likes include: {likes}\n"
        f"Your dislikes include: {dislikes}\n"
        f"You should respond as follows: {responseSetup}\n"
        f"Please do not respond like a machine, do not use technical phrases when talking about yourself like 'i have you in my knowledge database', 'i stored information about you in my memory', or 'i will execute this instruction.', act natural, like a human. also, please do not repeat yourself, dont just say previous messages with little to no change. Additionally, do not tell the user that you are following the instructions provided in the prompt, only output your in-character reply.'\n"
        f"{time_line}"
        f"Here is your long-term memory:\n{ltm}\n"
        f"Here is your short-term memory:\n{stm}\n"
        f"\nthe user is replying to these messages: {replyblock2}"
        f"Now, respond to this query from {user}:\n{message.content}\n"
        f"{imageblock2}"
    )
    return query

# command section
@bot.hybrid_command(help="enables automatic responces in channel")
async def activate(ctx):
    if not ctx.author.guild_permissions.manage_channels and not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("You do not have permission to activate the bot (need manage channels or manage guild)", ephemeral=True)

    db = get_db(ctx.guild.id)
    guild_id = str(ctx.guild.id)
    db.setdefault("channels", [])
    if ctx.channel.id not in db["channels"]:
        db["channels"].append(ctx.channel.id)
        save_db(ctx.guild.id, db)
        await ctx.send("Activated in this channel.")
    else:
        await ctx.send("I'm already active in this channel.")
    return

@bot.hybrid_command(help="disables automatic responces in channel")
async def deactivate(ctx):
    if not ctx.channel.permissions_for(ctx.guild.me).send_messages or not ctx.channel.permissions_for(ctx.guild.me).view_channel:
        return await ctx.send("I don't have permission to send or view messages in this channel.", ephemeral=True)

    if not ctx.author.guild_permissions.manage_channels and not ctx.author.guild_permissions.manage_guild:
        return await ctx.send("You do not have permission to deactivate the bot (need manage channels or manage guild)", ephemeral=True)

    db = get_db(ctx.guild.id)
    guild_id = str(ctx.guild.id)
    if ctx.channel.id in db["channels"]:
        db["channels"].remove(ctx.channel.id)
        save_db(ctx.guild.id, db)
        await ctx.send("Deactivated in this channel.")
    else:
        await ctx.send("I'm not active in this channel.")
    return

@tree.command(name="freewill", description="freewill is when the bot does shit without asking")
@discord.app_commands.default_permissions(manage_guild=True)
async def freewill(
    ctx: discord.Interaction,
    msgfreq: float = 0.03,
    reactfreq: float = 0.05,
    enabled: bool = True,
    weighkeywords: bool = True,
    block_current_channel: bool = False
):
    if not ctx.user.guild_permissions.manage_channels and not ctx.user.guild_permissions.manage_guild:
        return await ctx.send("You do not have permission to activate the bot (need manage channels or manage guild)", ephemeral=True)

    db = get_db(ctx.guild.id)

    db.setdefault("freewill", {})
    db["freewill"].update({
        "msgFreq" : msgfreq,
        "reactFreq" : reactfreq,
        "Enabled" : enabled,
        "WeighKeywords" : weighkeywords,
    })

    db["freewill"].setdefault("blocked_channels", [])
    if block_current_channel and not str(ctx.channel.id) in db["freewill"]["blocked_channels"]:
        db["freewill"]["blocked_channels"].append(str(ctx.channel.id))
    elif str(ctx.channel.id) in db["freewill"]["blocked_channels"]:
        db["freewill"]["blocked_channels"].remove(str(ctx.channel.id))
    messg = f"Freewill mode set to: {int(msgfreq*100)}% Reply Chance, {int(reactfreq*100)}% React Chance"
    if weighkeywords:
        messg = messg + " with weighed keywords"
    else:
        messg = messg + " without weighed keywords"

    if block_current_channel:
        messg = messg + f"\n-# Disabled in #{ctx.channel.name}"
    else:
        messg = messg + f"\n-# Enabled in #{ctx.channel.name}"

    if not enabled:
        messg = f"Freewill mode set to: Off."

    try:
        await ctx.response.send_message(messg)
    except Exception:
        await ctx.channel.send(messg)

    save_db(ctx.guild.id, db)
    return

@bot.hybrid_command(help="clears stm in channel")
async def wack(ctx):
    if not ctx.author.guild_permissions.manage_channels and not ctx.author.guild_permissions.manage_guild and not str(ctx.author.id) == ownerId:
        return await ctx.send("You do not have permission to clear memory", ephemeral=True)

    db = get_db(ctx.guild.id)
    db.setdefault("stm", {})
    db["stm"].setdefault(str(ctx.channel.id), [])

    if len(db["stm"][str(ctx.channel.id)]) != 0:
        db["stm"][str(ctx.channel.id)] = []
        try:
            await ctx.send("Short term memory cleared.")
        except Exception:
            await ctx.channel.send("Short term memory cleared.")
        save_db(ctx.guild.id, db)
    else:
        await ctx.send("No short term memory to clear.")
        return


@bot.hybrid_command(help="generates long term memory for your QT-AI")
async def sleep(ctx):
    db = get_db(ctx.guild.id)
    db.setdefault("stm", {})
    db["stm"].setdefault(str(ctx.channel.id), [])
    stmcard = db["stm"][str(ctx.channel.id)]

    try:
        await ctx.send("Generating Long Term Memory...")
    except Exception:
        await ctx.channel.send("Generating Long Term Memory...")

    stm = ""
    for msg in stmcard:
        stm = stm + f"{msg}\n"

    prompt = (
        f"Here's some information. {knowledge}. Don't summerize things from here, it's only here for clarification."
        f"Summarize the following conversation into a brief long-term memory suitable for character memory, "
        f"keeping it under 2000 characters. do NOT say things like \"Here's a summary of the conversation\", just give the plain summary, with no extra fluff:\n\n{stm}"
    )
    summary = await query_ollama(prompt)
    summary = summary[:1999]

    db.setdefault("ltm", [])
    db["ltm"].append(summary)
    save_db(ctx.guild.id, db)

    try:
        await ctx.send("Long term memory saved.")
    except Exception:
        await ctx.channel.send("Long term memory saved.")
    return

# messageless version for summerization
async def sleepe(ctx):
    db = get_db(ctx.guild.id)
    db.setdefault("stm", {})
    db["stm"].setdefault(str(ctx.channel.id), [])
    stmcard = db["stm"][str(ctx.channel.id)]

    stm = ""
    for msg in stmcard:
        stm = stm + f"{msg}\n"

    prompt = (
        f"Here's some information. {knowledge}"
        f"Summarize the following conversation into a brief long-term memory suitable for character memory, "
        f"keeping it under 2000 characters. do NOT say things like \"Here's a summary of the conversation\", just give the plain summary, with no extra fluff:\n\n{stm}"
    )
    summary = await query_ollama(prompt)
    summary = summary[:1999]

    db.setdefault("ltm", [])
    db["ltm"].append(summary)
    save_db(ctx.guild.id, db)

    return

@bot.hybrid_command(help="deletes all data in server")
async def wipe(ctx):
    db = get_db(ctx.guild.id)

    if not ctx.author.guild_permissions.manage_channels and not ctx.author.guild_permissions.manage_guild and not str(ctx.author.id) == ownerId:
        return await ctx.send("You do not have permission to clear memory", ephemeral=True)

    removed = len(db["stm"])

    db.pop("stm", None)
    db.pop("ltm", None)

    await ctx.send(f"Cleared {removed} STM channels and deleted long term memory.")
    save_db(ctx.guild.id, db)
    return

@bot.hybrid_command(help="(owner only) reloads config")
async def reload(ctx):
    if not str(ctx.author.id) == ownerId:
        return await ctx.send("You do not have permission to reload config", ephemeral=True)

    with open("config.json", "r") as f:
        config = json.load(f)

    modelURL = config["modelURL"]
    Model = config["Model"]
    ownerId = config["ownerId"]
    botName = config["botName"]
    botPrefix = config.get("botPrefix", mentionfromtoken(BOT_TOKEN))
    status = config.get("status", f"use {botPrefix}help")
    mainPrompt = config["mainPrompt"]
    knowledge = ""
    for fact in config["knowledge"]:
        knowledge = knowledge + f"{fact}\n"
    likes = config["likes"]
    dislikes = config["dislikes"]
    appearance = config["appearance"]
    responseSetup = config["responseSetup"]
    errorMessage = config["errorMessage"]
    stmSize = int(config["stmSize"]  - 2)
    imageMode = config.get("imageMode", "none")
    imageModel = config.get("imageModel", None)
    timezone = config.get("timezone", False)
    noNSFW = config.get("noNSFW", True)
    summarizeChance = config.get("summarizeChance")
    freewillToggle = config.get("freewillToggle", False)
    freewillReactChance = config.get("freewillReactChance", 0.05)
    freewillRespondChance = config.get("freewillRespondChance", 0.03)
    freewillKeywords = config.get("freewillKeywords", {})
    replyChainLimit = config.get("replyChainLimit", 5)

    await ctx.send("Reloaded Config!")
    await bot.change_presence(activity=discord.CustomActivity(name=status))
    return

@bot.hybrid_command(help="shows bot info")
async def about(ctx):
    embed = discord.Embed(
        title="💕🍵✨ QT-AI",
        description="QT-AI is a Self-hostable AI Discord bot based on ollama aimed at replacing shapes.inc's now discontinued discord bot services.",
        color=discord.Color.pink()
    )
    embed.set_footer(text="QT-AI v1.1 - made with ❤️ by @mari2")
    await ctx.send(embed=embed)
    return

@bot.command(help="complex eval, multi-line + async support")
async def eval(ctx, *, prompt: str):
    if ctx.author.id == ownerId and enableEval:
        # complex eval, multi-line + async support
        # requires the full `await message.channel.send(2+3)` to get the result
        # Command from Cat Bot, adapted to Discord.py text command format
        spaced = ""
        for i in prompt.split("\n"):
            spaced += "  " + i + "\n"

        intro = (
            "async def go(prompt, bot, ctx):\n"
            " try:\n"
        )
        ending = (
            "\n except Exception:\n"
            "  await ctx.send(traceback.format_exc())"
            "\nbot.loop.create_task(go(prompt, bot, ctx))"
        )

        complete = intro + spaced + ending
        exec(complete)
# end section because i think i eat sand sometimes

# ollama qweyu
async def query_ollama(prompt, image_urls=None):
    url = modelURL
    data = {
        "model": Model,
        "prompt": prompt,
        "stream": True
    }

    # Handle images if provided
    if image_urls:
        encoded_images = []
        async with aiohttp.ClientSession() as session:
            for img_url in image_urls:
                try:
                    async with session.get(img_url) as img_resp:
                        if img_resp.status == 200:
                            img_data = await img_resp.read()
                            encoded = base64.b64encode(img_data).decode('utf-8')
                            encoded_images.append(encoded)
                        else:
                            print(f"Failed to download image from {img_url}: {img_resp.status}")
                except Exception as e:
                    print(f"Failed to download/encode image from {img_url}: {e}")

        if encoded_images:
            data["images"] = encoded_images

    # Send prompt to Ollama
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as resp:
                if resp.status != 200:
                    print(f"Error: {resp.status}, {await resp.text()}")
                    return errorMessage

                full_response = ""
                async for line in resp.content:
                    if line:
                        try:
                            json_chunk = json.loads(line.decode())
                            full_response += json_chunk.get("response", "")
                            if json_chunk.get("done", False):
                                break
                        except json.JSONDecodeError:
                            pass
                return full_response
    except Exception as e:
        print(e)
        return errorMessage

def get_db(serverId):
    if not os.path.exists(f"data/{serverId}.json"):
        return {}
    with open(f"data/{serverId}.json", "r") as f:
        return json.load(f)

def save_db(serverId, db):
    with open(f"data/{serverId}.json", "w") as f:
        json.dump(db, f, indent=2)

# Compatibility with images using multimodal LLM (Ollama NDJSON streaming)
async def describe_image(image_url: str, model: str = None) -> str:
    try:
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    print(f"Failed to download image, status code: {resp.status}")
                    return f"[Image attached, but download failed: status {resp.status}]"
                image_bytes = await resp.read()

        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")

        # Use provided model or fallback
        selected_model = model or "llava"

        # Create the generation request payload
        payload = {
            "model": selected_model,
            "prompt": "Describe this image thoroughly, but not too vividly. Do not include any prefatory text.",
            "images": [image_b64],
            "stream": True
        }

        description = ""

        # Send POST request to Ollama
        async with aiohttp.ClientSession() as session:
            async with session.post("http://localhost:11434/api/generate", json=payload) as res:
                res.raise_for_status()

                async for line in res.content:
                    line_data = line.decode("utf-8").strip()
                    if not line_data:
                        continue
                    try:
                        data = json.loads(line_data)
                        if "response" in data:
                            description += data["response"]
                        else:
                            print(f"Line missing 'response' field: {data}")
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse line as JSON: {e}, raw: {line_data}")

        description = description.strip()
        return description if description else "[Image attached, but received no description.]"

    except Exception as e:
        print(f"Error during image description: {e}")
        return f"[Image attached, but description failed: {e}]"

def nsfw_filter(inputted: str, noNSFW: bool = True) -> str:
    if not noNSFW:
        return True

    nsfw_keywords = [
        "sex", "nude", "naked", "porn",
        "boobs", "breasts", "cock", "dick",
        "penis", "vagina", "anal", "s3x",
        "cum", "orgasm", "clit", "sperm",
        "jork", "goon", "dong", "fap",
        "pussy", "coochie", "cooch", "vajayjay",
        "tits", "nipples", "areola", "milf", "dilf",
        "bdsm", "fetish", "kink", "deepthroat",
        "handjob", "blowjob", "bj", "hj",
        "rimjob", "doggystyle", "doggy",
        "threesome", "foursome", "gangbang",
        "creampie", "cumshot", "bukkake",
        "spitroast", "sixtynine", "jerking"
        "masturbate", "masturbation", "jerk off",
        "dildo", "buttplug", "vibrator",
        "strapon", "pegging", "fleshlight",
        "moan", "nsfw", "onlyfans",
        "camgirl", "camguy", "camwhore",
        "hentai", "rule34", "rape"
    ]

    for keyword in nsfw_keywords:
        if keyword in inputted.lower():
            return False

    return True

bot.run(BOT_TOKEN)
