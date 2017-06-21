#!/usr/bin/python

import cfg
import sys
import socket
import re
import time
import requests
import iso8601
import datetime
import pytz
import signal


# SIGINT handler for graceful exit
def sigint_handler(signal, frame):
    print("\nFinished.")
    sys.exit(0)
signal.signal(signal.SIGINT, sigint_handler)


# Read sensitive bot account info from external file
# accountinfo.txt should have username on the first line and OAuth string on the second
with open("accountinfo.txt") as f:
    data = f.read()
f.closed
lines = data.split("\n")
NICK = lines[0]
PASS = lines[1]
print("Using account {}".format(NICK))


# Get channel name from command line, or from cfg.py
if len(sys.argv) > 1:
    CHAN = sys.argv[1]
else:
    CHAN = cfg.CHAN
print("Joining channel {}".format(CHAN))


# Chat functions
def chat(sock, msg) :
    """
    Send a chat message to the server.
    Keyword arguments:
    sock -- the socket over which to send the message
    msg  -- the message to be sent
    """
    sock.send("PRIVMSG #{} :{}\r\n".format(CHAN.lower(), msg).encode("utf-8"))

def ban(sock, user):
    """
    Ban a user from the current channel.
    Keyword arguments:
    sock -- the socket over which to send the ban command
    user -- the user to be banned
    """
    chat(sock, ".ban {}".format(user))

def timeout(sock, user, secs=600):
    """
    Timeout a user for a set period of time.
    Keyword arguments:
    sock -- the socket over which to send the timeout command
    user -- the user to be timed out
    secs -- the length of timeout in seconds (default 600)
    """
    chat(sock, ".timeout {}".format(user, secs))


# Set up socket then join the Twitch channel's IRC
s = socket.socket()
s.connect((cfg.HOST, cfg.PORT))
s.send("PASS {}\r\n".format(PASS).encode("utf-8"))
s.send("NICK {}\r\n".format(NICK).encode("utf-8"))
s.send("JOIN #{}\r\n".format(CHAN.lower()).encode("utf-8"))


# Info for making HTTP requests
URL_CHANNEL = "https://api.twitch.tv/kraken/channels/{}".format(CHAN.lower())
URL_STREAM = "https://api.twitch.tv/kraken/streams/{}".format(CHAN.lower())
headers = {
        "Client-ID": "asadyq6bfn2skqs8gmrof5wpesq7qi", 
        "Accept": "application/wnd.twitchtv.v5+json"
        }


# Stream timezone
#TODO let user decide timezone, for now assume Pacific time
stream_tz = "America/Vancouver"
#stream_tz = "America/New_York"
def convert_from_utc(utc_dt, tz):
    """
    Convert a datetime from UTC to another timezone.
    Keyword arguments:
    utc_dt -- a datetime in UTC
    tz     -- a string containing the name of the pytz timezone to convert to
    """
    return utc_dt.astimezone(pytz.timezone(tz)) 


# Regex for matching chat messages
# TODO match and parse extended Twitch tags
CHAT_MSG = re.compile(r"^.*:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")


# Flag for receiving Tag capabilities from Twitch IRC
got_tags = False


# Main loop
while True:
    response = s.recv(1024).decode("utf-8")
    print(response)
    if ":tmi.twitch.tv CAP * ACK :twitch.tv/tags" in response:
        got_tags = True
    elif not got_tags:
        s.send("CAP REQ :twitch.tv/tags\r\n".encode("utf-8"))

    # Keep the bot signed in
    if response == "PING :tmi.twitch.tv\r\n":
        s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
    else:
        # Get username and message strings
        username = re.search(r"\w+", response).group(0)
        message = CHAT_MSG.sub("", response)

        # Special command !uptime
        if re.match(r"!uptime", message):
            # Request stream information from Kraken
            r = requests.get(URL_STREAM, headers=headers)
            j = r.json()
            # Check if there is a live stream
            if j['stream'] is None:
                chat(s, "{} is currently offline.".format(CHAN))
            else:
                starttime = iso8601.parse_date(j["stream"]["created_at"])
                localtime = convert_from_utc(starttime, stream_tz);
                # Send a nicely formatted start time to the chat. TODO user-defined timezone
                chat(s, "This stream began at {}:{} (Pacific).".format(localtime.time().hour, str(localtime.time().minute).zfill(2)))

        # Check for bot commands and response accordingly in the chat.
        for comm in list(cfg.COMMANDS.keys()):
            if re.match(comm, message):
                chat(s, cfg.COMMANDS[comm])
                break

    # Slow your roll, we don't want to get banned
    time.sleep(1 / cfg.RATE)

