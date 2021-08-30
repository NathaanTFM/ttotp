from panda3d.direct import DCPacker
from pprint import pformat

class DatabaseObject:
    def __init__(self, dbss, doId, dclass):
        self.dbss = dbss
        self.doId = doId
        self.dclass = dclass
        self.fields = {}
        
    def packRequired(self, dg):
        packer = DCPacker()
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if field.isRequired():
                packer.beginPack(field)
                if field.getName() in self.fields:
                    field.packArgs(packer, self.fields[field.getName()])
                else:
                    packer.packDefaultValue()
                    
                packer.endPack()
                
        dg.appendData(packer.getBytes())
        
        
    def packOther(self, dg):
        packer = DCPacker()
        count = 0
        
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if field.isDb() and not field.isRequired() and field.getName() in self.fields:
                packer.rawPackUint16(field.getNumber())
                packer.beginPack(field)
                field.packArgs(packer, self.fields[field.getName()])
                packer.packDefaultValue()
                packer.endPack()
                count += 1
                
        dg.addUint16(count)
        dg.appendData(packer.getBytes())
    
    def packField(self, fieldName, value):
        field = self.dclass.getFieldByName(fieldName)
        if not field:
            return None
        
        packer = DCPacker()
        packer.beginPack(field)
        field.packArgs(packer, value)
        packer.endPack()
        
        return packer.getBytes()
        
    def unpackField(self, fieldName, data):
        packer = DCPacker()

        if not data:
            return None
            
        packer.setUnpackData(data)
        
        field = self.dclass.getFieldByName(fieldName)
        if not field:
            return None
            
        packer.beginUnpack(field)
        value = field.unpackArgs(packer)
        packer.endUnpack()

        return value
        
    @classmethod
    def fromBinary(cls, dbss, data):
        if data[:16] == b"# DatabaseObject":
            dclassName, doId, fieldsData = eval(data)
            
            dclass = dbss.dc.getClassByName(dclassName)
            
            self = cls(dbss, doId, dclass)
            for fieldName, value in fieldsData.items():
                field = dclass.getFieldByName(fieldName)
                if field.isDb():
                    self.fields[field.getName()] = value
                else:
                    print("Got an extra field %r" % field.getName())
                    
            return self
                
            
        else:
            packer = DCPacker()
            packer.setUnpackData(data)
            
            version = packer.rawUnpackUint8()
            
            if version != 1:
                raise Exception("bad version %d" % version)
                
            dclass = dbss.dc.getClassByName(packer.rawUnpackString())
            doId = packer.rawUnpackUint32()
            
            self = cls(dbss, doId, dclass)
            
            # We get every field
            while packer.getUnpackLength() > packer.getNumUnpackedBytes():
                field = dclass.getFieldByName(packer.rawUnpackString())
                
                packer.beginUnpack(field)
                value = field.unpackArgs(packer)
                packer.endUnpack()
                
                if field.isDb():
                    self.fields[field.getName()] = value
                else:
                    print("Got an extra field %r" % field.getName())
                    
            return self
        
        
    def toBinary(self):
        if True:
            # Special readable format. We probably should benchmark this,
            # it's perhaps faster
            
            return b"# DatabaseObject\n" + pformat((self.dclass.getName(), self.doId, self.fields), width=-1, sort_dicts=True).encode("utf8")
            
        else:
            data = bytearray()
            packer = DCPacker()
            
            packer.rawPackUint8(1) # version
            packer.rawPackString(self.dclass.getName())
            packer.rawPackUint32(self.doId)
            
            # We get every field
            for fieldName, value in self.fields.items():
                field = self.dclass.getFieldByName(fieldName)
                
                if field.isDb():
                    packer.rawPackString(field.getName())
                    packer.beginPack(field)
                    field.packArgs(packer, self.fields[field.getName()])
                    packer.endPack()
                    
            return packer.getBytes()
        
        
    def receiveField(self, field, di):
        packer = DCPacker()
        packer.setUnpackData(di.getRemainingBytes())
        
        molecular = field.asMolecularField()
        if molecular:
            for n in range(molecular.getNumAtomics()):
                atomic = molecular.getAtomic(n)
                
                packer.beginUnpack(atomic)
                value = atomic.unpackArgs(packer)
                
                if atomic.isDb():
                    self.fields[atomic.getName()] = value
                    
                packer.endUnpack()
                
        else:
            packer.beginUnpack(field)
            value = field.unpackArgs(packer)
            
            if field.isDb():
                self.fields[field.getName()] = value
            
            packer.endUnpack()
            
        di.skipBytes(packer.getNumUnpackedBytes())
        
        # This isn't very optimized, but we wanna make sure we don't lose anything
        self.dbss.saveDatabaseObject(self)
        
        
    def update(self, field, *values):
        # "Manual" update
        field = self.dclass.getFieldByName(field)
        
        if field.asAtomicField():
            self.fields[field.getName()] = values
            
        elif field.asMolecularField():
            raise Exception("No.")
            
        elif field.asParameter():
            if len(values) != 1:
                raise Exception("Arg count mismatch")
                
            self.fields[field.getName()] = values[0]
            
        self.dbss.saveDatabaseObject(self)