from panda3d.core import Vec3, Vec4, Filename, VirtualFileSystem
from direct.stdpy.file import open

"""AllowedKeywords = {
    None: ['group', 'hood_model', 'model', 'node', 'place_model', 'store_font', 'store_suit_point', 'store_texture'],
    'anim_building': ['anim', 'building_type', 'code', 'nhpr', 'pos', 'sign', 'title'],
    'anim_prop': ['anim', 'code', 'nhpr', 'pos'],
    'baseline': ['code', 'color', 'flags', 'graphic', 'height', 'hpr', 'kern', 'nhpr', 'pos', 'scale', 'stomp', 'stumble', 'text', 'width', 'wiggle'],
    'cornice': ['code', 'color'],
    'door': ['code', 'color'],
    'flat_building': ['hpr', 'nhpr', 'pos', 'prop', 'wall', 'width'],
    'flat_door': ['code', 'color'],
    'graphic': ['code'],
    'group': ['anim_building', 'flat_building', 'group', 'interactive_prop', 'landmark_building', 'node', 'prop', 'street', 'visgroup'],
    'hood_model': ['store_node'],
    'interactive_prop': ['anim', 'cell_id', 'code', 'nhpr', 'pos'],
    'landmark_building': ['building_type', 'code', 'door', 'hpr', 'nhpr', 'pos', 'prop', 'sign', 'title'],
    'model': ['store_node'],
    'node': ['flat_building', 'group', 'landmark_building', 'nhpr', 'node', 'pos', 'prop', 'scale', 'street'],
    'place_model': ['store_node'],
    'prop': ['code', 'color', 'hpr', 'nhpr', 'pos', 'scale', 'sign'],
    'sign': ['baseline', 'code', 'color', 'nhpr', 'pos', 'scale'],
    'street': ['code', 'hpr', 'nhpr', 'pos', 'texture'],
    'text': ['letters'],
    'visgroup': ['anim_prop', 'battle_cell', 'flat_building', 'group', 'interactive_prop', 'landmark_building', 'node', 'prop', 'street', 'suit_edge', 'vis'],
    'wall': ['code', 'color', 'cornice', 'flat_door', 'height', 'windows'],
    'windows': ['code', 'color', 'count'],
}"""


