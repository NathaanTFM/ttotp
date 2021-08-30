from panda3d.core import Datagram
from panda3d.direct import DCPacker
    
class DistributedObject:

    def __init__(self, doId, dclass, parentId, zoneId):
        self.doId = doId
        self.dclass = dclass
        self.parentId = parentId
        self.zoneId = zoneId
        
        self.senders = []
        self.senderId = None
        
        self.fields = {}
        
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if (field.isRequired() or field.isRam()) and field.asAtomicField():
                self.fields[field.getNumber()] = None

    def update(self, field, *values):
        self.fields[self.dclass.getFieldByName(field).getNumber()] = values
        
    def packField(self, dg, field):
        packer = DCPacker()
        packer.beginPack(field)
        
        if field.getNumber() in self.fields:
            field.packArgs(packer, self.fields[field.getNumber()])
        else:
            packer.packDefaultValue()
            
        packer.endPack()
        dg.appendData(packer.getBytes())

    def packRequired(self, dg):
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if field.isRequired() and field.asAtomicField():
                self.packField(dg, field)

    def packRequiredBroadcast(self, dg):
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if (field.isRequired() and field.isBroadcast()) and field.asAtomicField():
                self.packField(dg, field)

    def packOther(self, dg):
        dg2 = Datagram()
        count = 0
        
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if field.isBroadcast() and not field.isRequired() and self.fields.get(field.getNumber(), None) is not None:
                count += 1
                
                dg2.addUint16(field.getNumber())
                self.packField(dg2, field)
                
        dg.addUint16(count)
        dg.appendData(dg2.getMessage())
        
        
    def receiveField(self, field, di):
        packer = DCPacker()
        packer.setUnpackData(di.getRemainingBytes())
        
        molecular = field.asMolecularField()
        if molecular:
            for n in range(molecular.getNumAtomics()):
                atomic = molecular.getAtomic(n)
                
                packer.beginUnpack(atomic)
                value = atomic.unpackArgs(packer)
                
                if atomic.getNumber() in self.fields:
                    self.fields[atomic.getNumber()] = value
                    
                packer.endUnpack()
                
        else:
            packer.beginUnpack(field)
            value = field.unpackArgs(packer)
            
            if field.getNumber() in self.fields:
                self.fields[field.getNumber()] = value
            
            packer.endUnpack()
            
        di.skipBytes(packer.getNumUnpackedBytes())
        
    def receiveRequired(self, di):
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if field.isRequired() and field.asAtomicField():
                self.receiveField(field, di)
        
    def receiveRequiredBroadcast(self, di):
        for index in range(self.dclass.getNumInheritedFields()):
            field = self.dclass.getInheritedField(index)
            if field.isRequired() or field.asAtomicField():
                self.receiveField(field, di)
        
    def receiveOther(self, di):
        for n in range(di.getUint16()):
            index = di.getUint16()
            
            field = self.dclass.getFieldByIndex(index)
            self.receiveField(field, di)

    def __repr__(self):
        return "<" + self.dclass.getName() + " instance at " + str(self.doId) + ", in " + str(self.parentId) + " zone " + str(self.zoneId) + ">"