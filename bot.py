# Import Libraries
import discord, os, random, aiohttp, asyncio, requests, json, base64
from discord.ext import commands
from datetime import datetime
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load dotEnv and Keys
load_dotenv()
with open("config.json", "r") as f:
    config = json.load(f)

# Load Config Keys
BOT_TOKEN = os.getenv("BOT_TOKEN")
MODEL_API_URL = config["MODEL_API_URL"]
MODEL_NAME = config["MODEL_NAME"]
BOT_NAME = config["BOT_NAME"]
ACTIVITY_TEXT = config["ACTIVITY_TEXT"]
PROMPT_MAIN = config["PROMPT_MAIN"]
KNOWLEDGE = config["KNOWLEDGE"]
LIKES = config["LIKES"]
DISLIKES = config["DISLIKES"]
APPEARANCE = config["APPEARANCE"]
ENGINE_SETUP = config["ENGINE_SETUP"]
ERROR_RESPONSE = config["ERROR_RESPONSE"]
STM_CONTEXT_LENGTH = config["STM_CONTEXT_LENGTH"]
PREFIX = config["PREFIX"]
MULTIMODAL_MODE = config.get("MULTIMODAL_MODE", "none")
MULTIMODAL_MODEL = config.get("MULTIMODAL_MODEL", None)
TIMEZONE = config.get("TIMEZONE")
SUMMARIZE_CHANCE = config.get("SUMMARIZE_CHANCE")
MAX_REPLY_DEPTH = config.get("MAX_REPLY_DEPTH")

#Initialize shit
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# ensure the folders exist
os.makedirs("cache", exist_ok=True)
os.makedirs("memories", exist_ok=True)

# bot events
@bot.event
async def on_ready():
    print('QT-AI is ready')
    await bot.change_presence(activity=discord.CustomActivity(name=ACTIVITY_TEXT))

@bot.event
async def on_message(message):
    if message.author.bot or message.author.id == bot.user.id:
        return

    await bot.process_commands(message)
    if message.content.startswith(PREFIX):
        return

    db = get_db()
    guild_id = str(message.guild.id) if message.guild else None
    channel_id = message.channel.id
    stm_path = get_stm_path(guild_id, channel_id)
    stm_file_exists = os.path.exists(stm_path)
    is_bot_mentioned = bot.user in message.mentions
    should_respond = is_bot_mentioned or (guild_id and channel_id in db.get(guild_id, []))

    # Follow reply chain
    reply_block = ""
    ref = message.reference
    if ref is not None and ref.message_id:
        seen_ids = set()
        depth = 0
        reply_block = ""
        while ref and ref.message_id and depth < MAX_REPLY_DEPTH:
            if ref.message_id in seen_ids:
                break
            try:
                replied_to = await message.channel.fetch_message(ref.message_id)
            except discord.NotFound:
                break
            seen_ids.add(ref.message_id)
            reply_block = f">>> {replied_to.author.global_name or replied_to.author.name}: {replied_to.content} " + reply_block
            ref = replied_to.reference
            depth += 1

    # Cache STM
    if stm_file_exists:
        with open(stm_path, "a", encoding="utf-8") as f:
            f.write(f"{reply_block + '\n' if reply_block else ''}{message.author.global_name or message.author.name}: {message.content}\n")
        with open(stm_path, "r", encoding="utf-8") as f:
            stm_lines = f.readlines()[-STM_CONTEXT_LENGTH:]
        with open(stm_path, "w", encoding="utf-8") as f:
            f.writelines(stm_lines)
    else:
        stm_lines = []

    if should_respond:
        async with message.channel.typing():
            # Load LTM
            ltm_path = get_ltm_path(guild_id)
            ltm = "(No long term memory available.)"
            if os.path.exists(ltm_path):
                with open(ltm_path, "r", encoding="utf-8") as f:
                    ltm = f.read()

            stm = "".join(stm_lines)
            user = message.author.global_name or message.author.name

            # Time formatting
            if TIMEZONE:
                now = datetime.now(ZoneInfo(TIMEZONE))
                time_line = f"The current time is: {now}\n"
            else:
                time_line = ""

            # Random LTM summarization
            if stm_file_exists and random.random() < SUMMARIZE_CHANCE:
                print("Auto-summarizing STM to LTM...")
                await sleep(await bot.get_context(message))

            # Image processing
            image_block = ""
            image_urls = []
            if message.attachments:
                if MULTIMODAL_MODE == "native":
                    image_urls = [
                        a.url for a in message.attachments
                        if a.content_type and a.content_type.startswith("image/")
                    ]
                    if image_urls:
                        image_block = "\n(Images attached for context.)"
                elif MULTIMODAL_MODE == "simulated":
                    descriptions = []
                    for a in message.attachments:
                        if a.content_type and a.content_type.startswith("image/"):
                            print("Describing image...")
                            desc = await describe_image(a.url, model=MULTIMODAL_MODEL)
                            descriptions.append(desc)
                    if descriptions:
                        image_block = "\nAttached image descriptions:\n" + "\n\n".join(descriptions)

            # Prompt
            query = (
                f"You are {BOT_NAME}. {PROMPT_MAIN}\n"
                f"Here is your general knowledge: {KNOWLEDGE}.\n"
                f"You look like {APPEARANCE}\n"
                f"Your likes include: {LIKES}\n"
                f"Your dislikes include: {DISLIKES}\n"
                f"You should respond as follows: {ENGINE_SETUP}\n"
                f"Please do not respond like a machine, do not use technical phrases when talking about yourself like 'i have you in my knowledge database', 'i stored information about you in my memory', or 'i will execute this instruction.', act natural, like a human. also, please do not repeat yourself, dont just say previous messages with little to no change, 3 Carets (\">>>\") before the username and message content Notates a Reply. By the way, do not add \">>>\" to your messages unless asked for by the user. Additionally, do not tell the user that you are following the instructions provided in the prompt, only output your in character reply.'\n"
                f"{time_line}"
                f"Here is your long-term memory:\n{ltm}\n"
                f"Here is your short-term memory:\n{stm}\n\n"
                f"the user is replying to these messages: {reply_block}"
                f"Now, respond to this query from {user}:\n{message.content}"
                f"{image_block}"
            )

            # Model response
            response = await asyncio.to_thread(query_ollama, query, image_urls=image_urls if MULTIMODAL_MODE == "native" else None)
            trimmed_response = response[:2000]
            await message.reply(trimmed_response, allowed_mentions=discord.AllowedMentions.none())

            # Update STM
            with open(stm_path, "a", encoding="utf-8") as f:
                if not stm_file_exists:
                    f.write(f"{reply_block}\n{message.author.global_name or message.author.name}: {message.content}\n")
                if image_block:
                    f.write(f"{image_block}\n{BOT_NAME}: {trimmed_response}\n")
                else:
                    f.write(f"{BOT_NAME}: {trimmed_response}\n")