class DNAParser:
    def __init__(self, root, data, position = 0):
        self.root = root
        self.data = data 
        self.position = position 
        
        # This fixes a SINGLE file and I don't think i should even do this shit
        if self.data and self.data[0] == " ":
            self.position = self.data.index("\n")
        
        self.readGroup(root, True)
        
    def readGroup(self, currentNode, root=False):
        if not root:
            self.expect("[")
            
        while not (self.next("]") if not root else self.eof()):
            keyword = self.read()
            
            if keyword == "anim":
                if not isinstance(currentNode, (DNAAnimProp, DNAAnimBuilding)):
                    raise TypeError("Got anim for %r" % currentNode)
                    
                self.expect("[")
                currentNode.anim = self.readString()
                self.expect("]")
                
            elif keyword == "anim_building":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got anim_building for %r" % currentNode)
                    
                node = DNAAnimBuilding(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "anim_prop":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got anim_prop for %r" % currentNode)
                    
                node = DNAAnimProp(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "baseline":
                if not isinstance(currentNode, (DNASign)):
                    raise TypeError("Got anim_building for %r" % currentNode)
                    
                node = DNASignBaseline()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                    
            elif keyword == "battle_cell":
                if not isinstance(currentNode, DNAVisGroup):
                    raise TypeError("Got battle_cell for %r" % currentNode)
                    
                self.expect("[")
                width = self.readNumber()
                height = self.readNumber()
                pos = Vec3(self.readNumber(), self.readNumber(), self.readNumber())
                self.expect("]")
                
                currentNode.battleCells.append(DNABattleCell(width, height, pos))
                
            elif keyword == "building_type":
                if not isinstance(currentNode, DNALandmarkBuilding):
                    raise TypeError("Got battle_cell for %r" % currentNode)
                    
                self.expect("[")
                currentNode.buildingType = self.readString()
                self.expect("]")
                
            elif keyword == "cell_id":
                if not isinstance(currentNode, DNAInteractiveProp):
                    raise TypeError("Got cell_id for %r" % currentNode)
                    
                self.expect("[")
                currentNode.cellId = self.readNumber()
                self.expect("]")
                
            elif keyword == "code":
                if not isinstance(currentNode, (DNAWall, DNALandmarkBuilding, DNACornice, DNADoor, DNASign, DNASignBaseline, DNASignGraphic, DNASignText, DNAProp, DNAStreet, DNAWindows)):
                    raise TypeError("Got code for %r" % currentNode)
                    
                self.expect("[")
                currentNode.code = self.readString()
                self.expect("]")
                
            elif keyword == "color":
                if not isinstance(currentNode, (DNAWall, DNACornice, DNADoor, DNASign, DNASignBaseline, DNASignGraphic, DNASignText, DNAProp, DNAWindows)):
                    raise TypeError("Got color for %r" % currentNode)
                    
                self.expect("[")
                currentNode.color = Vec4(self.readNumber(), self.readNumber(), self.readNumber(), self.readNumber())
                self.expect("]")
                
            elif keyword == "cornice":
                if not isinstance(currentNode, DNAWall):
                    raise TypeError("Got cornice for %r" % currentNode)
                    
                node = DNACornice()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "count":
                if not isinstance(currentNode, DNAWindows):
                    raise TypeError("Got count for %r" % currentNode)
                    
                self.expect("[")
                currentNode.count = self.readNumber()
                self.expect("]")
                
            elif keyword == "door":
                if not isinstance(currentNode, (DNALandmarkBuilding)):
                    raise TypeError("Got door for %r" % currentNode)
                    
                node = DNADoor()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "flags":
                if not isinstance(currentNode, DNASignBaseline):
                    raise TypeError("Got flags for %r" % currentNode)
                    
                self.expect("[")
                currentNode.flags = self.readString()
                self.expect("]")
                
            elif keyword == "flat_building":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got flat_building for %r" % currentNode)
                    
                node = DNAFlatBuilding(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "flat_door":
                if not isinstance(currentNode, (DNAWall)):
                    raise TypeError("Got flat_door for %r" % currentNode)
                    
                node = DNAFlatDoor()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "graphic":
                if not isinstance(currentNode, (DNASignBaseline)):
                    raise TypeError("Got height for %r" % currentNode)
                    
                node = DNASignGraphic()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                    
            elif keyword == "group":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got height for %r" % currentNode)
                    
                node = DNAGroup(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "height":
                if not isinstance(currentNode, (DNAWall, DNASignBaseline, DNASignGraphic)):
                    raise TypeError("Got height for %r" % currentNode)
                
                self.expect("[")
                currentNode.height = self.readNumber()
                self.expect("]")
                
            elif keyword == "hood_model":
                if not isinstance(currentNode, (DNAData)):
                    raise TypeError("Got height for %r" % currentNode)
                
                elem = HoodModel(self.readString())
                self.readGroup(elem)
                
            elif keyword == "hpr":
                # TODO: this is **old** hpr and therefore it's supposed to be broken
                if not isinstance(currentNode, (DNANode)):
                    raise TypeError("Got hpr for %r" % node)
                    
                self.expect("[")
                currentNode.hpr = Vec3(self.readNumber(), self.readNumber(), self.readNumber())
                self.expect("]")
                
            elif keyword == "interactive_prop":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got interactive_prop for %r" % currentNode)
                    
                node = DNAInteractiveProp(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "kern":
                if not isinstance(currentNode, DNASignBaseline):
                    raise TypeError("Got kern for %r" % currentNode)
                    
                self.expect("[")
                currentNode.kern = self.readNumber()
                self.expect("]")
                
            elif keyword == "landmark_building":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got landmark_building for %r" % currentNode)
                    
                node = DNALandmarkBuilding(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "letters":
                if not isinstance(currentNode, (DNASignText)):
                    raise TypeError("Got letters for %r" % currentNode)
                    
                self.expect("[")
                currentNode.letters.append(self.readString())
                self.expect("]")
                
            elif keyword == "model":
                if not isinstance(currentNode, (DNAData)):
                    raise TypeError("Got model for %r" % currentNode)
                    
                elem = Model(self.readString())
                self.readGroup(elem)
                
            elif keyword == "nhpr":
                if not isinstance(currentNode, (DNANode)):
                    raise TypeError("Got nhpr for %r" % node)
                    
                self.expect("[")
                currentNode.hpr = Vec3(self.readNumber(), self.readNumber(), self.readNumber())
                self.expect("]")
                
            elif keyword == "node":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got node for %r" % currentNode)
                    
                node = DNANode(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "place_model":
                if not isinstance(currentNode, (DNAData)):
                    raise TypeError("Got place_model for %r" % currentNode)
                    
                elem = PlaceModel(self.readString())
                self.readGroup(elem)
                
            elif keyword == "pos":
                if not isinstance(currentNode, (DNANode)):
                    raise TypeError("Got pos for %r" % node)
                    
                self.expect("[")
                currentNode.pos = Vec3(self.readNumber(), self.readNumber(), self.readNumber())
                self.expect("]")
                
            elif keyword == "prop":
                if not isinstance(currentNode, (DNAGroup)):
                    raise TypeError("Got prop for %r" % node)
                    
                node = DNAProp(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "scale":
                if not isinstance(currentNode, (DNANode)):
                    raise TypeError("Got scale for %r" % node)
                    
                self.expect("[")
                currentNode.scale = Vec3(self.readNumber(), self.readNumber(), self.readNumber())
                self.expect("]")
                
            elif keyword == "sign":
                if not isinstance(currentNode, (DNALandmarkBuilding, DNAFlatBuilding, DNAProp)):
                    raise TypeError("Got sign for %r" % currentNode)
                    
                node = DNASign()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "stomp":
                if not isinstance(currentNode, DNASignBaseline):
                    raise TypeError("Got stomp for %r" % currentNode)
                    
                self.expect("[")
                currentNode.stomp = self.readNumber()
                self.expect("]")
                
            elif keyword == "store_font":
                self.expect("[")
                self.readString()
                self.readString()
                self.readString()
                self.expect("]")
                
            elif keyword == "store_node":
                self.expect("[")
                self.readString()
                self.readString()
                if not self.next("]"):
                    self.readString()
                    self.expect("]")
            
            elif keyword == "store_suit_point":
                self.expect("[")
                self.readNumber()
                self.expect(",")
                self.read()
                self.expect(",")
                self.readNumber()
                self.readNumber()
                self.readNumber()
                if self.expect("]", ",") == ",":
                    self.readNumber()
                    self.expect("]")
                
            elif keyword == "store_texture":
                self.expect("[")
                self.readString()
                self.readString()
                self.readString()
                self.expect("]")
                
            elif keyword == "street":
                if not isinstance(currentNode, DNAGroup):
                    raise TypeError("Got street for %r" % currentNode)
                    
                node = DNAStreet(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "stumble":
                if not isinstance(currentNode, DNASignBaseline):
                    raise TypeError("Got stumble for %r" % currentNode)
                    
                self.expect("[")
                currentNode.stumble = self.readNumber()
                self.expect("]")
                    
            elif keyword == "suit_edge":
                if not isinstance(currentNode, DNAVisGroup):
                    raise TypeError("Got suit_edge for %r" % currentNode)
                    
                self.expect("[")
                startPoint = self.readNumber()
                endPoint = self.readNumber()
                self.expect("]")
                
                currentNode.suitEdges.append(DNASuitEdge(startPoint, endPoint))
                
            elif keyword == "text":
                if not isinstance(currentNode, DNASignBaseline):
                    raise TypeError("Got visgroup for %r" % currentNode)
                    
                node = DNASignText()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "texture":
                if not isinstance(currentNode, DNAStreet):
                    raise TypeError("Got texture for %r" % currentNode)
                    
                self.expect("[")
                texture = self.readString()
                self.expect("]")
                
                if currentNode.streetTexture is None:
                    currentNode.streetTexture = texture
                elif currentNode.sidewalkTexture is None:
                    currentNode.sidewalkTexture = texture
                elif currentNode.curbTexture is None:
                    currentNode.curbTexture = texture
                
            elif keyword == "title":
                if not isinstance(currentNode, DNALandmarkBuilding):
                    raise TypeError("Got title for %r" % currentNode)
                    
                self.expect("[")
                currentNode.title = self.readString()
                self.expect("]")
                
            elif keyword == "vis":
                if not isinstance(currentNode, DNAVisGroup):
                    raise TypeError("Got vis for %r" % currentNode)
                    
                self.expect("[")
                while not self.next("]"):
                    currentNode.visibles.append(self.readString())
                
            elif keyword == "visgroup":
                if not isinstance(currentNode, DNAGroup):
                    raise TypeError("Got visgroup for %r" % currentNode)
                    
                node = DNAVisGroup(self.readString())
                node.parent = currentNode
                self.readGroup(node)
                
                currentNode.children.append(node)
                self.root.dnaStorage.visGroups.append(node)
                
            elif keyword == "wall":
                if not isinstance(currentNode, DNAFlatBuilding):
                    raise TypeError("Got wall for %r" % currentNode)
                    
                node = DNAWall()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            elif keyword == "width":
                if not isinstance(currentNode, (DNAFlatBuilding, DNASignBaseline, DNASignGraphic)):
                    raise TypeError("Got width for %r" % currentNode)
                    
                self.expect("[")
                currentNode.width = self.readNumber()
                self.expect("]")
                
            elif keyword == "wiggle":
                if not isinstance(currentNode, DNASignBaseline):
                    raise TypeError("Got wiggle for %r" % currentNode)
                    
                self.expect("[")
                currentNode.wiggle = self.readNumber()
                self.expect("]")
                
            elif keyword == "windows":
                if not isinstance(currentNode, DNAWall):
                    raise TypeError("Got windows for %r" % currentNode)
                    
                node = DNAWindows()
                node.parent = currentNode
                self.readGroup(node)
                currentNode.children.append(node)
                
            else:
                raise NotImplementedError(keyword)
                
                
    def read(self, charset = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"):
        self.trim()
        
        if not self.data[self.position] in charset:
            raise Exception(self.data[self.position])
            
        pos = self.position
        while self.data[self.position] in charset:
            self.position += 1
            
        return self.data[pos:self.position]
        
        
    def readNumber(self):
        value = self.read("0123456789e-.")
        return float(value)
        
        
    def readString(self):
        self.trim()
        self.expect('"')
        
        pos = self.position
        while self.data[self.position] != '"':
            self.position += 1
            
        self.position += 1
        return self.data[pos:self.position-1]
        
        
    def trim(self):
        while True:
            while self.data[self.position] in (" ", "\n", "\r", "\t"):
                self.position += 1
                
            if self.data[self.position] == "/" == self.data[self.position+1]:
                while self.data[self.position] != "\n":
                    self.position += 1
                
            elif self.data[self.position] == "#":
                while self.data[self.position] != "\n":
                    self.position += 1
                    
            else:
                break
                
                
    def eof(self):
        return len(self.data[self.position:].rstrip(" \n\r\t")) == 0
        
        
    def expect(self, *charset):
        self.trim()
        if self.data[self.position] not in charset:
            raise ValueError(self.data[self.position])
            
        self.position += 1
        return self.data[self.position-1]
        
        
    def next(self, char):
        self.trim()
        if self.data[self.position] == char:
            self.position += 1
            return True
            
        return False
        
        
class DNAGroup:
    def __init__(self, name = ""):
        self.name = name # from Namable
        self.children = []
        self.parent = None


class DNANode(DNAGroup):
    def __init__(self, name = ""):
        super().__init__(name)
        self.pos = None # Vec3f
        self.hpr = None # Vec3f
        self.scale = None # Vec3f
        
        
class DNAWall(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.height = None
        self.color = None
        
        
class DNAFlatBuilding(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.width = None
        # self.current wall height?
        
        
class DNALandmarkBuilding(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.title = None
        self.article = None
        self.code = None
        self.wallColor = None
        self.buildingType = None
        
        
class DNACornice(DNAGroup):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        
        
class DNAData(DNAGroup):
    def __init__(self, name = ""):
        super().__init__(name)
        self.dnaStorage = None
        
    def read(self, filename):
        filename.setBinary()
        
        data = VirtualFileSystem.getGlobalPtr().readFile(filename, False).decode("utf8")
        DNAParser(self, data, 0)
        

class DNADoor(DNAGroup):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        

class DNAFlatDoor(DNADoor):
    def __init__(self, name = ""):
        super().__init__(name)
        
        
class DNAVisGroup(DNAGroup):
    def __init__(self, name = ""):
        super().__init__(name)
        self.visibles = []
        self.suitEdges = []
        self.battleCells = []
        
        
class DNASign(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        
        
class DNASignBaseline(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        self.font = None
        self.indent = None
        self.kern = None
        self.wiggle = None
        self.stumble = None
        self.stomp = None
        self.width = None
        self.height = None
        self.flags = None
        
        
class DNASignGraphic(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        self.width = None
        self.height = None
        
        
class DNASignText(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        self.letters = []
        
        
class DNASuitPoint:
    def __init__(self, index, pointType, pos, lbIndex = -1):
        self.index = index
        self.pointType = pointType
        self.pos = pos
        self.graphId = None
        self.landmarkBuildingIndex = lbIndex
        
        
class DNASuitEdge:
    def __init__(self, startPoint, endPoint):
        self.startPoint = startPoint
        self.endPoint = endPoint
        
        
class DNASuitPath:
    def __init__(self):
        self.points = []
        
        
class DNABattleCell:
    def __init__(self, width, height, pos):
        self.width = width
        self.height = height
        self.pos = pos
        
        
class DNAProp(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.color = None
        
        
class DNAAnimProp(DNAProp):
    def __init__(self, name = ""):
        super().__init__(name)
        self.anim = None
        
        
class DNAInteractiveProp(DNAAnimProp):
    def __init__(self, name = ""):
        super().__init__(name)
        self.cellId = None
        
        
class DNAAnimBuilding(DNALandmarkBuilding):
    def __init__(self, name = ""):
        super().__init__(name)
        self.anim = None
        
        
class DNAStorage:
    def __init__(self):
        self.visGroups = []
        
        
class DNAStreet(DNANode):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.streetTexture = None
        self.sidewalkTexture = None
        self.curbTexture = None
        self.streetColor = None
        self.sidewalkColor = None
        self.curbColor = None
        
        
class DNAWindows(DNAGroup):
    def __init__(self, name = ""):
        super().__init__(name)
        self.code = None
        self.windowCount = None
        self.color = None
        
        
class Model:
    def __init__(self, model):
        self.model = model
        
        
class HoodModel(Model):
    pass
        
        
class PlaceModel(Model):
    pass
    
    
def loadDNAFile(dnaStore, filename):
    dnaData = DNAData()
    dnaData.dnaStorage = dnaStore
    dnaData.read(filename)
    return dnaData
    
    
