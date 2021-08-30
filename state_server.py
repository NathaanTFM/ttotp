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
        
        # Database Distributed Objects
        self.dbObjects = {}
        
        # We add the StateServer Object
        self.objects[20100000] = DistributedObject(20100000, self.dc.getClassByName("ObjectServer"), 0, 0)
        self.objects[20100000].update("setName", "PyOTP")
        self.objects[20100000].update("setDcHash", 798635679)
        self.objects[20100000].update("setDateCreated", int(time.time()))
        
        # CentralLogger
        self.objects[4688] = DistributedObject(4688, self.dc.getClassByName("CentralLogger"), 0, 0)

        
    def getInterested(self, do, sender):
        """
        Get channels interested in those do updates.
        In a full working otp, this should include a channel for zones.
        """
        channels = set()
        
        for senderId in do.senders:
            #print("Adding do sender channel %d to channels." % (senderId))
            channels.add(senderId)
        
        if do.parentId in self.objects:
            parent = self.objects[do.parentId]
            for parentSender in parent.senders:
                #print("Adding channel %d from parent." % (parentSender))
                channels.add(parentSender)
        
        if sender in channels:
            #print("Remove sender %d from channels." % (sender))
            channels.remove(sender)
            
        return list(channels)
        
        
    def deleteObject(self, do, sender):
        """
        Delete an object and transmits the deletion
        """
        
        # Yeah no.
        if not do:
            return
        
        # We don't have the object in either! Nothing to do here.
        if not do.doId in self.dbObjects and not do.doId in self.objects:
            #print("Tried to delete do %d that wasn't in objects anymore!" % (do.doId))
            return
            
        #print("Deleting do %d in objects!" % (do.doId))
            
        if not do.doId in self.dbObjects:
            assert self.objects[do.doId] == do, "wrong object"
            
            # We can delete the object
            del self.objects[do.doId]
        else:
            assert self.dbObjects[do.doId] == do, "wrong database object"
            
            # We can delete the object
            del self.dbObjects[do.doId]
        
        # We should tell everyone the object is gone
        # Write the delete ram packet
        dg = Datagram()
        dg.addUint32(do.doId)
        
        # We send the update to the interested OTP clients
        channels = self.getInterested(do, sender)
        # We want to reflect the delete back to the AI, 
        # Otherwise the deleted object channel in question will not be cleaned up.
        channels.append(sender)
        if channels:
            self.messageDirector.sendMessage(channels, sender, STATESERVER_OBJECT_DELETE_RAM, dg)
        
        # We announce to game clients too (through ClientAgent)
        self.clientAgent.announceDelete(do, sender)
        
        
    def handle(self, channels, sender, code, datagram):
        """
        Handle a message
        """
        for channel in channels:
            # There's an object with ID 20100000 : it's the ObjectServer.
            # That's why we need to check for object channels first
            if channel in self.objects or channel in self.dbObjects:
                di = DatagramIterator(datagram)
                if channel in self.dbObjects:
                    do = self.dbObjects[channel]
                else:
                    do = self.objects[channel]
                
                # Empty datagrams are bad for the state server, 
                # We don't have a single type that doesn't have params.
                if not di.getRemainingSize():
                    print("Datagram unexpectedly ended short!")
                    return
                
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
                    if not doId in self.dbObjects:
                        do = self.objects[doId]
                    else:
                        do = self.dbObjects[doId]
                    
                    field = do.dclass.getFieldByIndex(fieldId)
                    do.receiveField(field, di)
                    
                    # We transmit the update if it was not sent by the owner
                    channels = self.getInterested(do, sender)
                    
                    # Get our uberDog client.
                    uberDog = self.messageDirector.getUberdog()
                    
                    # We did not implement airecv fields yet so let's do it.
                    for senderId in do.senders:
                        if not senderId in channels:
                            continue
                        # Check for if the Uberdog should recieve the field,
                        if uberDog and uberDog.getPrimaryChannel() == senderId and \
                            (field.isDb() or not field.isClrecv() and not field.isClsend() and not field.isAirecv()):
                            continue
                        # If the AI isn't going to recieve it, Remove it.
                        if not field.isAirecv():
                            channels.remove(senderId)
                            
                    # Don't send it back to yourself you fucking dumbass!
                    # We don't want any of your fucking infinite loops.
                    if do.doId in channels:
                        channels.remove(do.doId)

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
                        # This is very likely a uninitalized DB object.
                        # We don't want to delete these yet as they are used
                        # for a generate in the future.
                        if do.zoneId == 0 and do.parentId == 0:
                            return
                        # It was sent directly to the object, which means it was found
                        self.deleteObject(do, sender)
                        
                    elif channel == 20100000: # Same as checking do.doId
                        # It was sent to the state server,
                        # which means the state server handles the deletion of the object
                        if doId in self.objects:
                            do = self.objects[doId]
                            # This is very likely a uninitalized DB object.
                            # We don't want to delete these yet as they are used
                            # for a generate in the future.
                            if do.zoneId == 0 and do.parentId == 0:
                                return
                            self.deleteObject(do, 20100000)
                        elif doId in self.dbObjects:
                            do = self.dbObjects[doId]
                            # This is very likely a uninitalized DB object.
                            # We don't want to delete these yet as they are used
                            # for a generate in the future.
                            if do.zoneId == 0 and do.parentId == 0:
                                return
                            self.deleteObject(do, 20100000)
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
                    prevParentChannel = self.objects[do.parentId].senders[0] if do.parentId in self.objects else None
                    prevParentId, prevZoneId = do.parentId, do.zoneId
                    
                    # We set the new zone
                    do.parentId = parentId
                    do.zoneId = zoneId
                    
                    # We announce the object was moved if it was not asked by the "owner"
                    if do.parentId in self.objects and not sender in self.objects[do.parentId].senders:
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
                                
                                self.messageDirector.sendMessage([prevParentChannel], sender, STATESERVER_OBJECT_LEAVING_AI_INTEREST, dg)
                            
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
                    
                elif channel != 20100000 and code in (STATESERVER_OBJECT_GENERATE_WITH_REQUIRED, STATESERVER_OBJECT_GENERATE_WITH_REQUIRED_OTHER):
                    # We are asked to create an object
                    parentId = di.getUint32()
                    zoneId = di.getUint32()
                    classId = di.getUint16()
                    doId = di.getUint32()
                    
                    # Get our uberDog client.
                    uberDog = self.messageDirector.getUberdog()
                    
                    if not channel in self.dbObjects:
                        # We get the dclass
                        dclass = self.dc.getClass(classId)
                        
                        # We create the object
                        do = DistributedObject(doId, dclass, parentId, zoneId)
                        do.senders.append(sender)
                        
                        #if uberDog and dclass.getName() + "UD" in self.otp.dclassesByName:
                        #    if uberDog.getPrimaryChannel() not in do.senders:
                        #        do.senders.append(uberDog.getPrimaryChannel())
                        
                        # We save the object
                        self.dbObjects[doId] = do
                    else:
                        # We update the object
                        do = self.dbObjects[channel]
                        do.parentId = parentId
                        do.zoneId = zoneId
                        do.senders.append(sender)
                        
                        #if uberDog and dclass.getName() + "UD" in self.otp.dclassesByName:
                        #    if uberDog.getPrimaryChannel() not in do.senders:
                        #        do.senders.append(uberDog.getPrimaryChannel())
                    
                        if do.doId != doId:
                            print("A generate was sent for an incorrect database object!")
                        
                    #print("Generating %s db object %d at (%d, %d)" % (do.dclass.getName(), do.doId, do.parentId, do.zoneId))
                    
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
                    #print("Announcing Create for Database Object %d with sender %d!" % (do.doId, sender))
                    self.clientAgent.announceCreate(do, sender)
                    
                elif channel == 20100000:
                    # Now we're in the case it was sent to the state server
                    
                    if code in (STATESERVER_OBJECT_GENERATE_WITH_REQUIRED, STATESERVER_OBJECT_GENERATE_WITH_REQUIRED_OTHER):
                        # We are asked to create an object
                        parentId = di.getUint32()
                        zoneId = di.getUint32()
                        classId = di.getUint16()
                        doId = di.getUint32()
                        
                        # Get our uberDog client.
                        uberDog = self.messageDirector.getUberdog()
                        
                        if not doId in self.objects:
                            # We get the dclass
                            dclass = self.dc.getClass(classId)
                            
                            # We create the object
                            do = DistributedObject(doId, dclass, parentId, zoneId)
                            do.senders.append(sender)
                            
                            #if uberDog and dclass.getName() + "UD" in self.otp.dclassesByName:
                            #    if uberDog.getPrimaryChannel() not in do.senders:
                            #        do.senders.append(uberDog.getPrimaryChannel())
                            
                            # We save the object
                            self.objects[doId] = do
                        else:
                            do = self.objects[doId]
                            do.parentId = parentId
                            do.zoneId = zoneId
                            do.senders.append(sender)
                            
                            #if uberDog and dclass.getName() + "UD" in self.otp.dclassesByName:
                            #    if uberDog.getPrimaryChannel() not in do.senders:
                            #        do.senders.append(uberDog.getPrimaryChannel())
                        
                        #print("Generating %s object %d at (%d, %d)" % (do.dclass.getName(), do.doId, do.parentId, do.zoneId))
                        
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
                        #print("Announcing Create for Object %d with sender %d!" % (do.doId, sender))
                        self.clientAgent.announceCreate(do, sender)
                        
                    elif code == STATESERVER_SHARD_REST:
                        # Shard is going down.
                        # We gotta delete its objects.
                        shardId = di.getUint64()
                        
                        # We get every object to delete,
                        # which means we look for the objects created by this shard,
                        # or every object parented to it.
                        objects = []
                        for do in self.objects.values():
                            if shardId in do.senders or (do.parentId in self.objects and shardId in self.objects[do.parentId].senders):
                                objects.append(do)

                        for do in self.dbObjects.values():
                            if shardId in do.senders or (do.parentId in self.dbObjects and shardId in self.dbObjects[do.parentId].senders):
                                objects.append(do)
                        
                        # We got all the objects, we can now delete them.
                        # The state server deletes the object, so we set the sender to 20100000.
                        for do in objects:
                            self.deleteObject(do, 20100000)
                            
                    else:
                        raise NotImplementedError("Received %d on stateserver channel" % code)
                        
                else:
                    # If the unknown packet was sent on an object channel, we raise.  
                    raise NotImplementedError("Received %d on object channel" % code)
                
                if di.getRemainingSize():
                    raise Exception("Data remaining on stateserver: code %d has %d bytes left", (code, di.getRemainingBytes()))