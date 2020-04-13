from src.networking.packet_handler import PacketHandler
from src.networking.packets.serverbound import Handshake, LoginStart, EncryptionResponse, ClientStatus, \
    PlayerPositionAndLook
from src.networking.packets.clientbound import EncryptionRequest, SetCompression, SpawnEntity, ChunkData, \
    TimeUpdate, HeldItemChange, PlayerListItem
from src.networking.packets.clientbound import PlayerPositionAndLook as PlayerPositionAndLookClientbound

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.padding import PKCS1v15

import select

class LoginHandler(PacketHandler):
    def __init__(self, connection, mc_connection):
        super().__init__(connection)
        self.mc_connection = mc_connection

    def handle_held_item_change(self, packet):
        if packet.id != HeldItemChange.id:
            return

        self.mc_connection.held_item_slot = HeldItemChange().read(packet.packet_buffer).Slot

    def handle_position(self, packet):
        if packet.id != PlayerPositionAndLook.id:
            return

        pos_packet = PlayerPositionAndLook().read(packet.packet_buffer)
        self.mc_connection.last_yaw = pos_packet.Yaw
        self.mc_connection.last_pitch = pos_packet.Pitch
        self.mc_connection.last_pos_packet = pos_packet

        # Replace the currently logged PlayerPositionAndLookClientbound packet
        self.mc_connection.last_pos_packet = pos_packet

    def send_packet_dict(self, id_):
        if id_ in self.mc_connection.packet_logger.log:
            packet_dict = self.mc_connection.packet_logger.log[id_]
            for packet in packet_dict.values():
                self.connection.send_packet_buffer(packet.compressed_buffer)

    def join_world(self):
        # Send the player all the packets that lets them join the world
        for id_ in self.mc_connection.join_ids:
            if id_ in self.mc_connection.packet_logger.log:
                packet = self.mc_connection.packet_logger.log[id_]
                self.connection.send_packet_buffer(packet.compressed_buffer)

        # Send them their last position/look if it exists
        if PlayerPositionAndLookClientbound.id in self.mc_connection.packet_logger.log:
            if self.mc_connection and self.mc_connection.last_pos_packet:
                last_packet = self.mc_connection.last_pos_packet

                pos_packet = PlayerPositionAndLookClientbound( \
                    X=last_packet.X, Y=last_packet.Y, Z=last_packet.Z, \
                    Yaw=self.mc_connection.last_yaw, Pitch=self.mc_connection.last_pitch, Flags=0)
                self.connection.send_packet(pos_packet)
            else:
                self.connection.send_packet_buffer(
                    self.mc_connection.packet_logger.log[PlayerPositionAndLookClientbound.id] \
                        .compressed_buffer)  # Send the last packet that we got

        # if TimeUpdate.id in self.mc_connection.packet_logger.log:
        #     self.connection.send_packet(self.mc_connection.packet_logger.log[TimeUpdate.id])

        # Send the player list items (to see other players)
        self.send_packet_dict(PlayerListItem.id)

        # Send all loaded chunks
        print("Sending chunks")
        self.send_packet_dict(ChunkData.id)
        print("Done sending chunks")

        # Send the player all the currently loaded entities
        self.send_packet_dict(SpawnEntity.id)

        # Player sends ClientStatus, this is important for respawning if died
        self.mc_connection.send_packet(ClientStatus(ActionID=0))

        # Send their last held item
        self.connection.send_packet(HeldItemChange(Slot=self.mc_connection.held_item_slot))

    def setup(self):
        print("Reading handshake")
        Handshake().read(self.read_packet_from_stream().packet_buffer)
        print("Reading login start")
        LoginStart().read(self.read_packet_from_stream().packet_buffer)

        # Generate a dummy (pubkey, privkey) pair
        privkey = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
        pubkey = privkey.public_key().public_bytes(encoding=serialization.Encoding.DER,
                                                   format=serialization.PublicFormat.SubjectPublicKeyInfo)
        self.connection.send_packet(
            EncryptionRequest(ServerID='', PublicKey=pubkey, VerifyToken=self.mc_connection.VerifyToken))

        # The encryption response will be encrypted with the server's public key
        # Luckily, when this goes wrong read_packet returns None
        _ = self.read_packet_from_stream()

        if _ is None:
            print("Invalid packet!")
            self.connection.on_disconnect()
            return False

        encryption_response = EncryptionResponse().read(_.packet_buffer)

        # Decrypt and verify the verify token
        verify_token = privkey.decrypt(encryption_response.VerifyToken, PKCS1v15())
        assert (verify_token == self.mc_connection.VerifyToken)

        # Decrypt the shared secret
        shared_secret = privkey.decrypt(encryption_response.SharedSecret, PKCS1v15())

        # Enable encryption using the shared secret
        self.connection.enable_encryption(shared_secret)

        # Enable compression and assign the threshold to the connection
        if self.mc_connection.compression_threshold >= 0:
            self.connection.send_packet(SetCompression(Threshold=self.mc_connection.compression_threshold))
            self.connection.compression_threshold = self.mc_connection.compression_threshold

        self.connection.send_packet(self.mc_connection.login_success)

        print("Joining world")
        self.join_world()
        print("Finished joining world")

        # Let the real connection know about our client
        self.mc_connection.client_connection = self.connection

        return True

    # We need to switch to another handler here instead
    # This runs in the connection thread
    def handle(self):
        while self.connection.running:
            ready_to_read = select.select([self.connection.stream], [], [], self._timeout)[0]

            if ready_to_read:
                packet = self.read_packet_from_stream()

                if packet is not None:
                    self.handle_position(packet)
                    self.handle_held_item_change(packet)
                    self.mc_connection.send_packet_buffer(packet.compressed_buffer)
                else:
                    print("DCed? Exiting thread")
                    self.connection.on_disconnect()
                    break

