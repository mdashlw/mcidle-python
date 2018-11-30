from .packet_buffer import PacketBuffer
from src.networking.types import VarInt
from zlib import compress
from base64 import b64encode


class Packet:
    id = None
    definition = None

    def __init__(self, **kwargs):
        self.packet_buffer_ = PacketBuffer()
        self.assert_fields(**kwargs)
        self.set_fields(**kwargs)

    def set_fields(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    @property
    def bytes(self):
        return self.packet_buffer_.bytes

    @property
    def packet_buffer(self):
        return self.packet_buffer_

    def clear(self):
        self.packet_buffer_ = PacketBuffer()

    @property
    def buffer(self):
        return self.packet_buffer_

    """ Ensure that the fields match the packet's definition """
    def assert_fields(self, **kwargs):
        assert not kwargs or not self.definition or set(kwargs.keys()) == set(self.definition.keys()), "Packet fields do not match definition!"

    """ Read from the packet buffer into the packet's fields """
    def read(self, packet_buffer):
        assert(VarInt.read(packet_buffer) == self.id)
        for var_name, data_type in self.definition.items():
            val = data_type.read(packet_buffer)
            setattr(self, var_name, val)

        self.packet_buffer_ = packet_buffer
        self.packet_buffer.reset_cursor()

        return self

    def write(self, compression_threshold=None):
        if self.id is None:
            raise AttributeError("Packet ID is undefined.")

        if len(self.bytes) > 0:
            self.clear() # If we re-use packets we need to clear past byte data

        data_length = 0
        """ Create a temporary PacketBuffer """
        packet_buffer = PacketBuffer()
        """ Write the packet id """
        data_length += VarInt.write(self.id, packet_buffer)
        """ Write the data fields """
        data_length += self.__write_fields(packet_buffer)

        """ Apply compression if needed """
        if compression_threshold:
            self.__write_compressed(packet_buffer, data_length, data_length >= compression_threshold)
            return self

        """ Uncompressed packet """
        VarInt.write(data_length, self.packet_buffer_) # Write the packet length
        self.packet_buffer_.write(packet_buffer.bytes) # Write the data
        return self

    """ Write the compressed packet to the buffer """
    def __write_compressed(self, packet_buffer, data_length, is_compressed):
        actual_data_length = 0
        data = packet_buffer.bytes

        if is_compressed:
            data = compress(data)
            actual_data_length = VarInt.write(data_length, PacketBuffer()) + len(data)

        # Clear the last packet buffer to be overwritten
        packet_buffer.clear()

        packet_length = VarInt.write(actual_data_length, PacketBuffer()) + len(data)

        VarInt.write(packet_length, self.packet_buffer_)
        VarInt.write(actual_data_length, self.packet_buffer_)
        self.packet_buffer_.write(data)

    def __write_fields(self, packet_buffer):
        length = 0
        for var_name, data_type in self.definition.items():
            """ Get the field's data """
            data = getattr(self, var_name)
            length += data_type.write(data, packet_buffer)
        return length

    def field_string(self, field):
        """ The string representation of the value of the given named field
            of this packet. Override to customise field value representation.
        """
        value = getattr(self, field, None)

        # Byte arrays are represented in base64
        if isinstance(value, bytes) or isinstance(value, bytearray):
            return b64encode(value).decode("utf-8")

        return repr(value)

    @property
    def fields(self):
        """ An iterable of the names of the packet's fields, or None. """
        if self.definition is None:
            return None
        return self.definition.keys()

    def __str__(self):
        _str = type(self).__name__
        if self.id is not None:
            _str = '0x%02X %s' % (self.id, _str)
        fields = self.fields
        if fields is not None:
            _str = '%s(%s)' % (_str, ', '.join('%s=%s' %
                                               (k, self.field_string(k)) for k in fields))
        _str += " | " + str(self.packet_buffer_)
        return _str

    def __repr__(self):
        return str(self)
