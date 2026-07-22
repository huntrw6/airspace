from typing import Literal

AircraftKind = Literal["plane", "helicopter"]

# ICAO Doc 8643 designators whose AircraftDescription is "Helicopter".
ICAO_HELICOPTER_CODES = frozenset(
    """
    A109 A119 A129 A139 A149 A169 A189 A2RT A600 AC31 AC33 ALH ALO2 ALO3 ANST
    AS32 AS3B AS50 AS55 AS65 B06 B06T B105 B150 B212 B214 B222 B230 B305 B407
    B412 B427 B429 B430 B47G B47J B47T B505 B525 BABY BK17 BRB2 BSTP CH12 CH14
    CH7 CHIF COMU DJIN DRAG DYH2 DYH3 EC20 EC25 EC30 EC35 EC45 EC55 EC75 EGL3
    EH10 ELTO EN28 EN48 ES11 EXEC EXEJ EXPL FH11 FREL G2CA GAZL H12T H160 H2
    H21 H269 H43A H43B H46 H47 H500 H53 H53S H60 H64 HSMT HUCO HX2 IS2 JAG2
    K126 K209 K226 KA25 KA26 KA27 KA50 KA52 KA62 KH4 KMAX LAMA LCH LR2T LYNX
    M74 MD52 MD60 MH20 MI10 MI14 MI2 MI24 MI26 MI28 MI34 MI38 MI4 MI6 MI8 NA40
    NH90 OH1 PHIL PSW4 PUMA R22 R4 R44 R66 RMOU RP1 RVAL S274 S278 S285 S330
    S360 S434 S51 S52 S55P S55T S58P S58T S61 S61R S62 S64 S65C S76 S92 S97
    SB1 SCOR SCOU SH09 SH4 SUCO SURN SYCA TIGR UH1 UH12 UH1Y ULTS V500 W3 WASP
    WESX WZ10 X2 X3 X49 YNHL ZA6 ZEFR
    """.split()
)

# Common marketing/military aliases seen in provider data rather than Doc 8643 codes.
HELICOPTER_ALIASES = frozenset(
    "AH64 CH47 H125 H130 H135 H145 H175 H225 KA29 KA31 KA32 S70 V22".split()
)


def aircraft_kind(type_code: object = None, model: object = None) -> AircraftKind:
    """Classify for display only; incomplete data deliberately defaults to plane."""
    code = type_code.strip().upper() if isinstance(type_code, str) else ""
    if code in ICAO_HELICOPTER_CODES or code in HELICOPTER_ALIASES or code == "UHEL":
        return "helicopter"
    description = model.strip().upper() if isinstance(model, str) else ""
    if any(word in description for word in ("HELICOPTER", "ROTORCRAFT", "ROTOR CRAFT")):
        return "helicopter"
    return "plane"
