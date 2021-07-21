#### ZONE IDs ####
# Hood ids.  These are also the zone ids of the corresponding
# safezone, and also represent the first of a range of 1000 zone ids
# allocated to each hood.
DonaldsDock =           1000
ToontownCentral =       2000
TheBrrrgh =             3000
MinniesMelodyland =     4000
DaisyGardens =          5000
OutdoorZone =           6000
FunnyFarm =             7000
GoofySpeedway =         8000
DonaldsDreamland =      9000

# Street Branch zones
# DonaldsDock
BarnacleBoulevard =  1100
SeaweedStreet =      1200
LighthouseLane =     1300
# ToontownCentral
SillyStreet =        2100
LoopyLane =          2200
PunchlinePlace =     2300
# TheBrrrgh
WalrusWay =          3100
SleetStreet =        3200
PolarPlace =         3300
# MinniesMelodyland
AltoAvenue =         4100
BaritoneBoulevard =  4200
TenorTerrace =       4300
# DaisyGardens
ElmStreet =          5100
MapleStreet =        5200
OakStreet =          5300
# DonaldsDreamland
LullabyLane =        9100
PajamaPlace =        9200

# Keep a static zoneId for toonhall
ToonHall = 2513

# This is a special case.  It's not a real zoneId, but is used to
# represent the entire collection of WelcomeValley zones, which is
# maintained by the AI.  Requesting a transfer to this zone really
# means to go to a WelcomeValley zone of the AI's choosing.
WelcomeValleyToken =    0

# CogHQ hood/zone ids. (Some of these are not real zoneIds but are here
# so that quests can specify them as locations.)
BossbotHQ =            10000
BossbotLobby =         10100
BossbotCountryClubIntA = 10500
BossbotCountryClubIntB = 10600
BossbotCountryClubIntC = 10700
SellbotHQ =            11000
SellbotLobby =         11100
SellbotFactoryExt =    11200
SellbotFactoryInt =    11500 # for the sake of quests
CashbotHQ =            12000
CashbotLobby =         12100
CashbotMintIntA =      12500 # for the sake of quests
CashbotMintIntB =      12600 # for the sake of quests
CashbotMintIntC =      12700 # for the sake of quests
LawbotHQ =             13000
LawbotLobby =          13100
LawbotOfficeExt =      13200
LawbotOfficeInt =      13300 #should be a dynamic instance
LawbotStageIntA =      13300 # for the sake of quests
LawbotStageIntB =      13400 # for the sake of quests
LawbotStageIntC =      13500 # for the sake of quests
LawbotStageIntD =      13600 # for the sake of quests

# These are hood ids, but they are not zone ids.
Tutorial =             15000
MyEstate =             16000

# Minigolf hood ids
GolfZone =             17000

# Party zone hood id
PartyHood =            18000

# This is the pool of zone ids reserved for the dynamically-allocated
# copies of ToontownCentral known as WelcomeValley.  Each dynamic hood
# gets 1000 zone ids.
WelcomeValleyBegin =      22000
WelcomeValleyEnd =        61000

# Everything from this zone up to the top of the available range is
# reserved for the dynamic zone pool.  Note that our effective maximum
# zone may be less than DynamicZonesEnd, depending on the assignment
# of available doIds--we must be careful not to overlap.
DynamicZonesBegin =    61000
DynamicZonesEnd =      (1 << 20)


    
def getCanonicalZoneId(zoneId):
    if zoneId == WelcomeValleyToken:
        zoneId = ToontownCentral
        
    elif zoneId >= WelcomeValleyBegin and zoneId < WelcomeValleyEnd:
        zoneId = (zoneId%2000)
        if zoneId < 1000:
            zoneId = zoneId + ToontownCentral
        else:
            zoneId = zoneId - 1000 + GoofySpeedway
            
    return zoneId
    
    
def getTrueZoneId(zoneId, currentZoneId):
    if (zoneId >= WelcomeValleyBegin and \
       zoneId < WelcomeValleyEnd) or zoneId == WelcomeValleyToken:
        zoneId = getCanonicalZoneId(zoneId)

    if currentZoneId >= WelcomeValleyBegin and \
       currentZoneId < WelcomeValleyEnd:
        hoodId = getHoodId(zoneId)
        offset = currentZoneId - (currentZoneId % 2000)
        if hoodId == ToontownCentral:
            return (zoneId - ToontownCentral) + offset
        elif hoodId == GoofySpeedway: 
            return (zoneId - GoofySpeedway) + offset + 1000
    return zoneId
    

def getHoodId(zoneId):
    hoodId = zoneId - (zoneId % 1000)
    return hoodId