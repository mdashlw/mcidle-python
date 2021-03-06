from src.networking.packets.serverbound import Handshake, LoginStart, EncryptionResponse
from src.networking.packets.clientbound import EncryptionRequest, SetCompression, LoginSuccess
from src.networking.encryption import *
from src.networking.packet_handler import PacketHandler
from src.networking.packets.exceptions import InvalidPacketID

from .idle_handler import IdleHandler


class LoginHandler(PacketHandler):
    def handle(self):
        self.login()

    def on_setup(self):
        print("Switched to idling.")
        self.connection.packet_handler = IdleHandler(self.connection)
        self.connection.packet_handler.handle()

    """ Do all the authentication and logging in"""
    def setup(self):
        # Send a handshake and login start packet
        handshake = Handshake(ProtocolVersion=self.connection.protocol, ServerAddress=self.connection.address[0], \
                              ServerPort=self.connection.address[1], NextState=2)
        login_start = LoginStart(Name=self.connection.username)

        self.connection.send_packet(handshake)
        self.connection.send_packet(login_start)

        encryption_request = EncryptionRequest().read(self.read_packet_from_stream().packet_buffer)

        self.connection.VerifyToken = encryption_request.VerifyToken

        # Generate the encryption response to send over
        shared_secret = generate_shared_secret()
        (encrypted_token, encrypted_secret) = encrypt_token_and_secret(encryption_request.PublicKey,
                                                                       encryption_request.VerifyToken, shared_secret)
        encryption_response = EncryptionResponse(SharedSecret=encrypted_secret, VerifyToken=encrypted_token)

        # Generate an auth token, serverID is always empty
        server_id_hash = generate_verification_hash(encryption_request.ServerID, shared_secret,
                                                    encryption_request.PublicKey)

        # Client auth
        self.connection.auth.join(server_id_hash)

        # Send the encryption response
        self.connection.send_packet(encryption_response)

        # Enable encryption using the shared secret
        self.connection.enable_encryption(shared_secret)

        # Enable compression and set the threshold
        # We aren't sure if compression will be sent, or LoginSuccess immediately after
        unknown_packet = self.read_packet_from_stream().packet_buffer

        try:
            set_compression = SetCompression().read(unknown_packet)
            self.connection.compression_threshold = set_compression.Threshold
            print("Set compression threshold to %s" % self.connection.compression_threshold)

            self.connection.login_success = LoginSuccess().read(self.read_packet_from_stream().packet_buffer)
        except InvalidPacketID:
            print("Skipping compression..invalid compression packet")
            unknown_packet.reset_cursor()
            self.connection.compression_threshold = -1 # disabled
            self.connection.login_success = LoginSuccess().read(unknown_packet)
            return False

        return True


