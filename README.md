# QT-AI
Ollama-based Self-Hostable AI Chatbot for Discord

## Setup Instructions

Step 0. Make sure Ollama is set up, running, and working.

Step 1. Set up and Enable the Python Venv. The start.sh and start.bat expect the venv to be in python-venv, so run `python -m venv ./python-venv/` to create the venv

Step 2. run `pip -r requirements.txt` to get needed packages

Step 3. create a .env file containing `BOT_TOKEN=[Insert Token here, without brackets]`

Step 4 (Optional). Edit config.json to configure your custom AI bot. If Ollama is changed to use another port, you this is not Optional.

Step 5. Run the bot using start.sh or start.bat
