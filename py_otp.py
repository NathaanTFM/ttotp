from panda3d.core import Filename
from panda3d.direct import DCFile

from message_director import MessageDirector, MDClient
from state_server import StateServer
from client_agent import ClientAgent
from client import Client
from database_server import DatabaseServer

import socket
import select

class PyOTP:
    def __init__(self):
        # Every socket client (makes the code faster)
        self.clients = {}
        
        # DC File
        self.dc = DCFile()
        self.dc.read(Filename("otp.dc"))
        self.dc.read(Filename("toon.dc"))
        
        # "Handlers"
        self.messageDirector = MessageDirector(self)
        self.clientAgent = ClientAgent(self)
        self.stateServer = StateServer(self)
        self.databaseServer = DatabaseServer(self)
        
        
    def handleMessage(self, channels, sender, code, datagram):
        """
        Transmit a received message from MD to SS, CA and DBSS
        """
        self.stateServer.handle(channels, sender, code, datagram)
        self.clientAgent.handle(channels, sender, code, datagram)
        self.databaseServer.handle(channels, sender, code, datagram)
        
        
    def flush(self):
        """
        Do some socket magic
        """
        # TODO: use socketserver or something different.
        # We are very limited by select here
        
        r, w, x = select.select([self.messageDirector.sock, self.clientAgent.sock] + list(self.clients), [], [], 0)
        for sock in r:
            if sock == self.messageDirector.sock:
                sock, addr = sock.accept()
                self.clients[sock] = MDClient(self.messageDirector, sock, addr)
                self.messageDirector.clients.append(self.clients[sock])
                
            elif sock == self.clientAgent.sock:
                sock, addr = sock.accept()
                self.clients[sock] = Client(self.clientAgent, sock, addr)
                self.clientAgent.clients.append(self.clients[sock])
                
            else:
                client = self.clients[sock]
                try:
                    data = sock.recv(2048)
                except socket.error:
                    data = None
                    
                if not data:
                    client.onLost()
                    del self.clients[sock]
                    
                    if type(client) == MDClient:
                        self.messageDirector.clients.remove(client)
                        
                    elif type(client) == Client:
                        self.clientAgent.clients.remove(client)
                    
                else:
                    client.onData(data)
                    
                    

if __name__ == "__main__":
    otp = PyOTP()
    
    while True:
        otp.flush()