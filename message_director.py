from panda3d.core import Datagram, DatagramIterator
from msgtypes import *

import socket
import struct

class MDClient:
    def __init__(self, md, sock, addr):
        self.md = md
        self.sock = sock
        self.addr = addr
        
        # Quick access to OTP
        self.otp = self.md.otp
        
        self.buffer = bytearray()
        
        self.connectionName = ""
        self.connectionURL = ""
        self.channels = set()
        self.postRemove = []

    def onLost(self):
        for x in self.postRemove:
            self.onDatagram(Datagram(x))

    def onData(self, data):
        self.buffer += data
        while len(self.buffer) >= 2:
            length = struct.unpack("<H", self.buffer[:2])[0]
            if len(self.buffer) < length+2:
                break
                
            packet = self.buffer[2:length+2]
            self.buffer = self.buffer[length+2:]
        
            self.onDatagram(Datagram(bytes(packet)))

    def onDatagram(self, dg):
        di = DatagramIterator(dg)
        
        # First check if the datagram has anything in it.
        if not di.getRemainingSize() >= 1:
            print("Recieved Datagram was truncated!")
            return
        
        count = di.getUint8()
        
        channels = []
        for _ in range(count):
            # Check each loop to make sure we don't run out of size.
            # We can't have a size less then 8, Because that's how big
            # a 64 bit integer is at minimum.
            if not di.getRemainingSize() >= 8:
                print("Recieved Datagram was truncated!")
                return
            channel = di.getUint64()
            channels.append(channel)
        
        if count == 1 and channel == CONTROL_MESSAGE:
            code = di.getUint16()
            
            if code == CONTROL_SET_CHANNEL:
                channel = di.getUint64()
                self.channels.add(channel)
                
            elif code == CONTROL_REMOVE_CHANNEL:
                channel = di.getUint64()
                self.channels.remove(channel)
                
            elif code == CONTROL_ADD_POST_REMOVE:
                message = di.getBlob()
                self.postRemove.append(message)
                
            elif code == CONTROL_SET_CON_NAME:
                self.connectionName = di.getString()
                
            elif code == CONTROL_SET_CON_URL:
                self.connectionURL = di.getString()

            else:
                raise NotImplementedError("CONTROL_MESSAGE", code)
            
            print(self.connectionName, self.connectionURL, self.channels)
            
        else:
            sender = di.getUint64()
            code = di.getUint16()
            
            for client in self.md.clients:
                # We're not sending back our messages
                if client == self:
                    continue
                    
                if client.channels.intersection(channels):
                    client.sendDatagram(dg)

            # We send this message to OTP
            self.otp.handleMessage(channels, sender, code, Datagram(di.getRemainingBytes()))
            
    def isUberdog(self):
        return self.connectionName == "UberDog"
        
    def getPrimaryChannel(self):
        return list(self.channels)[0]

    def sendDatagram(self, dg):
        self.sock.send(struct.pack("<H", dg.getLength()))
        self.sock.send(bytes(dg))

class MessageDirector:
    def __init__(self, otp):
        # Main OTP
        self.otp = otp
        
        # MD Sock
        self.sock = socket.socket()
        self.sock.bind(("0.0.0.0", 6666))
        self.sock.listen(5)
        
        # MD Clients
        self.clients = []
        
    def getUberdog(self):
        for client in self.clients:
            if client.isUberdog():
                return client
        
        return None

    def sendMessage(self, channels, sender, code, datagram):
        """
        Send a message to MD
        """
        # We generate the message
        dg = Datagram()
        dg.addUint8(len(channels))
        for channel in channels:
            dg.addUint64(channel)
            
        dg.addUint64(sender)
        dg.addUint16(code)
        dg.appendData(datagram.getMessage())
        
        # We send the message to any listening
        for client in self.clients:
            if client.channels.intersection(channels):
                client.sendDatagram(dg)
        
        # Now we send this message to OTP
        # Please note we technically shouldn't transmit
        # to the handlers their own messages, but in this case
        # they know what they're doing. We'll fix this later. TODO
        self.otp.handleMessage(channels, sender, code, datagram)
        
        