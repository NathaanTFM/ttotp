from panda3d.core import Datagram, DatagramIterator
from zone_util import getCanonicalZoneId, getTrueZoneId
from msgtypes import *
import struct
import math
import os
import time 

class Client:
    def __init__(self, agent, sock, addr):
        self.agent = agent
        self.sock = sock
        self.addr = addr
        
        # Quick access for OTP
        self.otp = self.agent.otp
        self.messageDirector = self.otp.messageDirector
        self.databaseServer = self.otp.databaseServer
        self.stateServer = self.otp.stateServer
        
        # State stuff
        self.buffer = bytearray()
        self.interests = {}
        
        # Account stuff
        self.avatarId = 0
        self.account = None
        
        self.__interestCache = set()
        
        
    def onLost(self):
        pass
        
        
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
        
        msgType = di.getUint16()
        
        if msgType == CLIENT_HEARTBEAT:
            print("CLIENT_HEARTBEAT")
            
            
        elif msgType == CLIENT_CREATE_AVATAR:
            print("CLIENT_CREATE_AVATAR")
            contextId = di.getUint16()
            dnaString = di.getBlob()
            avPosition = di.getUint8()
            
            avatar = self.databaseServer.createDatabaseObject("DistributedToon")
            avatar.update("setDISLid", self.account.doId)
            avatar.update("setDNAString", dnaString)
            
            accountAvSet = self.account.fields["ACCOUNT_AV_SET"]
            accountAvSet[avPosition] = avatar.doId
            self.account.update("ACCOUNT_AV_SET", accountAvSet)
            
            datagram = Datagram()
            datagram.addUint16(contextId)
            datagram.addUint8(0) # returnCode
            datagram.addUint32(avatar.doId)
            self.sendMessage(CLIENT_CREATE_AVATAR_RESP, datagram)
            
            
        elif msgType == CLIENT_SET_NAME_PATTERN:
            print("CLIENT_SET_NAME_PATTERN")
            nameIndices = []
            nameFlags = []
            
            avId = di.getUint32()
            
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            
            avatar = self.databaseServer.loadDatabaseObject(avId)
            avatar.update("setName", "Unnamed Toon")
            
            datagram = Datagram()
            datagram.addUint32(avatar.doId)
            datagram.addUint8(0)
            self.sendMessage(CLIENT_SET_NAME_PATTERN_ANSWER, datagram)
            
            
        elif msgType == CLIENT_SET_WISHNAME:
            print("CLIENT_SET_WISHNAME")
            
            avId = di.getUint32()
            name = di.getString()
            
            if avId == 0: # Check
                datagram = Datagram()
                datagram.addUint32(0)
                datagram.addUint16(0)
                datagram.addString("")
                datagram.addString(name)
                datagram.addString("")
                
                self.sendMessage(CLIENT_SET_WISHNAME_RESP, datagram)
            
            else:
                avatar = self.databaseServer.loadDatabaseObject(avId)
                avatar.update("setName", name)
                
                datagram = Datagram()
                datagram.addUint32(avatar.doId)
                datagram.addUint16(0)
                datagram.addString("")
                datagram.addString(name)
                datagram.addString("")
                
                self.sendMessage(CLIENT_SET_WISHNAME_RESP, datagram)
                
                
        elif msgType == CLIENT_LOGIN_2:
            print("CLIENT_LOGIN_2")
            playToken = di.getString()
            serverVersion = di.getString()
            hashVal = di.getUint32()
            tokenType = di.getUint32()
            validateDownload = di.getString()
            wantMagicWords = di.getString()
            
            accFile = os.path.join("database", str(playToken) + ".txt")
            if os.path.isfile(accFile):
                with open(accFile, "r") as f:
                    self.account = self.databaseServer.loadDatabaseObject(int(f.read()))
                    
            else:
                # We create an Account
                self.account = self.databaseServer.createDatabaseObject("Account")
                with open(accFile, "w") as f:
                    f.write(str(self.account.doId))
            
            
            datagram = Datagram()
            datagram.addUint8(0) # returnCode
            datagram.addString("") # errorString
            datagram.addString(playToken) # userName - not saved in our db so we're just putting the playToken
            datagram.addUint8(1) # canChat
            
            usec, sec = math.modf(time.time())
            datagram.addUint32(int(sec))
            datagram.addUint32(int(usec * 1000000))
            
            datagram.addUint8(1) # isPaid
            datagram.addInt32(-1) # minutesRemaining
            
            datagram.addString("") # familyStr, unused
            datagram.addString("YES") # whiteListChatEnabled
            datagram.addInt32(100000) # accountDays
            datagram.addString("01/01/01 00:00")
            self.sendMessage(CLIENT_LOGIN_2_RESP, datagram)
            
            
        elif msgType == CLIENT_LOGIN_TOONTOWN:
            print("CLIENT_LOGIN_TOONTOWN")
            playToken = di.getString()
            serverVersion = di.getString()
            hashVal = di.getUint32()
            tokenType = di.getInt32()
            wantMagicWords = di.getString()
            
            accFile = os.path.join("database", str(playToken) + ".txt")
            if os.path.isfile(accFile):
                with open(accFile, "r") as f:
                    self.account = self.databaseServer.loadDatabaseObject(int(f.read()))
                    
            else:
                # We create an Account
                self.account = self.databaseServer.createDatabaseObject("Account")
                with open(accFile, "w") as f:
                    f.write(str(self.account.doId))
            
            
            datagram = Datagram()
            datagram.addUint8(0) # returnCode
            datagram.addString("") # respString (in case of error)
            datagram.addUint32(self.account.doId) # DISL ID
            datagram.addString(playToken) # accountName - not saved in our db so we're just putting the playToken
            datagram.addUint8(1) # account name approved
            datagram.addString("YES") # openChatEnabled
            datagram.addString("YES") # createFriendsWithChat
            datagram.addString("YES") # chatCodeCreationRule
            
            usec, sec = math.modf(time.time())
            datagram.addUint32(int(sec))
            datagram.addUint32(int(usec * 1000000))
            
            datagram.addString("FULL") # access
            datagram.addString("YES") # whiteListChat
            datagram.addString("01/01/01 00:00")
            datagram.addInt32(100000) # accountDays
            datagram.addString("NO_PARENT_ACCOUNT")
            datagram.addString(playToken) # userName - not saved in our db so we're just putting a placeholder
            self.sendMessage(CLIENT_LOGIN_TOONTOWN_RESP, datagram)
            
            
        elif msgType == CLIENT_DELETE_AVATAR:
            print("CLIENT_DELETE_AVATAR")
            avId = di.getUint32()
            
            accountAvSet = self.account.fields["ACCOUNT_AV_SET"]
            accountAvSet[accountAvSet.index(avId)] = 0
            self.account.update("ACCOUNT_AV_SET", accountAvSet)
            
            datagram = Datagram()
            datagram.addUint8(0)
            self.addAvatarList(datagram)
            self.sendMessage(CLIENT_DELETE_AVATAR_RESP, datagram)
            
            
            
        elif msgType == CLIENT_ADD_INTEREST:
            print("CLIENT_ADD_INTEREST")
            handle = di.getUint16()
            contextId = di.getUint32()
            parentId = di.getUint32()
            
            zones = set()
            while di.getRemainingSize():
                zoneId = di.getUint32()
                zones.add(zoneId)
                
                canonicalZoneId = getCanonicalZoneId(zoneId)

                # We add visibles
                if canonicalZoneId in self.agent.visgroups:
                    for visZoneId in self.agent.visgroups[canonicalZoneId]:
                        zones.add(getTrueZoneId(visZoneId, zoneId))
                    
                    zones.add(zoneId - zoneId % 100)
            
            #
            oldZones = ()
            
            if handle in self.interests:
                # Shit, this is an interest overwrite
                oldParentId, oldZones = self.interests[handle]
                
                del self.interests[handle]
                self.updateInterestCache()
                
                if oldParentId == parentId:
                    # We gotta disable the objects we can't see anymore,
                    for do in self.stateServer.objects.values():
                        # If the object is not visible anymore, we disable it
                        # (it's in the removed zones, but not in the new interest or any current interest)
                        if do.parentId == parentId and do.zoneId in oldZones and not (do.zoneId in zones or self.hasInterest(do.parentId, do.zoneId)):
                            dg = Datagram()
                            dg.addUint32(do.doId)
                            self.sendMessage(CLIENT_OBJECT_DISABLE, dg)
                    
                else:
                    # We gotta disable the objects we can't see anymore
                    # We only check if we're no longer interested in
                    for do in self.stateServer.objects.values():
                        if do.parentId == oldParentId and do.zoneId in oldZones and not self.hasInterest(do.parentId, do.zoneId):
                            dg = Datagram()
                            dg.addUint32(do.doId)
                            self.sendMessage(CLIENT_OBJECT_DISABLE, dg)
                
                    # We set oldZones to an empty tuple
                    oldZones = ()
                    
            # We send the newly visible objects
            newZones = []
            for zoneId in zones:
                if not zoneId in oldZones and not self.hasInterest(parentId, zoneId) and zoneId != 1:
                    newZones.append(zoneId)
                    
            self.sendObjects(parentId, newZones)
            
            self.interests[handle] = (parentId, zones)
            self.updateInterestCache()
            
            dg = Datagram()
            dg.addUint16(handle)
            dg.addUint32(contextId)
            self.sendMessage(CLIENT_DONE_INTEREST_RESP, dg)
            
            
        elif msgType == CLIENT_REMOVE_INTEREST:
            print("CLIENT_REMOVE_INTEREST")
            handle = di.getUint16()
            contextId = di.getUint32() # Might be optional
            
            oldParentId, oldZones = self.interests[handle]
            
            del self.interests[handle]
            self.updateInterestCache()
            
            for do in self.stateServer.objects.values():
                if do.parentId == oldParentId and do.zoneId in oldZones and not self.hasInterest(do.parentId, do.zoneId):
                    dg = Datagram()
                    dg.addUint32(do.doId)
                    self.sendMessage(CLIENT_OBJECT_DISABLE, dg)
            
            dg = Datagram()
            dg.addUint16(handle)
            dg.addUint32(contextId)
            self.sendMessage(CLIENT_DONE_INTEREST_RESP, dg)
            
            
        elif msgType == CLIENT_GET_AVATARS:
            print("CLIENT_GET_AVATARS")
            dg = Datagram()
            dg.addUint8(0) # returnCode
            self.addAvatarList(dg)
            self.sendMessage(CLIENT_GET_AVATARS_RESP, dg)
            
            
        elif msgType == CLIENT_SET_AVATAR:
            print("CLIENT_SET_AVATAR")
            avId = di.getUint32()
            
            if self.avatarId and avId:
                raise Exception("Double auth?")
                
            if avId:
                if not avId in self.account.fields["ACCOUNT_AV_SET"]:
                    raise Exception("Invalid avatar?")
                    
                self.avatarId = avId
                
                avatar = self.databaseServer.loadDatabaseObject(self.avatarId)
                
                # We ask STATESERVER to create our object
                dg = Datagram()
                dg.addUint32(0)
                dg.addUint32(0)
                dg.addUint16(avatar.dclass.getNumber())
                dg.addUint32(avatar.doId)
                avatar.packRequired(dg)
                avatar.packOther(dg)
                self.messageDirector.sendMessage([20100000], self.avatarId, STATESERVER_OBJECT_GENERATE_WITH_REQUIRED_OTHER, dg)
                
                # We probably should wait for an answer, but we're not threaded and everything is happening on the same script
                # (tl;dr it's blocking), so we won't.
                
                # We can send that we are the proud owner of a DistributedToon!
                dg = Datagram()
                dg.addUint32(avatar.doId)
                dg.addUint8(0)
                avatar.packRequired(dg)
                self.sendMessage(CLIENT_GET_AVATAR_DETAILS_RESP, dg)
                
            else:                
                # We ask STATESERVER to delete our object
                dg = Datagram()
                dg.addUint32(self.avatarId)
                self.messageDirector.sendMessage([self.avatarId], self.avatarId, STATESERVER_OBJECT_DELETE_RAM, dg)
                self.avatarId = 0
                
        
        elif msgType == CLIENT_OBJECT_UPDATE_FIELD:
            print("CLIENT_OBJECT_UPDATE_FIELD")
            doId = di.getUint32()
            fieldId = di.getUint16()
            
            dg = Datagram()
            dg.addUint32(doId)
            dg.addUint16(fieldId)
            dg.appendData(di.getRemainingBytes())
            
            self.messageDirector.sendMessage([doId], self.avatarId, STATESERVER_OBJECT_UPDATE_FIELD, dg)
            
            
        elif msgType == CLIENT_OBJECT_LOCATION:
            print("CLIENT_OBJECT_LOCATION")
            doId = di.getUint32()
            parentId = di.getUint32()
            zoneId = di.getUint32()
            
            dg = Datagram()
            dg.addUint32(parentId)
            dg.addUint32(zoneId)
            self.messageDirector.sendMessage([doId], self.avatarId, STATESERVER_OBJECT_SET_ZONE, dg)
            
            
        else:
            print("Received unknown message ID %d" % msgType)
            
        #else:
            #raise NotImplementedError(msgType)
            
        #if di.getRemainingSize():
            #raise Exception("remaining", di.getRemainingBytes())
            
            
    def addAvatarList(self, dg):
        dg.addUint16(sum(n != 0 for n in self.account.fields["ACCOUNT_AV_SET"])) # avatarTotal
        
        for pos, avId in enumerate(self.account.fields["ACCOUNT_AV_SET"]):
            if avId == 0:
                continue
                
            avatar = self.databaseServer.loadDatabaseObject(avId)
            
            dg.addUint32(avatar.doId) # avNum
            dg.addString(avatar.fields["setName"][0])
            dg.addString("")
            dg.addString("")
            dg.addString("")
            dg.addBlob(avatar.fields["setDNAString"][0])
            dg.addUint8(pos)
            dg.addUint8(0)
            
        
        
    def sendMessage(self, code, datagram):
        dg = Datagram()
        dg.addUint16(code)
        dg.appendData(datagram.getMessage())
        self.sendDatagram(dg)
        
        
    def sendDatagram(self, dg):
        self.sock.send(struct.pack("<H", dg.getLength()))
        self.sock.send(bytes(dg))
        
        
    def hasInterest(self, parentId, zoneId):
        if zoneId == 1:
            return False
            
        return (parentId, zoneId) in self.__interestCache
        
        """for handle in self.interests:
            handleParentId, handleZones = self.interests[handle]
            
            if handleParentId == parentId and zoneId in handleZones:
                return True
                
        return False"""
        
        
    def updateInterestCache(self):
        self.__interestCache.clear()
        
        for handle in self.interests:
            parentId, zones = self.interests[handle]
            
            for zoneId in zones:
                self.__interestCache.add((parentId, zoneId))
                
        return False
        
        
    def sendObjects(self, parentId, zones):
        objects = []
        for do in self.stateServer.objects.values():
            if do.doId == self.avatarId:
                continue
                
            if do.parentId == parentId and do.zoneId in zones:
                objects.append(do)
                
                
        objects.sort(key = lambda x: x.dclass.getNumber())
        for do in objects:
            dg = Datagram()
            dg.addUint32(do.parentId)
            dg.addUint32(do.zoneId)
            dg.addUint16(do.dclass.getNumber())
            dg.addUint32(do.doId)
            do.packRequiredBroadcast(dg)
            do.packOther(dg)
            self.sendMessage(CLIENT_CREATE_OBJECT_REQUIRED_OTHER, dg)
            
            