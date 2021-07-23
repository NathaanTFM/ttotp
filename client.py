from panda3d.core import Datagram, DatagramIterator
from panda3d.direct import DCPacker
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

        # Cache for interests, so we don't have to iterate through all interests
        # every time an object updates.
        # This could be optimized in other languages, but we're using Python so
        # we're just gonna use a set
        self.__interestCache = set()

    def onLost(self):
        # We remove the avatar if we're disconnecting. Bye!
        if self.avatarId:
            self.chooseAvatar(0)


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
            pass # The client is alive, neat.

        elif msgType == CLIENT_CREATE_AVATAR:
            # Client wants to create an avatar

            # We read av info
            contextId = di.getUint16()
            dnaString = di.getBlob()
            avPosition = di.getUint8()

            # Is avPosition valid?
            if not 0 <= avPosition < 6:
                raise Exception("Client sent an invalid av position")

            # Doesn't it already have an avatar at this slot?
            accountAvSet = self.account.fields["ACCOUNT_AV_SET"]

            if accountAvSet[avPosition]:
                raise Exception("Client tried to overwrite an avatar")

            # We can create the avatar
            avatar = self.databaseServer.createDatabaseObject("DistributedToon")
            avatar.update("setDISLid", self.account.doId)
            avatar.update("setDNAString", dnaString)

            # We save the avatar in the account
            accountAvSet[avPosition] = avatar.doId
            self.account.update("ACCOUNT_AV_SET", accountAvSet)

            # We tell the client their new avId!
            datagram = Datagram()
            datagram.addUint16(contextId)
            datagram.addUint8(0) # returnCode
            datagram.addUint32(avatar.doId)
            self.sendMessage(CLIENT_CREATE_AVATAR_RESP, datagram)


        elif msgType == CLIENT_SET_NAME_PATTERN:
            # Client sets his name
            # We may only allow this if we don't already have a name,
            # or only have a default name.

            # But for now, we don't care. TODO
            if not self.account:
                raise Exception("Client has no account")

            nameIndices = []
            nameFlags = []

            avId = di.getUint32()
            if not avId in self.account.fields["ACCOUNT_AV_SET"]:
                raise Exception("Client sets the name of another Toon")

            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())
            nameIndices.append(di.getInt16())
            nameFlags.append(di.getInt16())

            # TODO: Check if the name is valid (incl KeyError)
            # King King KingKing is NOT a valid name.

            name = ""
            for index in range(4):
                indice, flag = nameIndices[index], nameFlags[index]
                if indice != -1:
                    namePartType, namePart = self.agent.nameDictionary[indice]
                    if flag:
                        namePart = namePart.capitalize()

                    # %s %s %s%s
                    if index != 3:
                        name += " "

                    name += namePart

            # We set the toon's name
            avatar = self.databaseServer.loadDatabaseObject(avId)
            avatar.update("setName", name.strip())

            # We tell the client that their new name is accepted
            datagram = Datagram()
            datagram.addUint32(avatar.doId)
            datagram.addUint8(0)
            self.sendMessage(CLIENT_SET_NAME_PATTERN_ANSWER, datagram)


        elif msgType == CLIENT_SET_WISHNAME:
            # Client sets his name
            # We may only allow this if we don't already have a name,
            # or only have a default name.

            # But for now, we don't care. TODO
            if not self.account:
                raise Exception("Client has no account")

            avId = di.getUint32()
            if avId and not avId in self.account.fields["ACCOUNT_AV_SET"]:
                raise Exception("Client sets the name of another Toon")

            name = di.getString()

            if avId == 0:
                # Client just wants to check the name
                datagram = Datagram()
                datagram.addUint32(0)
                datagram.addUint16(0)
                datagram.addString("")
                datagram.addString(name)
                datagram.addString("")

                self.sendMessage(CLIENT_SET_WISHNAME_RESP, datagram)

            else:
                # Client wants to set the name and we're just gonna
                # allow him to.
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
            # Client wants to delete one of his avatars.
            # That's sad but let it be.
            avId = di.getUint32()

            # Is that even our avatar?
            accountAvSet = self.account.fields["ACCOUNT_AV_SET"]
            if not avId in accountAvSet:
                raise Exception("Client tries to delete an avatar it doesnt own!")

            # We remove the avatar
            accountAvSet[accountAvSet.index(avId)] = 0
            self.account.update("ACCOUNT_AV_SET", accountAvSet)

            # We tell him it's done and we send him his new av list.
            datagram = Datagram()
            datagram.addUint8(0)
            self.writeAvatarList(datagram)
            self.sendMessage(CLIENT_DELETE_AVATAR_RESP, datagram)


        elif msgType == CLIENT_ADD_INTEREST:
            # Client wants to add or replace an interest
            handle = di.getUint16()
            contextId = di.getUint32()
            parentId = di.getUint32()

            # We get every zone in the interest, including visibles zones from our visgroup
            zones = set()
            while di.getRemainingSize():
                zoneId = di.getUint32()
                if zoneId == 1:
                    # No we don't want you Quiet Zone
                    continue

                zones.add(zoneId)

                # We add visibles
                canonicalZoneId = getCanonicalZoneId(zoneId)

                if canonicalZoneId in self.agent.visgroups:
                    for visZoneId in self.agent.visgroups[canonicalZoneId]:
                        zones.add(getTrueZoneId(visZoneId, zoneId))

                    # We want to add the "main" zone, i.e 2200 for 2205, etc
                    zones.add(zoneId - zoneId % 100)

            # This is set to an empty tuple because it's only defined if
            # it's overwriting an interest, but needed anyway.
            oldZones = ()

            if handle in self.interests:
                # Our interest is overwriting another interest:
                #
                # - if the parent id is different, we're just gonna remove it by
                #   disabling every object present in the old zones if we're not interested
                #   in them anymore.
                #
                # - if it's the same parent id, we're gonna do some intersection stuff and
                #   only send from the new zones and remove from the old zones,
                #   basically not sending anything for the zones in the intersection

                # We get the old interest
                oldParentId, oldZones = self.interests[handle]

                # We remove it
                del self.interests[handle]
                self.updateInterestCache()

                # We gotta disable the objects we can't see anymore,
                if oldParentId == parentId:
                    for do in self.stateServer.objects.values():
                        # If the object is not visible anymore, we disable it
                        # (it's in the removed interest zones, but not in the new interest (or any current interest) zones)
                        if do.parentId == parentId and do.zoneId in oldZones and not (do.zoneId in zones or self.hasInterest(do.parentId, do.zoneId)):
                            dg = Datagram()
                            dg.addUint32(do.doId)
                            self.sendMessage(CLIENT_OBJECT_DISABLE, dg)

                else:
                    # We only check if we're no longer interested in
                    for do in self.stateServer.objects.values():
                        if do.parentId == oldParentId and do.zoneId in oldZones and not self.hasInterest(do.parentId, do.zoneId):
                            dg = Datagram()
                            dg.addUint32(do.doId)
                            self.sendMessage(CLIENT_OBJECT_DISABLE, dg)

                    # We set oldZones to an empty tuple
                    # (because we're ignoring them as parentId is difference)
                    oldZones = ()

            # We send the newly visible objects
            newZones = []
            for zoneId in zones:
                if not zoneId in oldZones and not self.hasInterest(parentId, zoneId):
                    newZones.append(zoneId)

            # We have got a new zone list, we can finally send the objects.
            self.sendObjects(parentId, newZones)

            # We save the interest
            self.interests[handle] = (parentId, zones)
            self.updateInterestCache()

            # We tell the client we're done
            dg = Datagram()
            dg.addUint16(handle)
            dg.addUint32(contextId)
            self.sendMessage(CLIENT_DONE_INTEREST_RESP, dg)


        elif msgType == CLIENT_REMOVE_INTEREST:
            # Client wants to remove an interest
            handle = di.getUint16()
            contextId = di.getUint32() # Might be optional

            # Did the interest exist?
            if not handle in self.interests:
                raise Exception("Client tried to remove an unexisting interest")

            # We get what the interest was
            oldParentId, oldZones = self.interests[handle]

            # We remove the interest
            del self.interests[handle]
            self.updateInterestCache()

            # We disable all the objects we're no longer interested in
            for do in self.stateServer.objects.values():
                if do.parentId == oldParentId and do.zoneId in oldZones and not self.hasInterest(do.parentId, do.zoneId):
                    dg = Datagram()
                    dg.addUint32(do.doId)
                    self.sendMessage(CLIENT_OBJECT_DISABLE, dg)

            # We tell the client we're done
            dg = Datagram()
            dg.addUint16(handle)
            dg.addUint32(contextId)
            self.sendMessage(CLIENT_DONE_INTEREST_RESP, dg)


        elif msgType == CLIENT_GET_AVATARS:
            # Client asks us their avatars.
            if not self.account:
                # TODO Should we boot the client out or just set a bad returnCode?
                # For now we'll throw an exception as this should never happen.
                raise Exception("Client asked avatars with no account")

            dg = Datagram()
            dg.addUint8(0) # returnCode
            self.writeAvatarList(dg)
            self.sendMessage(CLIENT_GET_AVATARS_RESP, dg)


        elif msgType == CLIENT_SET_AVATAR:
            # Client picked an avatar.
            # If avId is 0, it disconnected.
            avId = di.getUint32()

            self.chooseAvatar(avId)

        elif msgType == CLIENT_OBJECT_UPDATE_FIELD:
            # Client wants to update a do object
            doId = di.getUint32()
            fieldId = di.getUint16()

            dg = Datagram()
            dg.addUint32(doId)
            dg.addUint16(fieldId)
            dg.appendData(di.getRemainingBytes())

            # Can we send this field?
            if not doId in self.stateServer.objects:
                raise Exception("Attempt to update a field but DoId not found")

            do = self.stateServer.objects[doId]

            field = do.dclass.getFieldByIndex(fieldId)
            if not field:
                raise Exception("Attempt to update a field but it was not found")

            if not (field.isClsend() or (field.isOwnsend() and do.doId == self.avatarId)): # We probably should check for owner stuff too but Toontown does not implement it
                raise Exception("Attempt to update a field but we don't have the rights")

            # Ignore DistributedNode and DistributedSmoothNode fields for debugging
            if field.getName() not in ("setX", "setY", "setZ", "setH", "setP", "setR", "setPos", "setHpr", "setPosHpr", "setXY", "setXZ", "setXYH", "setXYZH",
                                       "setComponentL", "setComponentX", "setComponentY", "setComponentZ", "setComponentH", "setComponentP", "setComponentR", "setComponentT",
                                       "setSmStop", "setSmH", "setSmZ", "setSmXY", "setSmXZ", "setSmPos", "setSmHpr", "setSmXYZH", "setSmPosHpr", "setSmPosHprL",
                                       "clearSmoothing", "suggestResync", "returnResync"):

                print("Avatar %d updates %d (dclass %s) field %s" % (self.avatarId, do.doId, do.dclass.getName(), field.getName()))


            if doId == self.avatarId and fieldId == self.agent.setTalkFieldId:
                # Weird case: it's broadcasting and the others can see the chat, but the client
                # does not receive it has he sent it.

                # We will change the sender to 4681 (Chat Manager) to bypass this problem
                self.messageDirector.sendMessage([doId], 4681, STATESERVER_OBJECT_UPDATE_FIELD, dg)

            else:
                # We just send the update to the StateServer.
                self.messageDirector.sendMessage([doId], self.avatarId, STATESERVER_OBJECT_UPDATE_FIELD, dg)


        elif msgType == CLIENT_OBJECT_LOCATION:
            # Client wants to move an object
            doId = di.getUint32()
            parentId = di.getUint32()
            zoneId = di.getUint32()

            # Can we move it?
            if doId != self.avatarId:
                raise Exception("Client wants to move an object it doesn't own")

            # We tell the StateServer that we're moving an object.
            dg = Datagram()
            dg.addUint32(parentId)
            dg.addUint32(zoneId)
            self.messageDirector.sendMessage([doId], self.avatarId, STATESERVER_OBJECT_SET_ZONE, dg)

        elif msgType in (CLIENT_GET_AVATAR_DETAILS, CLIENT_GET_PET_DETAILS):
            # Client wants to get information on a object.
            # Object could either be a Pet or another Toon.
            if msgType == CLIENT_GET_AVATAR_DETAILS:
                # Details about a Toon are being requested.
                dclassName = 'DistributedToon'
                sendId = CLIENT_GET_AVATAR_DETAILS_RESP
            elif msgType == CLIENT_GET_PET_DETAILS:
                # Details about a Pet are being requested.
                dclassName = 'DistributedPet'
                sendId = CLIENT_GET_PET_DETAILS_RESP

            # The indentifier of the object.
            doId = di.getUint32()

            # Get the dclass object by name.
            dclass = self.databaseServer.dc.getClassByName(dclassName)

            # Grab the fields from the object via the database.
            fields = self.databaseServer.loadDatabaseObject(doId).fields

            # Pack our data to go to the client.
            packedData = self.packDetails(dclass, fields)

            # Tell the client about the response.
            dg = Datagram()
            dg.addUint32(doId)
            dg.addUint8(0)
            dg.appendData(packedData)

            # Tell the client about the response.
            self.sendMessage(sendId, dg)

        else:
            print("Received unknown message: %d" % msgType)

        #else:
            #raise NotImplementedError(msgType)

        #if di.getRemainingSize():
            #raise Exception("remaining", di.getRemainingBytes())

    def packDetails(self, dclass, fields):
        # Pack required fields.
        fieldPacker = DCPacker()
        for i in range(dclass.getNumInheritedFields()):
            field = dclass.getInheritedField(i)
            if not field.isRequired() or field.asMolecularField():
                continue

            k = field.getName()
            v = fields.get(k, None)

            fieldPacker.beginPack(field)
            if not v:
                fieldPacker.packDefaultValue()
            else:
                field.packArgs(fieldPacker, v)

            fieldPacker.endPack()

        return fieldPacker.getBytes()

    def writeAvatarList(self, dg):
        """
        Add client avatar list to a datagram
        """
        accountAvSet = self.account.fields["ACCOUNT_AV_SET"]

        # Avatar count
        dg.addUint16(sum(n != 0 for n in accountAvSet)) # avatarTotal

        # We send every avatar
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
        """
        Send a message
        """
        dg = Datagram()
        dg.addUint16(code)
        dg.appendData(datagram.getMessage())
        self.sendDatagram(dg)


    def sendDatagram(self, dg):
        """
        Send a datagram
        """
        self.sock.send(struct.pack("<H", dg.getLength()))
        self.sock.send(bytes(dg))


    def hasInterest(self, parentId, zoneId):
        """
        Check if we're interested in a zone
        """
        # Do we have this intereste cached?
        return (parentId, zoneId) in self.__interestCache


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
            # We're not sending our own object because
            # we already know who we are (we are the owner)
            if do.doId == self.avatarId:
                continue

            # If the object is in one of the new interest zones, we get it
            if do.parentId == parentId and do.zoneId in zones:
                objects.append(do)

        # We sort them by dclass (fix some issues)
        objects.sort(key = lambda x: x.dclass.getNumber())

        # We send every object
        for do in objects:
            dg = Datagram()
            dg.addUint32(do.parentId)
            dg.addUint32(do.zoneId)
            dg.addUint16(do.dclass.getNumber())
            dg.addUint32(do.doId)
            do.packRequiredBroadcast(dg)
            do.packOther(dg)
            self.sendMessage(CLIENT_CREATE_OBJECT_REQUIRED_OTHER, dg)

    def chooseAvatar(self, avId):
        """
        Choose an avatar
        """
        if avId:
            if self.avatarId:
                raise Exception("Client tried to pick an avatar but it already has one")

            if not avId in self.account.fields["ACCOUNT_AV_SET"]:
                raise Exception("Client tried to pick an avatar it doesn't own")

            # We load the avatar from the database
            avatar = self.databaseServer.loadDatabaseObject(avId)

            # We ask STATESERVER to create our object
            dg = Datagram()
            dg.addUint32(0)
            dg.addUint32(0)
            dg.addUint16(avatar.dclass.getNumber())
            dg.addUint32(avatar.doId)
            avatar.packRequired(dg)
            avatar.packOther(dg)
            self.messageDirector.sendMessage([20100000], avatar.doId, STATESERVER_OBJECT_GENERATE_WITH_REQUIRED_OTHER, dg)

            # We probably should wait for an answer, but we're not threaded and everything is happening on the same script
            # (tl;dr it's blocking), so we won't.

            # We remember who we are
            self.avatarId = avatar.doId

            # We can send that we are the proud owner of a DistributedToon!
            dg = Datagram()
            dg.addUint32(avatar.doId)
            dg.addUint8(0)
            avatar.packRequired(dg)
            self.sendMessage(CLIENT_GET_AVATAR_DETAILS_RESP, dg)

        else:
            if not self.avatarId:
                raise Exception("Client tried to remove his avatar but it already has none")

            # We ask State Server to delete our object
            dg = Datagram()
            dg.addUint32(self.avatarId)
            self.messageDirector.sendMessage([self.avatarId], self.avatarId, STATESERVER_OBJECT_DELETE_RAM, dg)
            self.avatarId = 0