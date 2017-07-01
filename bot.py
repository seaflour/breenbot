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
import random


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


def read_commands_from_file(c):
    c = {}
    with open("{}.txt".format(CHAN.lower())) as f:
        data = f.read()
    f.closed
    lines = data.split("\n")
    for l in lines[:-1]:
        items = l.split("\t")
        print("'{}'->'{}'".format(items[0], items[1]))
        c[items[0]] = items[1]


commands = {}
#read_commands_from_file(commands)
# Open command file and read in commands and responses from {CHAN}.txt
with open("{}.txt".format(CHAN.lower())) as f:
    data = f.read()
f.closed
lines = data.split("\n")
for l in lines[:-1]:
    items = l.split("\t")
    print("'{}'->'{}'".format(items[0],items[1]))
    commands[items[0]] = items[1]




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


# Regex for matching chat messages
# TODO match and parse extended Twitch tags
CHAT_MSG = re.compile(r"^.*:\w+!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #\w+ :")
REG_BADGES = re.compile(r"badges=(.*?);")
REG_BITS = re.compile(r"bits=(.*?);")
REG_DISPNAME = re.compile(r"display-name=(.*?);")
REG_USERNAME = re.compile(r" :(\w+?)!")
REG_USERTYPE = re.compile(r"user-type=(.*?) :")


# Flag for receiving Tag capabilities from Twitch IRC
got_tags = False


sp_commands = {}

# Special Commands:
def cmd_help():
    """
    Returns a string with all available commands
    """
    return ", ".join(list(sp_commands) + list(commands))
def cmd_uptime():
    """
    Returns a string with the uptime of the channel's stream
    """
    # Request stream information from Kraken
    r = requests.get(URL_STREAM, headers=headers)
    j = r.json()
    # Check if there is a live stream
    if j['stream'] is None:
        return "{} is currently offline.".format(CHAN)
    else:
        starttime = iso8601.parse_date(j["stream"]["created_at"])
        nowtime = datetime.datetime.now(pytz.utc)
        uptime = nowtime - starttime
        uphours = int(uptime.seconds / (60*60))
        upminutes = int(uptime.seconds / 60 % 60)
        if uphours > 0:
            return "This stream has been live for {} hours and {} minutes.".format(uphours, upminutes)
        else:
            return "This stream has been live for {} minutes.".format(upminutes)
def cmd_rate():
    """
    Returns a random score out of ten
    """
    # stupid random weight
    values = ['1', '2', '3', '4', '5', '5', '6', '6', '7', '8', '9', '10', 'Fun', 'Fun'] 
    return "{}/10".format(random.choice(values))

sp_commands = {
        r"!help": cmd_help,
        r"!uptime": cmd_uptime,
        r"!rate": cmd_rate
        }


# Main loop
while True:
    response = s.recv(1024).decode("utf-8")
    #print(response)
    if ":tmi.twitch.tv CAP * ACK :twitch.tv/tags" in response:
        got_tags = True
    elif not got_tags:
        s.send("CAP REQ :twitch.tv/tags\r\n".encode("utf-8"))

    # Keep the bot signed in
    if response == "PING :tmi.twitch.tv\r\n":
        s.send("PONG :tmi.twitch.tv\r\n".encode("utf-8"))
    else:
        # Get username
        dispname_match = REG_DISPNAME.search(response)
        if dispname_match:
            dispname = dispname_match.group(1)
        else:
            dispname = "NOBODY"

        # Get usertype
        mod = False
        usertype_match = REG_USERTYPE.search(response)
        if usertype_match:
            usertype = usertype_match.group(1)
            if usertype == "mod":
                mod = True

        # Determine if the user is the broadcaster
        broadcaster = False
        username_match = REG_USERNAME.search(response)
        if username_match:
            username = username_match.group(1)
            if username.lower() == CHAN:
                broadcaster = True
                print("(!) ", end='')



        message = CHAT_MSG.sub("", response)
        print("{}: {}".format(dispname,message).strip())

        flag = True
        # Check for special commands and respond in the chat
        for comm in list(sp_commands):
            if re.search(comm, message) != None:
                chat(s, sp_commands[comm]())
                flag = False
                break

        # Check for normal commands and response accordingly in the chat.
        if flag:
            for comm in list(commands):
                if re.search(comm, message) != None:
                    chat(s, commands[comm])
                    break

    # Slow your roll, we don't want to get banned
    time.sleep(1 / cfg.RATE)
