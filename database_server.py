from panda3d.core import DatagramIterator
from panda3d.direct import DCPacker
from database_object import DatabaseObject
from msgtypes import *
import os

class DatabaseServer:
    def __init__(self, otp):
        # Main OTP
        self.otp = otp
        
        # Database server objects
        self.databaseCache = {}
        
        # DC File
        self.dc = self.otp.dc
        
        
    def handle(self, channels, sender, code, datagram):
        """
        Handle a message
        """
        for channel in channels:
            if channel in self.databaseCache:
                di = DatagramIterator(datagram)
                do = self.databaseCache[channel]
                
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
        files = os.listdir("database")
        
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
        
        
    def saveDatabaseObject(self, do):
        """
        Save a database object
        """
        with open(os.path.join("database", str(do.doId) + ".bin"), "wb") as file:
            file.write(do.toBinary())
        
        
    def loadDatabaseObject(self, doId):
        """
        Load a database object by its id
        """
        if not doId in self.databaseCache:
            with open(os.path.join("database", str(doId) + ".bin"), "rb") as file:
                self.databaseCache[doId] = DatabaseObject.fromBinary(self, file.read())
        
        return self.databaseCache[doId]
        
        