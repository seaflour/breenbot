#!/usr/bin/python

import cfg
import socket
import re
import time
import requests
import iso8601
import datetime
import pytz


# Get 

# Chat functions
def chat(sock, msg) :
    """
    Send a chat message to the server.
    Keyword arguments:
    sock -- the socket over which to send the message
    msg  -- the message to be sent
    """
    sock.send("PRIVMSG #{} :{}\r\n".format(cfg.CHAN.lower(), msg).encode("utf-8"))

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


# Socket stuff, join the Twitch IRC
s = socket.socket()
s.connect((cfg.HOST, cfg.PORT))
s.send("PASS {}\r\n".format(cfg.PASS).encode("utf-8"))
s.send("NICK {}\r\n".format(cfg.NICK).encode("utf-8"))
s.send("JOIN #{}\r\n".format(cfg.CHAN.lower()).encode("utf-8"))

# Set up info for making HTTP requests
URL_CHANNEL = "https://api.twitch.tv/kraken/channels/{}".format(cfg.CHAN.lower())
URL_STREAM = "https://api.twitch.tv/kraken/streams/{}".format(cfg.CHAN.lower())
headers = {
        "Client-ID": "asadyq6bfn2skqs8gmrof5wpesq7qi", 
        "Authorization": cfg.PASS2,
        "Accept": "application/wnd.twitchtv.v5+json"
        }

# Stream timezone
#TODO let user decide timezone
#stream_tz = pytz.timezone("America/New_York")
stream_tz = pytz.timezone("America/Vancouver")
def convert_from_utc(utc_dt):
    """
    Convert a datetime from UTC to another timezone.
    Keyword arguments:
    utc_dt -- a datetime in UTC
    """
    return stream_tz.normalize(utc_dt.replace(tzinfo=stream_tz).astimezone(pytz.utc))

# Regex for matching chat messages
CHAT_MSG = re.compile(r"^.*:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")

got_commands = False
got_tags = False

while True:
    response = s.recv(1024).decode("utf-8")
    print(response)
    if ":tmi.twitch.tv CAP * ACK :twitch.tv/tags" in response:
        got_tags = True
    elif not got_tags:
        s.send("CAP REQ :twitch.tv/tags\r\n".encode("utf-8"))
    #if ":tmi.twitch.tv CAP * ACK :twitch.tv/commands" in response:
    #    got_commands = True
    #elif not got_commands:
    #    s.send("CAP REQ :twitch.tv/commands\r\n".encode("utf-8"))


    # Keep the bot signed in
    if response == "PING :tmi.twitch.tv\r\n":
        s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
    else:
        # Request Twitch tag information
        #if not got_commands:
        #    s.send("CAP REQ :twitch.tv/commands\r\n".encode("utf-8"))
        #if not got_tags:
        #    s.send("CAP REQ :twitch.tv/tags\r\n".encode("utf-8"))

        # Get username and message strings
        username = re.search(r"\w+", response).group(0)
        message = CHAT_MSG.sub("", response)

        if re.match(r"!uptime", message):
            # Request stream information from Kraken
            r = requests.get(URL_STREAM, headers=headers)
            j = r.json()
            # Check if there is a live stream
            if j['stream'] is None:
                chat(s, "{} is currently offline.".format(cfg.CHAN))
            else:
                starttime = iso8601.parse_date(j["stream"]["created_at"])
                localtime = convert_from_utc(starttime);
                # Send a nicely formatted start time to the chat. TODO user-defined timezone
                chat(s, "This stream began at {}:{} (Pacific).".format(localtime.time().hour - 5, str(localtime.time().minute).zfill(2)))

        # Check for bot commands and response accordingly in the chat.
        for comm in list(cfg.COMMANDS.keys()):
            if re.match(comm, message):
                chat(s, cfg.COMMANDS[comm])
                break
    time.sleep(1 / cfg.RATE)

