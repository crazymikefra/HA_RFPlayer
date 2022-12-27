"""Parsers."""

from enum import Enum
import json
import logging
import re
from typing import Any, Callable, Dict, Generator, cast

log = logging.getLogger(__name__)

PACKET_ID_SEP = "_"

PACKET_FIELDS = {
    "bat": "battery",
    "cmd": "command",
    "dtc": "detector",
    "sta": "status",
    "sen": "sensor",
    "cov": "cover"
}

RTS_ELEM = {
    "0": "shu",
    "1": "por",
}

UNITS = {
    "bat": None,
    "cmd": None,
    "detector": None,
    "sta": None,
}

DTC_STATUS_LOOKUP = {
    "0": "closed",
    "2": "open",
    "8": "alive",
    "16": "assoc",
    "18": "test",
}

RTS_STATUS_LOOKUP = {
    "1" : "DOWN", #Down /OFF
    "4" : "MY", #My
    "7" : "UP", #Up /ON
    "13" : "ASSOC",
    
    "5" : "LEFT", #Left button
    "6" : "RIGHT", #Right button
}

VALUE_TRANSLATION = cast(
    Dict[str, Callable[[str], str]],
    {
        "detector": lambda x: DTC_STATUS_LOOKUP.get(x, "unknown"),
        "rts_status": lambda x: RTS_STATUS_LOOKUP.get(x, "unknown"),
        "rts_elem": lambda x: RTS_ELEM.get(x, "unknown"),
    },
)

PACKET_HEADER_RE = (
    "^("
    + "|".join(
        [
            "ZIA--",  # command reply
            "ZIA33",  # json reply
        ]
    )
    + ")"
)

packet_header_re = re.compile(PACKET_HEADER_RE)

PacketType = Dict[str, Any]


class PacketHeader(Enum):
    """Packet source identification."""

    master = "10"
    echo = "11"
    gateway = "20"


def valid_packet(packet: str) -> bool:
    """Check if packet is valid."""
    return bool(packet_header_re.match(packet))


def decode_packet(packet: str) -> list:
    """Decode packet."""
    packets_found = []
    data = cast(PacketType, {"node": PacketHeader.gateway.name})

    # Welcome messages directly send
    if packet.startswith("ZIA--"):
        data["message"] = packet.replace("ZIA--", "")
        return [data]

    # Protocols
    message = json.loads(packet.replace("ZIA33", ""))["frame"]
    data["protocol"] = message["header"]["protocolMeaning"]

    if data["protocol"] in ["BLYSS", "CHACON", "JAMMING"]:
        data["id"] = message["infos"]["id"]
        data["command"] = message["infos"]["subType"]
        data["state"] = message["infos"]["subTypeMeaning"]
        packets_found.append(data)
    elif data["protocol"] in ["X2D"]:
        data["id"] = message["infos"]["id"]
        if message["infos"]["subTypeMeaning"] == 'Detector/Sensor':
          value = VALUE_TRANSLATION['detector'](message["infos"]["qualifier"]) 
          data["command"] = value
          data["state"] = value
        else:
          data["command"] = message["infos"]["subTypeMeaning"]
          data["state"] = message["infos"]["qualifier"]
        packets_found.append(data)           
    elif data["protocol"] in ["OREGON"]:
        data["id"] = message["infos"]["id_PHY"]
        data["hardware"] = message["infos"]["id_PHYMeaning"]
        for measure in message["infos"]["measures"]:
            measure_data = data.copy()
            measure_data["command"] = measure["value"]
            measure_data["state"] = measure["value"]
            measure_data["unit"] = measure["unit"]
            measure_data["type"] = measure["type"]
            packets_found.append(measure_data)
    elif data["protocol"] in ["EDISIO"]:
        data["id"] = message["infos"]["id"]
        data["hardware"] = message["infos"]["infoMeaning"]
        data["command"] = message["infos"]["subType"]
        data["state"] = message["infos"]["subType"]
        packets_found.append(data)
    elif data["protocol"] in ["RTS"]:
        data["id"] = message["infos"]["id"]
        data["platform"] = "cover"
        value = VALUE_TRANSLATION['rts_status'](message["infos"]["qualifier"]) 
        #data["platform"] = "cover"
        data["cover"] = value
        packets_found.append(data)
    else:
        data["id"] = message["infos"].get("id")
        data["command"] = message["infos"].get("subType")
        packets_found.append(data)

    return packets_found


def encode_packet(packet: PacketType) -> str:
    """Construct packet string from packet dictionary."""
    command = str(packet["command"]).upper()
    protocol = str(packet["protocol"]).upper()
    if "id" in packet:
        return f"ZIA++{command} {protocol} ID {packet['id']}"
    if "address" in packet:
        return f"ZIA++{command} {protocol} {packet['address']}"
    raise Exception("No ID or Address found")


def serialize_packet_id(packet: PacketType) -> str:
    """Serialize packet identifiers into one reversible string."""
    return PACKET_ID_SEP.join(
        filter(
            None,
            [
                packet.get("protocol", None),
                packet.get("id", None),
                packet.get("switch", None),
            ],
        )
    )


def deserialize_packet_id(packet_id: str) -> Dict[str, str]:
    """Deserialize packet id."""
    if packet_id == "rfplayer":
        return {"protocol": "unknown"}

    if packet_id == "ZIA":
        return {"protocol": "ZIA++"}

    if packet_id.lower().startswith("chacon"):
        return {
            "protocol": "chacon",
            "address": packet_id.split(PACKET_ID_SEP)[1],
        }

    if packet_id.startswith("dooya_v4"):
        return {
            "protocol": "dooya_v4",
            "id": packet_id.replace("dooya_v4_", "").split(PACKET_ID_SEP)[0],
            "switch": packet_id.replace("dooya_v4_", "").split(PACKET_ID_SEP)[0],
        }

    packet_id_splited = packet_id.split(PACKET_ID_SEP)
    packet = {
        "protocol": packet_id_splited[0],
        "id": packet_id_splited[1],
    }
    if len(packet_id_splited) > 2:
        packet["switch"] = packet_id_splited[2]

    return packet


def packet_events(packet: PacketType) -> Generator[PacketType, None, None]:
    platform=None
    log.debug("packet:%s", str(packet))
    """Handle packet events."""
    field_abbrev = {
        v: k
        for k, v in sorted(
            PACKET_FIELDS.items(), key=lambda x: (x[1], x[0]), reverse=True
        )
    }

    packet_id = serialize_packet_id(packet)
    events = {f: v for f, v in packet.items() if f in field_abbrev}
    for f, v in packet.items():
        log.debug("f:%s,v:%s", f, v)
        if f == "platform":
            platform=v
        if f == "protocol":
            protocol=v
    for s, v in events.items():
        log.debug("event: %s -> %s", s, v)

    # try:
    #   packet["message"]
    #   yield { "id": packet_id, "message": packet["message"] }
    # except KeyError:
    for sensor, value in events.items():
        log.debug("packet_events, sensor:%s,value:%s", sensor, value)
        unit = packet.get(sensor + "_unit", None)
        yield {
            "id": packet_id + PACKET_ID_SEP + field_abbrev[sensor],
            sensor: sensor,
            "value": value,
            "unit": unit,
            "platform": platform,
            "protocol": protocol
        }
