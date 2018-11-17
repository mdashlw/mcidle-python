import socket, select
import time
info = socket.getaddrinfo("localhost", 25565,
                          0, socket.SOCK_STREAM)


# Prefer to use IPv4 (for backward compatibility with previous
# versions that always resolved hostnames to IPv4 addresses),
# then IPv6, then other address families.
def key(ai):
    return 0 if ai[0] == socket.AF_INET else \
        1 if ai[0] == socket.AF_INET6 else 2


ai_faml, ai_type, ai_prot, _ai_cnam, ai_addr = min(info, key=key)

ssocket = socket.socket(ai_faml, ai_type, ai_prot)
ssocket.settimeout(15)
print(ai_addr)
ssocket.connect(ai_addr)

from src.networking.packets.serverbound import *

time.sleep(3)

ssocket.send(Handshake(ProtocolVersion=316, ServerAddress="localhost", ServerPort=25565, NextState=2).write().buffer.get_bytes())
print(Handshake(ProtocolVersion=316, ServerAddress="localhost", ServerPort=25565, NextState=2).write())
ssocket.send(LoginStart(Name="leddit").write().buffer.get_bytes())
print(LoginStart(Name="leddit").write())

file_object = ssocket.makefile("rb", 0)

ready_to_read = select.select([file_object], [], [], 0.05)[0]

if ready_to_read:
    byte = ssocket.recv(1024)
    if len(byte) > 0:
        print("Got data", byte)

ssocket.close()
