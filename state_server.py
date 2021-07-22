from panda3d.core import Datagram, DatagramIterator
from distributed_object import DistributedObject
from msgtypes import *
import time

class StateServer:
    def __init__(self, otp):
        # Main OTP
        self.otp = otp
        
        # DC File
        self.dc = self.otp.dc
        
        # Quick access for CA and MD 
        self.clientAgent = self.otp.clientAgent
        self.messageDirector = self.otp.messageDirector
        
        # Distributed Objects
        self.objects = {}
        
        # We add the StateServer Object
        self.objects[20100000] = DistributedObject(20100000, self.dc.getClassByName("ObjectServer"), 0, 0)
        self.objects[20100000].senderId = 0
        self.objects[20100000].update("setName", "PyOTP")
        self.objects[20100000].update("setDcHash", 798635679)
        self.objects[20100000].update("setDateCreated", int(time.time()))
        
        # CentralLogger
        self.objects[4688] = DistributedObject(4688, self.dc.getClassByName("CentralLogger"), 0, 0)
        self.objects[4688].senderId = 0
        
        
        
        
    def getInterested(self, do, sender):
        """
        TODO 
        """
        channels = set()
        
        if do.parentId in self.objects:
            channels.add(self.objects[do.parentId].senderId)
        
        if sender in channels:
            channels.remove(sender)
            
        return list(channels)
        
        
    def handle(self, channels, sender, code, datagram):
        """
        Handle a message
        """
        for channel in channels:
            # There's an object with ID 20100000 : it's the ObjectServer.
            # That's why we need to check for object channels first
            if channel in self.objects:
                di = DatagramIterator(datagram)
                do = self.objects[channel]
                
                if code == STATESERVER_QUERY_OBJECT_ALL:
                    # Someone is asking info about us
                    context = di.getUint32()
                    
                    # We're sending our REQUIRED and OTHER fields
                    dg = Datagram()
                    dg.addUint32(context)
                    dg.addUint32(do.parentId)
                    dg.addUint32(do.zoneId)
                    dg.addUint16(do.dclass.getNumber())
                    dg.addUint32(do.doId)
                    do.packRequired(dg)
                    do.packOther(dg) # TODO Should we check for airecv?
                    
                    self.messageDirector.sendMessage([sender], 20100000, STATESERVER_QUERY_OBJECT_ALL_RESP, dg)
                    
                    
                elif code == STATESERVER_OBJECT_UPDATE_FIELD:
                    # We are asked to update a field
                    doId = di.getUint32()
                    fieldId = di.getUint16()
                    
                    # Is this sent to the correct object?
                    if doId != do.doId:
                        raise Exception("Object %d does not match channel %d" % (doId, do.doId))
                        
                    # The remaining data is field data
                    data = di.getRemainingBytes()
                    
                    # We apply the update
                    do = self.objects[doId]
                    
                    field = do.dclass.getFieldByIndex(fieldId)
                    do.receiveField(field, di)
                    
                    # We transmit the update if it was not sent by the owner
                    channels = self.getInterested(do, sender)
                    
                    # We did not implement airecv fields yet so let's do it.
                    if not field.isAirecv() and do.senderId in channels:
                        channels.remove(do.senderId)
                        
                    if channels:
                        dg = Datagram()
                        dg.addUint32(doId)
                        dg.addUint16(fieldId)
                        dg.appendData(data)
                        
                        self.messageDirector.sendMessage(channels, sender, STATESERVER_OBJECT_UPDATE_FIELD, dg)
                        
                    # We announce to clients too (cause we're a ClientAgent)
                    self.clientAgent.announceUpdate(do, field, data, sender)
                    
                        
                elif code == STATESERVER_OBJECT_DELETE_RAM:
                    # We are asked to delete an object.
                    
                    # This packet can be sent to the StateServer (20100000)
                    # or the object channel.
                    
                    # We must check if doId matches, and if it doesn't,
                    # it means it was sent to the wrong channel or to the SS channel.
                    
                    doId = di.getUint32()
                    if do.doId == doId:
                        # It was sent directly to the object, which means it was found
                        dg = Datagram()
                        dg.addUint32(doId)
                        
                        channels = self.getInterested(do, sender)
                        
                        self.messageDirector.sendMessage(channels, sender, STATESERVER_OBJECT_DELETE_RAM, dg)
                        del self.objects[doId]
                        
                        # We announce to clients too (through ClientAgent)
                        self.clientAgent.announceDelete(do, sender)
                        
                    elif channel == 20100000: # Same as checking do.doId
                        if doId in self.objects:    
                            # We found the object.
                            do = self.objects[doId]
                            
                            dg = Datagram()
                            dg.addUint32(doId)
                            
                            # We must send the delete message to everyone, including
                            # the object itself. The sender will be the state server
                            channels = self.getInterested(do, 20100000)
                            
                            self.messageDirector.sendMessage(channels, 20100000, STATESERVER_OBJECT_DELETE_RAM, dg)
                            del self.objects[doId]
                            
                            # We announce to clients too (through ClientAgent)
                            self.clientAgent.announceDelete(do, sender)
                            
                        
                        else:
                            # We answer it was not found
                            dg = Datagram()
                            dg.addUint32(doId)
                            self.messageDirector.sendMessage([sender], 20100000, STATESERVER_OBJECT_NOTFOUND, dg)
                            
                    else:
                        raise Exception("Received invalid delete object message (channel %d doId %d)" % (channel, doId))
                        
                        
                elif code == STATESERVER_OBJECT_SET_ZONE:
                    # We are asked to move an object.
                    parentId = di.getUint32()
                    zoneId = di.getUint32()
                    
                    # We get the previous zone
                    prevParentChannel = self.objects[do.parentId].senderId if do.parentId in self.objects else None
                    prevParentId, prevZoneId = do.parentId, do.zoneId
                    
                    # We set the new zone
                    do.parentId = parentId
                    do.zoneId = zoneId
                    
                    # We announce the object was moved if it was not asked by the "owner"
                    if sender != self.objects[do.parentId].senderId:
                        if prevParentId == do.parentId:
                            # Parent id is the same: just send the update to the old a new zone
                            channels = self.getInterested(do, sender)
                            if channels:
                                dg = Datagram()
                                dg.addUint32(do.doId)
                                dg.addUint32(do.parentId)
                                dg.addUint32(do.zoneId)
                                dg.addUint32(prevParentId)
                                dg.addUint32(prevZoneId)
                                
                                self.messageDirector.sendMessage(channels, sender, STATESERVER_OBJECT_CHANGE_ZONE, dg)
                            
                        else:
                            # Parent id changed: we must remove it and add it back
                            if prevParentChannel:
                                dg = Datagram()
                                dg.addUint32(do.doId)
                                
                                self.messageDirector.sendMessage([prevParentChannel], sender, STATESERVER_OBJECT_DELETE_RAM, dg)
                            
                            channels = self.getInterested(do, sender)
                            if channels:
                                dg = Datagram()
                                dg.addUint32(do.parentId)
                                dg.addUint32(do.zoneId)
                                dg.addUint16(do.dclass.getNumber())
                                dg.addUint32(do.doId)
                                do.packRequired(dg)
                                do.packOther(dg) # TODO Should we check for airecv?
                                
                                self.messageDirector.sendMessage(channels, sender, STATESERVER_OBJECT_ENTERZONE_WITH_REQUIRED_OTHER, dg)
                    
                    # We announce to clients too (cause we're a ClientAgent)
                    self.clientAgent.announceMove(do, prevParentId, prevZoneId, sender)
                    
                    
                elif channel == 20100000:
                    # Now we're in the case it was sent to the state server
                    
                    if code in (STATESERVER_OBJECT_GENERATE_WITH_REQUIRED, STATESERVER_OBJECT_GENERATE_WITH_REQUIRED_OTHER):
                        # We are asked to create an object
                        parentId = di.getUint32()
                        zoneId = di.getUint32()
                        classId = di.getUint16()
                        doId = di.getUint32()
                        
                        # We get the dclass
                        dclass = self.dc.getClass(classId)
                        
                        # We create the object
                        do = DistributedObject(doId, dclass, parentId, zoneId)
                        do.senderId = sender
                        
                        # We save the object
                        self.objects[doId] = do
                        
                        # We update the object
                        do.receiveRequired(di)
                        if code == STATESERVER_OBJECT_GENERATE_WITH_REQUIRED_OTHER:
                            do.receiveOther(di)
                            
                        # We announce the object was created if it was not created by the owner.
                        channels = self.getInterested(do, sender)
                        
                        if channels:
                            dg = Datagram()
                            dg.addUint32(do.parentId)
                            dg.addUint32(do.zoneId)
                            dg.addUint16(do.dclass.getNumber())
                            dg.addUint32(do.doId)
                            do.packRequired(dg)
                            do.packOther(dg) # TODO Should we check for airecv?
                            
                            self.messageDirector.sendMessage(channels, sender, STATESERVER_OBJECT_ENTERZONE_WITH_REQUIRED_OTHER, dg)
                            
                        # We announce to clients too (cause we're a ClientAgent)
                        self.clientAgent.announceCreate(do, sender)
                        
                        
                    else:
                        raise NotImplementedError("Received %d on stateserver channel" % code)
                        
                else:
                    # If the unknown packet was sent on an object channel, we raise.  
                    raise NotImplementedError("Received %d on object channel" % code)
                
                if di.getRemainingSize():
                    raise Exception("Data remaining on stateserver: code %d has %d bytes left", (code, di.getRemainingBytes()))
                