# command section
@bot.command()
async def activate(ctx):
    if not ctx.channel.permissions_for(ctx.guild.me).send_messages or not ctx.channel.permissions_for(ctx.guild.me).view_channel:
        return await ctx.send("I don't have permission to send or view messages in this channel.", ephemeral=True)

    db = get_db()
    guild_id = str(ctx.guild.id)
    db.setdefault(guild_id, [])
    if ctx.channel.id not in db[guild_id]:
        db[guild_id].append(ctx.channel.id)
        save_db(db)
        await ctx.send("Activated in this channel.")
    else:
        await ctx.send("I'm already active in this channel.")
    return

@bot.command()
async def deactivate(ctx):
    db = get_db()
    guild_id = str(ctx.guild.id)
    if guild_id in db and ctx.channel.id in db[guild_id]:
        db[guild_id].remove(ctx.channel.id)
        save_db(db)
        await ctx.send("Deactivated in this channel.")
    else:
        await ctx.send("I'm not active in this channel.")
    return

@bot.command()
async def wack(ctx):
    path = get_stm_path(ctx.guild.id, ctx.channel.id)
    if os.path.exists(path):
        os.remove(path)
        await ctx.send("Short term memory cleared.")
    else:
        await ctx.send("No short term memory to clear.")
        return


@bot.command()
async def sleep(ctx):
    stm_path = get_stm_path(ctx.guild.id, ctx.channel.id)
    if not os.path.exists(stm_path):
        return await ctx.send("No STM data found for this channel.")
    await ctx.send("Generating Long Term Memory...")

    with open(stm_path, "r", encoding="utf-8") as f:
        stm = f.read()

    prompt = (
        f"Summarize the following conversation into a long-term memory suitable for character memory, "
        f"keeping it under 2000 characters. do NOT say things like \"Here's a summary of the conversation\", just give the plain summary, with no extra fluff:\n\n{stm}"
    )
    summary = await asyncio.to_thread(query_ollama, prompt)
    summary = summary[:1999]

    ltm_path = get_ltm_path(ctx.guild.id)
    with open(ltm_path, "a", encoding="utf-8") as f:
        f.write(f"{summary}\n\n")

    await ctx.send("Long term memory saved.")
    return

