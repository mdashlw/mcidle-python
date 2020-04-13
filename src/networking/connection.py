import socket
import threading
import traceback

from .auth import Auth
from src.networking.encryption import *
from src.networking.packet_handler.serverbound import LoginHandler as ServerboundLoginHandler
from src.networking.packet_handler.clientbound import LoginHandler as ClientboundLoginHandler

from src.networking.packet_handler import PacketLogger


class Connection(threading.Thread):
    def __init__(self, ip=None, port=None):
        threading.Thread.__init__(self)
        self.threshold = None
        self.address = (ip, port)
        self.packet_handler = None
        self.running = False

        self.socket = None
        self.stream = None

        self.compression_threshold = None

        self.initialize_socket(socket.socket())

    def initialize_socket(self, sock):
        self.socket = sock
        """ Create a read only blocking file interface (stream) for the socket """
        self.stream = self.socket.makefile('rb')

    def destroy_socket(self):
        try:
            self.socket.close()
            self.socket = None
            self.stream = None
            print("Socket shutdown and closed.")
        except OSError:
            print("Failed to reset socket")
            pass

    def enable_encryption(self, shared_secret):
        cipher = create_AES_cipher(shared_secret)
        # Generate the encrypted endpoints
        encryptor = cipher.encryptor()
        decryptor = cipher.decryptor()

        # Replace the socket used with an encrypted socket
        self.socket = EncryptedSocketWrapper(self.socket, encryptor, decryptor)
        self.stream = EncryptedFileObjectWrapper(self.stream, decryptor)

    def initialize_connection(self):
        pass

    # We need this to stop reading packets from the dead stream
    # which halts the wait thread
    def on_disconnect(self):
        self.running = False
        self.destroy_socket()

    def send_packet(self, packet):
        self.socket.send(packet.write(self.compression_threshold).bytes)

    def send_packet_buffer(self, packet_buffer):
        self.socket.send(packet_buffer.bytes)

    def run(self):
        self.initialize_connection()
        if self.packet_handler is not None:
            if self.packet_handler.setup():
                self.running = True
                self.packet_handler.on_setup()
                self.packet_handler.handle()


class MinecraftConnection(Connection):
    def __init__(self, username, ip, protocol, port=25565, server_port=1001, profile=None):
        super().__init__(ip, port)

        self.username = username
        self.protocol = protocol
        self.server = None
        self.server_port = server_port

        self.held_item_slot = 0
        self.last_pos_packet = None
        self.last_yaw = 0
        self.last_pitch = 0

        self.client_connection = None

        self.auth = Auth(username, profile)

        # Make sure the access token we are using is still valid
        self.auth.validate()

        self.packet_handler = ServerboundLoginHandler(self)

        """ JoinGame, ServerDifficulty, SpawnPosition, PlayerAbilities, Respawn """
        self.join_ids = []
        self.packet_logger = PacketLogger(self) # Logs incoming packets in another thread
        self.packet_logger.start_worker_threads()

    """ Connect to the socket and start a connection thread """
    def connect(self):
        self.socket.connect(self.address)
        print("Connected", flush=True)

    def initialize_connection(self):
        self.connect()
        # Should we wait here or is this blocking?
        self.start_server()

    def start_server(self):
        # Override the old server interface
        self.server = MinecraftServer(self, self.server_port)
        self.server.start() # Start main thread

    """ Connect to the socket and start a connection thread """
    def connect(self):
        self.socket.connect(self.address)
        print("Connected", flush=True)


class MinecraftServer(Connection):
    """ Used for listening on a port for a connection """
    def __init__(self, mc_connection, port=25565):
        super().__init__('localhost', port)
        self.mc_connection = mc_connection
        self.packet_handler = ClientboundLoginHandler(self, mc_connection)
        self.teleport_id = 2 # TODO: remove this and use a state wrapper

    def on_disconnect(self):
        print("Called MinecraftServer::on_disconnect()...")
        super().on_disconnect()
        if self.mc_connection:
            self.mc_connection.start_server()

    """ Bind to a socket and wait for a client to connect """
    def initialize_connection(self):
        try:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(self.address)
            print("Waiting for client")
            self.socket.listen(1) # Listen for 1 incoming connection

            (connection, address) = self.socket.accept()

            # Replace the server socket with the client's socket
            # Maybe this is a bad idea because of race conditions
            self.initialize_socket(connection)
        except OSError as e:
            traceback.print_exc()
            import time
            print("Failed to bind socket (race condition?), it's already on")
