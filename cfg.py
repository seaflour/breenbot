# cfg.py
HOST = "irc.twitch.tv"      # Twitch irc server
PORT = 6667                 # yup
CHAN = "Twitch"             # default channel, overridden by commandline argument
RATE = (20/30)              # messages per second

# TODO read commands from file, allow mods to add to list
COMMANDS = {
        r"!test": "It works!",
        r"!help": "I need somebody"
        }
