from panda3d.core import Datagram, Filename
from dnaparser import loadDNAFile, DNAStorage
from msgtypes import *
import socket
import time
import ssl


class ClientAgent:
    def __init__(self, otp):
        # Main OTP
        self.otp = otp
        
        # DC File
        self.dc = self.otp.dc
        
        # GameServer Sock
        sock = socket.socket()
        sock.bind(("0.0.0.0", 6667))
        sock.listen(5)
        
        # SSL Context
        #context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        #context.load_cert_chain('server.cert', 'server.key')

        # GameServer sock and clients
        self.sock = sock #context.wrap_socket(sock, server_side=True)
        self.clients = []
        
        # Every DNA file with visgroups. We don't care about all of them.
        dnaFiles = [
            "cog_hq_cashbot_sz.dna",
            "cog_hq_lawbot_sz.dna",
            "cog_hq_sellbot_11200.dna",
            "cog_hq_sellbot_sz.dna",
            "daisys_garden_5100.dna",
            "daisys_garden_5200.dna",
            "daisys_garden_5300.dna",
            #"daisys_garden_sz.dna",
            "donalds_dock_1100.dna",
            "donalds_dock_1200.dna",
            "donalds_dock_1300.dna",
            #"donalds_dock_sz.dna",
            "donalds_dreamland_9100.dna",
            "donalds_dreamland_9200.dna",
            #"donalds_dreamland_sz.dna",
            #"estate_1.dna",
            #"golf_zone_sz.dna",
            #"goofy_speedway_sz.dna",
            "minnies_melody_land_4100.dna",
            "minnies_melody_land_4200.dna",
            "minnies_melody_land_4300.dna",
            #"minnies_melody_land_sz.dna",
            #"outdoor_zone_sz.dna",
            #"party_sz.dna",
            "the_burrrgh_3100.dna",
            "the_burrrgh_3200.dna",
            "the_burrrgh_3300.dna",
            #"the_burrrgh_sz.dna",
            "toontown_central_2100.dna",
            "toontown_central_2200.dna",
            "toontown_central_2300.dna",
            #"toontown_central_sz.dna",
            #"tutorial_street.dna"
        ]
        
        # We cache the visgroups
        self.visgroups = {}
        dnaStore = DNAStorage()
        
        for filename in dnaFiles:
            loadDNAFile(dnaStore, Filename("dna", filename))
            
        for visgroup in dnaStore.visGroups:
            self.visgroups[int(visgroup.name)] = [int(i) for i in visgroup.visibles]
            
        # We read the NameMaster
        self.nameDictionary = {}
        with open("../toontown/src/configfiles/NameMasterEnglish.txt", "r") as file:
            for line in file:
                if line.startswith("#"):
                    continue
                    
                nameId, nameCategory, name = line.split("*", 2)
                self.nameDictionary[int(nameId)] = (int(nameCategory), name.strip())
                
        # Special fields IDs (cache)
        self.setTalkFieldId = self.dc.getClassByName("TalkPath_owner").getFieldByName("setTalk").getNumber()
        
            
    def announceCreate(self, do, sender):
        # We send to the interested clients that they have access to a brand new object!
        dg = Datagram()
        dg.addUint32(do.parentId)
        dg.addUint32(do.zoneId)
        dg.addUint16(do.dclass.getNumber())
        dg.addUint32(do.doId)
        do.packRequiredBroadcast(dg)
        do.packOther(dg)
        
        for client in self.clients:
            # No echo pls
            if client.avatarId == sender:
                continue
                
            # We send the object creation if we're the owner or if we're interested.
            if client.hasInterest(do.parentId, do.zoneId) or do.doId == client.avatarId:
                client.sendMessage(CLIENT_CREATE_OBJECT_REQUIRED_OTHER, dg)
        
        
    def announceDelete(self, do, sender):
        # We're deleting an object
        dg = Datagram()
        dg.addUint32(do.doId)
        
        for client in self.clients:
            # Not retransmitting
            if client.avatarId == sender:
                continue
                
            # If the client is the owner, we're in a special case and we're not sending the packet
            if do.doId == client.avatarId:
                client.onAvatarDelete()
            
            # We tell the client that it's disabled only if they're interested or the owner.
            # (Please note this last condition here is useless but it's meant to be replaced if owner view is implemented some day)
            elif client.hasInterest(do.parentId, do.zoneId) or do.doId == client.avatarId:
                client.sendMessage(CLIENT_OBJECT_DISABLE, dg)
        
        
    def announceMove(self, do, prevParentId, prevZoneId, sender):
        """
        Send CLIENT_OBJECT_LOCATION to interested clients,
        or CLIENT_OBJECT_DISABLE / CLIENT_CREATE_OBJECT_REQUIRED_OTHER
        """
        # Disable Message
        dg1 = Datagram()
        dg1.addUint32(do.doId)
        
        # Location Message
        dg2 = Datagram()
        dg2.addUint32(do.doId)
        dg2.addUint32(do.parentId)
        dg2.addUint32(do.zoneId)
        
        # Create Object Message
        dg3 = Datagram()
        dg3.addUint32(do.parentId)
        dg3.addUint32(do.zoneId)
        dg3.addUint16(do.dclass.getNumber())
        dg3.addUint32(do.doId)
        do.packRequiredBroadcast(dg3)
        do.packOther(dg3)
        
        for client in self.clients:
            # We are not transmitting back our own updates
            if client.avatarId == sender:
                continue
                
            # If we're the owner, we must receive it in any case
            if client.avatarId == do.doId:
                client.sendMessage(CLIENT_OBJECT_LOCATION, dg2)
                
            # If we're interested in the previous area
            elif client.hasInterest(prevParentId, prevZoneId):
                # If we're interested in the new area,
                # we can just tell the client that the object moved
                if client.hasInterest(do.parentId, do.zoneId):
                    client.sendMessage(CLIENT_OBJECT_LOCATION, dg2)
                else:   
                    # If we're not, we ask them to disable the object
                    client.sendMessage(CLIENT_OBJECT_DISABLE, dg1)
                    
            # If we're only interested in the new area,
            # we ask them to create the object
            elif client.hasInterest(do.parentId, do.zoneId):
                client.sendMessage(CLIENT_CREATE_OBJECT_REQUIRED_OTHER, dg3)
                
                
    def announceUpdate(self, do, field, data, sender):
        """
        Send CLIENT_OBJECT_UPDATE_FIELD to interested clients
        """
        # This field has no reason to be transmitted if it's not ownrecv or broadcast
        if not (field.isOwnrecv() or field.isBroadcast()):
            return
            
        # We generate the field update
        dg = Datagram()
        dg.addUint32(do.doId)
        dg.addUint16(field.getNumber())
        dg.appendData(data)
        
        for client in self.clients:
            # We are not transmitting back our own updates
            if client.avatarId == sender:
                continue
                
            # Can this client receive this update?
            # TODO: is broadcast check required?
            if (field.isOwnrecv() or not field.isBroadcast()) and client.avatarId != do.doId:
                continue
                
            # If we're interested OR owner, we send the update
            if client.hasInterest(do.parentId, do.zoneId) or client.avatarId == do.doId:
                client.sendMessage(CLIENT_OBJECT_UPDATE_FIELD, dg)
                
        
    def handle(self, channels, sender, code, datagram):
        """
        Handle a message
        """
        for channel in channels:
            for client in self.clients:
                if client.avatarId is None:
                    continue
                    
                if channel == client.avatarId + (1 << 32):
                    if code == STATESERVER_OBJECT_UPDATE_FIELD:
                        client.sendMessage(CLIENT_OBJECT_UPDATE_FIELD, datagram)
                    else:
                        raise Exception("Unexpected message on Puppet channel (code %d)" % code)
                        
                        