from panda3d.core import Datagram, DatagramIterator
from panda3d.direct import DCPacker
from database_object import DatabaseObject
from distributed_object import DistributedObject
from msgtypes import *
import os

class DatabaseServer:
    def __init__(self, otp):
        # Main OTP
        self.otp = otp
        
        # DC File
        self.dc = self.otp.dc
        
        # Quick access for CA and MD 
        self.clientAgent = self.otp.clientAgent
        self.messageDirector = self.otp.messageDirector
        self.stateServer = self.otp.stateServer
        
        # Cached DBObjects
        self.cache = {}
        
        # List of DC Classes that have the DcObjectType field.
        self.dbObjectClassNames = []
        
        # Database path
        self.path = "database"
        
        if not os.path.exists(self.path):
            os.mkdir(self.path)
        
        # Get all of our dc classes with the DcObjectType field.
        for i in range(0, self.dc.getNumClasses()):
            dclass = self.dc.getClass(i)
            # While DistributedToon is a valid db class.
            # It doesn't need an id.
            if dclass.getName() == "DistributedToon":
                continue
            if dclass.getFieldByName("DcObjectType"):
                self.dbObjectClassNames.append(dclass.getName())
            
    def handle(self, channels, sender, code, datagram):
        """
        Handle a message
        """
        for channel in channels:
            if channel == 4003:
                if code == DBSERVER_GET_STORED_VALUES:
                    self.getStoredValues(sender, datagram)
                    
                elif code == DBSERVER_SET_STORED_VALUES:
                    self.setStoredValues(sender, datagram)
                    
                elif code == DBSERVER_CREATE_STORED_OBJECT:
                    self.createStoredObject(sender, datagram)
                    
                elif code == DBSERVER_DELETE_STORED_OBJECT:
                    print("DBSERVER_DELETE_STORED_OBJECT")
                    
                elif code == DBSERVER_GET_ESTATE:
                    self.getEstate(sender, datagram)
                    
                elif code == DBSERVER_MAKE_FRIENDS:
                    self.makeFriends(sender, datagram)
                    
                elif code == DBSERVER_REQUEST_SECRET:
                    print("DBSERVER_REQUEST_SECRET")
                    
                elif code == DBSERVER_SUBMIT_SECRET:
                    print("DBSERVER_SUBMIT_SECRET")
                    
                else:
                    raise Exception("Unknown message on DBServer channel: %d" % code)
                    
            if channel in self.cache:
                di = DatagramIterator(datagram)
                do = self.cache[channel]
                
                if code == STATESERVER_OBJECT_UPDATE_FIELD:
                    # We are asked to update a field
                    doId = di.getUint32()
                    fieldId = di.getUint16()
                    
                    # Is this sent to the correct object?
                    if doId != do.doId:
                        raise Exception("Object %d does not match channel %d" % (doId, do.doId))
                    
                    # We apply the update
                    field = do.dclass.getFieldByIndex(fieldId)
                    do.receiveField(field, di)

    def createDatabaseObject(self, dclassName):
        """
        Create a database object with the dclass and default fields
        """
        
        # We look for the dclass
        dclass = self.dc.getClassByName(dclassName)
        if not dclass:
            raise NameError(dclassName)
        
        # We get a doId
        files = os.listdir(self.path)
        
        if sum(filename.endswith(".bin") for filename in files) == 0:
            doId = 10000000
        else:
            doId = max([int(filename[:-4]) for filename in files if filename.endswith(".bin")]) + 1
            
        # We generate the DatabaseObject
        do = DatabaseObject(self, doId, dclass)
        
        # We set default values
        packer = DCPacker()
        for n in range(dclass.getNumInheritedFields()):
            field = dclass.getInheritedField(n)
            if field.isDb():
                packer.setUnpackData(field.getDefaultValue())
                packer.beginUnpack(field)
                do.fields[field.getName()] = field.unpackArgs(packer)
                packer.endUnpack()
                
        # We save the object
        self.saveDatabaseObject(do)
        return do
        
    def hasDatabaseObject(self, doId):
        """
        Check if a database object exists.
        """
        return os.path.isfile(os.path.join(self.path, str(doId) + ".bin"))
        
    def saveDatabaseObject(self, do):
        """
        Save a database object
        """
        with open(os.path.join(self.path, str(do.doId) + ".bin"), "wb") as file:
            file.write(do.toBinary())
        
        
    def loadDatabaseObject(self, doId):
        """
        Load a database object by its id
        """
        if not doId in self.cache:
            with open(os.path.join(self.path, str(doId) + ".bin"), "rb") as file:
                self.cache[doId] = DatabaseObject.fromBinary(self, file.read())
        
        return self.cache[doId]
        
    def getStoredValues(self, sender, datagram):
        """
        Get the stored field values from the object specified in the datagram.
        """
        di = DatagramIterator(datagram)
        
        # Get the context.
        context = di.getUint32()
        
        # The doId we want to get the fields from.
        doId = di.getUint32()
        
        # The number of fields we're going to search for.
        numFields = di.getUint16()
        
        # Get all of the field names we want to work with!
        fieldNames = []
        for i in range(0, numFields):
            fieldNames.append(di.getString())
            
        numFields = len(fieldNames)
        
        dg = Datagram()
        dg.addUint32(context) # Rain or shine. We want the context.
        dg.addUint32(doId) # They'll need to know what doId this was for!
        dg.addUint16(numFields) # Send back the number of fields we searched for.
        
        # Add all of our field names.
        for i in range(0, numFields):
            dg.addString(fieldNames[i])
        
        # Make sure our database object even exists first.
        if not self.hasDatabaseObject(doId):
            # Failed to get our object. So we just add our response code.
            dg.addUint8(1)
            # Send out our response.
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_GET_STORED_VALUES_RESP, dg)
            return
            
        dg.addUint8(0)
        
        # Load our database object.
        do = self.loadDatabaseObject(doId)
        
        values = []
        found = []
        
        # Add our field values.
        for i in range(0, numFields):
            fieldName = fieldNames[i]
            if fieldName in do.fields: # Success
                values.append(do.packField(fieldName, do.fields[fieldName]).decode('ISO-8859-1'))
                found.append(True)
                continue
            # Failure, The field doesn't exist.
            #print("Couldn't find field %s for do %s!" % (fieldName, str(do.doId)))
            values.append("DEADBEEF")
            found.append(False)
            
        # Add our values.
        for i in range(0, numFields):
            value = values[i]
            dg.addString(value)
        
        # Add the list of our found field values.
        for i in range(0, numFields):
            foundField = found[i]
            dg.addUint8(foundField)

        # Send out our response.
        self.messageDirector.sendMessage([sender], 20100000, DBSERVER_GET_STORED_VALUES_RESP, dg)
        
        # Generate our db object if needed!
        if do.dclass.getName() in self.dbObjectClassNames:
            if do.doId in self.stateServer.objects:
                #print("%s object %d already exists in objects!" % (do.dclass.getName(), do.doId))
                return
            if do.doId in self.stateServer.dbObjects:
                #print("%s object %d already exists in db objects!" % (do.dclass.getName(), do.doId))
                return
            #print("Creating %s db object with doId %d!" % (do.dclass.getName(), do.doId))
            self.stateServer.dbObjects[do.doId] = DistributedObject(do.doId, do.dclass, 0, 0)
        
    def setStoredValues(self, sender, datagram):
        """
        Set the values of the fields for the object specified in the datagram.
        """
        di = DatagramIterator(datagram)
        
        # The doId we want to set the fields for.
        doId = di.getUint32()
        
        # The number of fields we're going to set.
        numFields = di.getUint32()
        
        fieldNames = []
        fieldValues = []
        
        # Get all of our field names.
        for i in range(0, numFields):
            fieldNames.append(di.getString())
        
        # Get all of our field values.
        for i in range(0, numFields):
            fieldValues.append(di.getString())
            
        # Make sure our database object even exists first.
        if not self.hasDatabaseObject(doId):
            return

        # Load our database object.
        do = self.loadDatabaseObject(doId)
        
        # Unpack and assign the field values.
        for i in range(0, numFields):
            fieldName = fieldNames[i]
            fieldValue = fieldValues[i]
            
            if not do.dclass.getFieldByName(fieldName):
                # We can't set a field our dcclass doesn't have!
                continue
            
            unpackedValue = do.unpackField(fieldName, fieldValue)
            if unpackedValue:
                do.fields[fieldName] = unpackedValue
        
        # Save the database object to make sure we don't lose our changes.
        self.saveDatabaseObject(do)
        
    def createStoredObject(self, sender, datagram):
        """
        Create a Database Object from the database object index.
        """
        di = DatagramIterator(datagram)
        
        fieldNames = []
        fieldValues = []
        
        # Get the context.
        context = di.getUint32()
        
        # We just need to do this for this unused value.
        u = di.getString()
        
        # This is our database object ID.
        dbObjectType = di.getUint16()
        
        # The amount of fields we have.
        numFields = di.getUint16()
        
        # Get all of our field names
        for i in range(0, numFields):
            fieldNames.append(di.getString())
        
        # Get all of our field values.
        for i in range(0, numFields):
            fieldValues.append(di.getString().encode('ISO-8859-1'))
        
        if dbObjectType >= len(self.dbObjectClassNames):
            dg = Datagram()
            # Add our context.
            dg.addUint32(context)
            # We failed, So add a response code of 1.
            dg.addUint8(1)
            
            # Send out our response.
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_CREATE_STORED_OBJECT_RESP, dg)
            return
        
        # Get the dc class name for our object type.
        dclassName = self.dbObjectClassNames[dbObjectType]
        
        # Create a database object from our dc class name.
        dbObject = self.createDatabaseObject(dclassName)
        
        # Unpack and assign the field values.
        for i in range(0, numFields):
            fieldName = fieldNames[i]
            fieldValue = fieldValues[i]

            if not dbObject.dclass.getFieldByName(fieldName):
                # We can't set a field our dcclass doesn't have!
                continue

            unpackedValue = dbObject.unpackField(fieldName, fieldValue)
            if unpackedValue:
                dbObject.fields[fieldName] = unpackedValue
                
        # Save the database object to make sure we don't lose our changes.
        self.saveDatabaseObject(dbObject)
        
        dg = Datagram()
        
        # Add our context.
        dg.addUint32(context)
        
        # We succesfully created and set the fields of the database object.
        dg.addUint8(0)
        
        # Add the resulting object doId.
        dg.addUint32(dbObject.doId)
        
        # Send out our response.
        self.messageDirector.sendMessage([sender], 20100000, DBSERVER_CREATE_STORED_OBJECT_RESP, dg)

    def getEstate(self, sender, datagram):
        """
        Return the database values for the Estate and fields specified, 
        If some parts of the Estate aren't created. They are here.
        """
        di = DatagramIterator(datagram)
        
        # Get the context for sending back.
        context = di.getUint32()
        
        # The avatar which has the estate.
        doId = di.getUint32()
        
        dg = Datagram()
        
        # Rain or shine. We want the context.
        dg.addUint32(context)
        
        if not self.hasDatabaseObject(doId):
            dg.addUint8(1) # Failed to get our avatar, So we can't get their houses either!
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_GET_ESTATE_RESP, dg)
            return
            
        currentAvatar = self.loadDatabaseObject(doId)
        
        # Somehow we don't have an account!
        if not 'setDISLid' in currentAvatar.fields:
            dg.addUint8(1) # Failed to get our avatar, So we can't get their houses either!
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_GET_ESTATE_RESP, dg)
            return
            
        accountId = currentAvatar.fields['setDISLid'][0]
        
        # Our account doesn't exist!?
        if not self.hasDatabaseObject(accountId):
            dg.addUint8(1) # Failed to get our avatar, So we can't get their houses either!
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_GET_ESTATE_RESP, dg)
            return
            
        account = self.loadDatabaseObject(accountId)
        
        # Pre-define this here.
        estate = None
        houseIds = None
        
        # We need to create an Estate!
        if not 'ESTATE_ID' in account.fields or account.fields['ESTATE_ID'] == 0:
            estate = self.createDatabaseObject("DistributedEstate")
            houseIds = [0, 0, 0, 0, 0, 0]
            account.update("ESTATE_ID", estate.doId)
            account.update("HOUSE_ID_SET", houseIds)
            if not estate.doId in self.stateServer.dbObjects:
                self.stateServer.dbObjects[estate.doId] = DistributedObject(estate.doId, estate.dclass, 0, 0)
        else:
            estate = self.loadDatabaseObject(account.fields['ESTATE_ID'])
            houseIds = account.fields["HOUSE_ID_SET"]
            if not estate.doId in self.stateServer.dbObjects:
                self.stateServer.dbObjects[estate.doId] = DistributedObject(estate.doId, estate.dclass, 0, 0)

        avatars = account.fields["ACCOUNT_AV_SET"]
        
        houses = []
        
        # First create all our blank houses.
        for i in range(0, len(houseIds)):
            if houseIds[i] == 0:
                house = self.createDatabaseObject("DistributedHouse")
                house.update("setName", "")
                house.update("setAvatarId", 0)
                house.update("setColor", i)
                houseIds[i] = house.doId
                if not house.doId in self.stateServer.dbObjects:
                    self.stateServer.dbObjects[house.doId] = DistributedObject(house.doId, house.dclass, 0, 0)
                houses.append(house)
            else: # If the house already exists... Just generate and store it.
                house = self.loadDatabaseObject(houseIds[i])
                house.update("setColor", i)
                if not house.doId in self.stateServer.dbObjects:
                    self.stateServer.dbObjects[house.doId] = DistributedObject(house.doId, house.dclass, 0, 0)
                houses.append(house)
                
        pets = []
                
        # Time to update our existing houses and pets!
        for i in range(0, len(avatars)):
            avDoId = avatars[i]
            
            # If we're missing the avatar for some reason... Skip!
            if not self.hasDatabaseObject(avDoId):
                continue
                
            # Load in our avatar.
            avatar = self.loadDatabaseObject(avDoId)
            
            # Load our pet for this avatar in question in.
            if "setPetId" in avatar.fields and avatar.fields["setPetId"][0] != 0:
                pet = self.loadDatabaseObject(avatar.fields["setPetId"][0])
                if not pet.doId in self.stateServer.dbObjects:
                    self.stateServer.dbObjects[pet.doId] = DistributedObject(pet.doId, pet.dclass, 0, 0)
                pets.append(pet)
                
            avPositionIndex = avatar.fields["setPosIndex"][0]
            # If for some reason theres no house here... Create one!
            if houseIds[avPositionIndex] == 0:
                house = self.createDatabaseObject("DistributedHouse")
                house.update("setName", avatar.fields["setName"][0])
                house.update("setAvatarId", avDoId)
                house.update("setColor", avPositionIndex)
                houseIds[avPositionIndex] = house.doId
                if not house.doId in self.stateServer.dbObjects:
                    self.stateServer.dbObjects[house.doId] = DistributedObject(house.doId, house.dclass, 0, 0)
            else: # Update our houses info just in case ours changed!
                house = self.loadDatabaseObject(houseIds[avPositionIndex])
                house.update("setName", avatar.fields["setName"][0])
                house.update("setAvatarId", avDoId)
                house.update("setColor", avPositionIndex)
                if not house.doId in self.stateServer.dbObjects:
                    self.stateServer.dbObjects[house.doId] = DistributedObject(house.doId, house.dclass, 0, 0)
            
        
        # Update our ids just in case a new house was made.
        account.update("HOUSE_ID_SET", houseIds)
        
        # Make sure our account saved it's changes.
        self.saveDatabaseObject(account)
        
        # We've succeeded in loading everything we need to, So we add this indicating success.
        dg.addUint8(0)
        
        # Add our estate doId
        dg.addUint32(estate.doId)
        
        # Add the amount of fields in our estate.
        dg.addUint16(len(estate.fields))
        
        # Add our field values. This in theory isn't needed at all.
        for name, value in estate.fields.items():
            try:
                dg.addString(name)
                dg.addString(estate.packField(name, value).decode('ISO-8859-1'))
                dg.addUint8(True)
            except:
                dg.addString("DEADBEEF")
                dg.addString("DEADBEEF")
                dg.addUint8(False)
                
        houseLen = len(houses)
        # Add the number of houses we have.
        dg.addUint16(houseLen)
        
        # Add all of our house doIds.
        for i in range(0, len(houses)):
            house = houses[i]
            dg.addUint32(house.doId)
        
        houseData = {}
        foundHouses = houseLen
        
        for name in list(houses[0].fields.keys()):
            houseData[name] = []
        
        # Make a our lists of field names and values. 
        for i in range(0, len(houses)):
            house = houses[i]
            for name, value in house.fields.items():
                houseData[name].append(house.packField(name, value))

        # Add the number of house keys we have.
        dg.addUint16(len(houseData))
        
        # Add our house keys.
        for name in list(houseData.keys()):
            dg.addString(name)
            
        # Add the number of house values we have.
        dg.addUint16(len(houseData))
        
        # Add our house values.
        for name, data in houseData.items():
            dg.addUint16(houseLen) # Why the fuck is this needed Disney.
            for i in range(0, len(data)):
                value = data[i]
                dg.addString(value.decode('ISO-8859-1'))

        # The amount of houses we got successfully,
        # It's not checked anymore. So it's safe to say it was scrapped.
        dg.addUint16(foundHouses)
        
        # Add in if we found a house or not, We don't really check this as of rn.
        # We've either failed eariler or gotten to this point.
        for i in range(0, len(houseData)):
            dg.addUint16(0) #hvLen, This isn't used anymore either.
            for j in range(0, houseLen):
                dg.addUint8(1)
            
        # Add the number of pets we have.
        dg.addUint16(len(pets))
        
        # Add our pet doIds.
        for i in range(0, len(pets)):
            pet = pets[i]
            dg.addUint32(pet.doId)
        
        # We can FINALLY send our message.
        self.messageDirector.sendMessage([sender], 20100000, DBSERVER_GET_ESTATE_RESP, dg)

    def makeFriends(self, sender, datagram):
        di = DatagramIterator(datagram)
        
        # The first person who wants to make friends.
        friendIdA = di.getUint32()
        
        # The second person who wants to make to friends.
        friendIdB = di.getUint32()
        
        # The flags for this friendship.
        flags = di.getUint8()
        
        # Get the context for sending back.
        context = di.getUint32()
        
        dg = Datagram()
        
        # If one or netiher of the database objects exist. They can NOT become friends.
        if not self.hasDatabaseObject(friendIdA) or not self.hasDatabaseObject(friendIdB):
            dg.addUint8(False)
            dg.addUint32(context)
            # Send out our response.
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_MAKE_FRIENDS_RESP, dg)
            return
            
        # Load the database objects for our friends.
        friendA = self.loadDatabaseObject(friendIdA)
        friendB = self.loadDatabaseObject(friendIdB)
        
        # If one or either can't possibly make friends, We will respond with a failure.
        if not friendA.dclass.getFieldByName("setFriendsList") or not friendB.dclass.getFieldByName("setFriendsList"):
            dg.addUint8(False)
            dg.addUint32(context)
            # Send out our response.
            self.messageDirector.sendMessage([sender], 20100000, DBSERVER_MAKE_FRIENDS_RESP, dg)
            return
            
        # Make sure we have the field already.
        if not "setFriendsList" in friendA.fields:
            friendA.fields["setFriendsList"] = ([],)
        if not "setFriendsList" in friendB.fields:
            friendB.fields["setFriendsList"] = ([],)
            
        friendAlist = friendA.fields["setFriendsList"][0]
        friendBlist = friendB.fields["setFriendsList"][0]
        
        # To know if we had the corresponding friends or not.
        HasFriendA = False
        HasFriendB = False
        
        # Check if we already have friend B in friend As list.
        # And update it if we do.
        for i in range(0, len(friendAlist)):
            friendPair = friendAlist[i]
            if friendPair[0] == friendIdB:
                # We did.  Update the code.
                friendAlist[i] = (friendIdB, flags)
                HasFriendA = True
                break
                
        if not HasFriendA:
            # We didn't already have this friend; tack it on.
            friendAlist.append((friendIdB, flags))
            
        # Check if we already have friend A in friend Bs list.
        # And update it if we do.
        for i in range(0, len(friendBlist)):
            friendPair = friendBlist[i]
            if friendPair[0] == friendIdA:
                # We did.  Update the code.
                friendBlist[i] = (friendIdA, flags)
                HasFriendB = True
                break
                
        if not HasFriendB:
            # We didn't already have this friend; tack it on.
            friendBlist.append((friendIdA, flags))
        
        # We succesfully added them as a friend!
        dg.addUint8(True)
        dg.addUint32(context)
        
        self.messageDirector.sendMessage([sender], 20100000, DBSERVER_MAKE_FRIENDS_RESP, dg)
        
        # Save the database objects to make sure we don't lose our changes.
        self.saveDatabaseObject(friendA)
        self.saveDatabaseObject(friendB)