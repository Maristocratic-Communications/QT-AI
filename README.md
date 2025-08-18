# QT-AI
Ollama-based Self-Hostable AI Chatbot for Discord

## Setup Instructions

Step 0. Make sure Ollama is set up, running, and working.

Step 1. Set up and Enable the Python Venv. The start.sh and start.bat expect the venv to be in python-venv, so run `python -m venv ./python-venv/` to create the venv

Step 2. run `pip install discord.py aiohttp python-dotenv tzdata` to get needed packages. You will also need to enable the venv. This is shown in start.sh and start.bat for Windows and *nix systems

Step 3. create a .env file containing `BOT_TOKEN=[Insert Token here, without brackets]`

Step 4 (Optional). Edit config.json to configure your custom AI bot. If Ollama is changed to use another port, this step is not Optional.

Step 5. Run the bot using start.sh or start.bat

## Config Guide
### outdated, too lazy to update tbh
* MODEL_API_URL<br>
This is where you set up the API where Ollama runs

* MODEL_NAME<br>
This is where you set the Main AI Model for the bot to use

* BOT_NAME<br>
This is where you set up the name of your Chatbot.

* ACTIVITY_TEXT<br>
This is where you set the status of it, such as "Baking Bread" or "use qt!help"

* PROMPT_MAIN<br>
This is the main prompt for the bot to follow

* KNOWLEDGE<br>
Extra info for the bot to know

* LIKES<br>
Things the bot likes

* DISLIKES<br>
Things the bot doesnt like

* APPEARANCE<br>
What the bot looks like

* ENGINE_SETUP<br>
Here is where you specify how the bot is to type

* ERROR_RESPONSE<br>
This is the message the bot sends if there's an error contacting the LLM

* STM_CONTEXT_LENGTH<br>
Roughly How many messages the bot takes into context 

* PREFIX<br>
The Prefix used for text commands

* MULTIMODAL_MODE<br>
Image handling. Has 3 Modes: `none`, for no image handling (faster); `simulated`, for image handling reguardless of Main AI Model (slowest, bot remembers description of image); and `native`, the image is fed directly to the main LLM (faster than simulated but slower than none)

* MULTIMODAL_MODEL<br>
Selects the Model for describing the image in simulated mode

* TIMEZONE<br>
Sets the bot's timezone. Leave `None` to not let the bot know the current time

* SUMMARIZE_CHANCE<br>
Chance the bot generates an LTM automatically. 1.0 will constantly generate LTMs every message, 0.0 will stop natural LTM generation completely. LTM generation is slower

* MAX_REPLY_DEPTH<br>
Max Amount of replies the bot can follow. allows for coherent conversations, even with low STM Context Lengh