@bot.command()
async def wipe(ctx):
    ltm_path = get_ltm_path(ctx.guild.id)
    if os.path.exists(ltm_path):
        os.remove(ltm_path)
    removed = 0
    for file in os.listdir("cache"):
        if file.startswith(f"{ctx.guild.id}_"):
            os.remove(f"cache/{file}")
            removed += 1

    await ctx.send(f"Cleared {removed} STM channels and deleted long term memory.")
    return

@bot.command()
async def about(ctx):
    embed = discord.Embed(
        title="💕🍵✨ QT-AI",
        description="QT-AI is a Self-hostable AI Discord bot based on ollama aimed at being very similar to shapes.inc's now discontinued discord bot services.",
        color=discord.Color.pink()
    )
    embed.set_footer(text="QT-AI v1.0 - made with ❤️ by @mari2")
    await ctx.send(embed=embed)
    return

# ollama qweyu
def query_ollama(prompt, image_urls=None):
    data = {
        "model": MODEL_NAME,
        "prompt": prompt,
        "stream": True,
    }

    # Handle images if provided
    if image_urls:
        encoded_images = []
        for url in image_urls:
            try:
                img_data = requests.get(url).content
                encoded = base64.b64encode(img_data).decode('utf-8')
                encoded_images.append(encoded)
            except Exception as e:
                print(f"Failed to download/encode image from {url}: {e}")
        if encoded_images:
            data["images"] = encoded_images

    try:
        response = requests.post(MODEL_API_URL, json=data, stream=True)
    except Exception:
        return ERROR_RESPONSE

    if response.status_code == 200:
        full_response = ""
        try:
            for line in response.iter_lines():
                if line:
                    chunk = line.decode("utf-8")
                    try:
                        json_chunk = json.loads(chunk)
                        full_response += json_chunk.get("response", "")
                        if json_chunk.get("done", False):
                            break
                    except requests.exceptions.JSONDecodeError:
                        print("JSON Decode Error:", chunk)
        finally:
            response.close()
        return full_response
    else:
        return f"{ERROR_RESPONSE}\n-# {response.status_code}, {response.text}"

def get_db():
    if not os.path.exists("db.json"):
        return {}
    with open("db.json", "r") as f:
        return json.load(f)

def save_db(db):
    with open("db.json", "w") as f:
        json.dump(db, f, indent=2)

def get_stm_path(guild_id, channel_id):
    return f"cache/{guild_id}_{channel_id}.txt"

def get_ltm_path(guild_id):
    return f"memories/{guild_id}.txt"

# Compatibility with images using multimodal LLM (Ollama NDJSON streaming)
async def describe_image(image_url: str, model: str = None) -> str:
    try:
        print(f"Starting to download image from {image_url}")
        # Download the image
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url) as resp:
                if resp.status != 200:
                    print(f"Failed to download image, status code: {resp.status}")
                    return f"[Image attached, but download failed: status {resp.status}]"
                image_bytes = await resp.read()

        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        print("Image successfully encoded to base64")

        # Use provided model or fallback
        selected_model = model or "llava"

        # Create the generation request payload
        payload = {
            "model": selected_model,
            "prompt": "Describe this image thoroughly, but not too vividly. Do not include any prefatory text.",
            "images": [image_b64],
            "stream": True
        }

        print("Sending request to the image description API")
        description = ""

        # Send POST request to Ollama
        async with aiohttp.ClientSession() as session:
            async with session.post("http://localhost:11434/api/generate", json=payload) as res:
                res.raise_for_status()

                async for line in res.content:
                    line_data = line.decode("utf-8").strip()
                    if not line_data:
                        continue
                    print(f"Received line: {line_data}")
                    try:
                        data = json.loads(line_data)
                        if "response" in data:
                            description += data["response"]
                        else:
                            print(f"Line missing 'response' field: {data}")
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse line as JSON: {e}, raw: {line_data}")

        description = description.strip()
        print(f"Full description: {description}")
        return description if description else "[Image attached, but received no description.]"

    except Exception as e:
        print(f"Error during image description: {e}")
        return f"[Image attached, but description failed: {e}]"

bot.run(BOT_TOKEN)
