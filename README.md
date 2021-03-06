# mcidle-python
An idling cli for minecraft which works by proxying your connection to a minecraft server remotely allowing you to disconnect at any point but remain connected to the server through mcidle.

It is particularly useful for servers which punish you for disconnecting (e.g `2b2t.org` which has queues)

I recommend using two accounts: one to login with via mcidle, and one to connect to mcidle with locally to avoid invalidating your login sessions (see notes).

Feel free to submit an issue if something doesn't work properly.

# Supported Versions

If your game/server version is not listed below then `mcidle` will not function properly.

| Version        | Protocol     |
|:-------------:|:-------------:|
| 1.12.2        | 340           |

Make sure you connect with the exact game version that matches the mcidle server and the real-server.

# Setup

Simply run `pip install -r requirements.txt` to install all the necessary packages.


# Notes

When you provide arguments `username` and `password` to the CLI you do not need to provide them again so long as your credentials have not been invalidated. Your username and password are not saved and the login credentials are stored in `credentials.json` (keep these secret).

***If you re-login to Minecraft after starting `mcidle` your `credentials.json` file will be invalidated, simply re-login and don't close mcidle and you'll be able to connect.***

***You'll know you have this error if you see an "Invalid Session" error after connecting to the local mcidle server.***

Make sure that when you connect you connect with the same game client version number as the server.

If you keep on logging in too fast (re-updating credentials) you might get an "invalid username or password" error even though your username/password is correct. Wait 5 minutes before running the script again (this has to do with the way Mojang auth works).

# Example Usage

Run `python mcidle.py --username=example@example.com --password=pw123 --ip=2b2t.org` to point mcidle to `2b2t.org` and listen on `localhost:1337` with the login information `example@example.com` and password `pw123`.

Connecting to `localhost:1337` with your Minecraft client will let you resume your connection to `2b2t.org`. You can change the port at any time by changing the `dport` flag.

Run `python mcidle.py --help` for additional instructions on how to use the command-line utility.

```
usage: mcidle.py [-h] [--ip IP] [--port PORT] [--protocol PROTOCOL]
               [--username USERNAME] [--password PASSWORD] [--dstport DSTPORT]

optional arguments:
  -h, --help           show this help message and exit
  --ip IP              The ip address of the server to connect to (e.g
                       localhost)
  --port PORT          The port of the server to connect to (default=25565)
  --protocol PROTOCOL  The protocol version of the server to connect to
                       (default=340)
  --username USERNAME  Your Mojang account username (an email or legacy name)
  --password PASSWORD  Your Mojang account password
  --dport DPORT    The port that mcidle listens on (default=1337)

```

# TODOs

- handle `UpdateBlockEntity`
- handle gamemode changes and inventory
- test out other versions (version support)
- version number files, somehow? player shouldn't have to worry about versions messing up
- TravisCLI integration with a test suite