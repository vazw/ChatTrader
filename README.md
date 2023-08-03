# Telegram Trading Bot with ChatGPT
VXMA Trading Bot Strategy with TelegramBot UI and ChatGPT Helper
Setting thought Telegram chat

## Dependency
- Docker
- Python

## Installtion
Put your TelegramBot and ChatGPT token to .env file
then run ./install.sh
installtion script may build Docker image and run it after finished.
you may be able to start you chat with bot on Telegram.

## Usage
- /start : use for the first time after completed installtion process
- /menu : Show application menu
- /help : Show help menu 
- /clear : to clear bot's chat and reset ChatGPT session
- any messages without "/" may sent to chatGPT

## Screenshot

**later


## Todo

1. Edit download ohlc candle data to save into a file with specified symbols name and timeframe.
2. Add customs strategy and implements strategy files loader.
3. Seperate Thread for 
  - Data loading
  - Signal generator from strategy
  - Telegram Callback
  - Money-managements
4. Implements more Exchange Post order Functions.
