"""Dependency-free Standard MIDI File reader/writer."""

from __future__ import annotations
from dataclasses import dataclass, field
import struct


class MidiError(ValueError):
    pass


def read_vlq(data: bytes, pos: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if pos >= len(data):
            raise MidiError("Neočekivan kraj VLQ vrijednosti")
        byte = data[pos]; pos += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, pos
    raise MidiError("Nevažeća VLQ vrijednost")


def write_vlq(value: int) -> bytes:
    value = max(0, int(value)); result = [value & 0x7F]; value >>= 7
    while value:
        result.append(0x80 | (value & 0x7F)); value >>= 7
    return bytes(reversed(result))


@dataclass
class Event:
    tick: int
    order: float
    kind: str
    channel: int | None = None
    data1: int | None = None
    data2: int | None = None
    status: int | None = None
    raw: bytes = b""


@dataclass
class MidiFile:
    format: int
    division: int
    tracks: list[list[Event]] = field(default_factory=list)


def parse_midi(data: bytes) -> MidiFile:
    if len(data) < 14 or data[:4] != b"MThd":
        raise MidiError("Fajl nije Standard MIDI File")
    header_len = struct.unpack(">I", data[4:8])[0]
    if header_len < 6 or 8 + header_len > len(data):
        raise MidiError("Nevažeća dužina MIDI zaglavlja")
    fmt, track_count, division = struct.unpack(">HHH", data[8:14])
    if division & 0x8000:
        raise MidiError("SMPTE time division nije podržan")
    pos = 8 + header_len; tracks = []
    for _ in range(track_count):
        if pos + 8 > len(data):
            raise MidiError("Prekinut MTrk header")
        if data[pos:pos + 4] != b"MTrk":
            raise MidiError("Nedostaje MTrk blok")
        length = struct.unpack(">I", data[pos + 4:pos + 8])[0]
        if pos + 8 + length > len(data):
            raise MidiError("Deklarisana MTrk dužina prelazi fajl")
        tracks.append(_parse_track(data[pos + 8:pos + 8 + length]))
        pos += 8 + length
    return MidiFile(fmt, division, tracks)


def _parse_track(chunk: bytes) -> list[Event]:
    events = []; pos = tick = order = 0; running = None
    while pos < len(chunk):
        delta, pos = read_vlq(chunk, pos); tick += delta
        if pos >= len(chunk): raise MidiError("Prekinut MIDI događaj")
        if chunk[pos] & 0x80:
            status = chunk[pos]; pos += 1
        elif running is not None:
            status = running
        else:
            raise MidiError("Running status bez prethodnog statusa")
        if status == 0xFF:
            running = None
            if pos >= len(chunk): raise MidiError("Prekinut meta tip")
            meta_type = chunk[pos]; pos += 1
            size, pos = read_vlq(chunk, pos)
            if pos + size > len(chunk): raise MidiError("Prekinut meta payload")
            payload = chunk[pos:pos + size]; pos += size
            events.append(Event(tick, order, "meta", data1=meta_type, raw=payload))
        elif status in (0xF0, 0xF7):
            running = None; size, pos = read_vlq(chunk, pos)
            if pos + size > len(chunk): raise MidiError("Prekinut SysEx payload")
            payload = chunk[pos:pos + size]; pos += size
            events.append(Event(tick, order, "sysex", status=status, raw=payload))
        else:
            running = status; family = status & 0xF0; channel = status & 0x0F
            size = 1 if family in (0xC0, 0xD0) else 2
            if pos + size > len(chunk): raise MidiError("Prekinuta channel poruka")
            d1 = chunk[pos]; d2 = chunk[pos + 1] if size == 2 else None; pos += size
            kind = {0x80:"note_off",0x90:"note_on",0xA0:"poly_pressure",0xB0:"control",0xC0:"program",0xD0:"pressure",0xE0:"pitch"}.get(family,"channel")
            if kind == "note_on" and d2 == 0: kind = "note_off"
            events.append(Event(tick, order, kind, channel, d1, d2, status))
        order += 1
    return events


def encode_midi(midi: MidiFile) -> bytes:
    header = b"MThd" + struct.pack(">IHHH", 6, midi.format, len(midi.tracks), midi.division)
    chunks = []
    for events in midi.tracks:
        body = bytearray(); previous = 0
        # End-of-Track must be the final event, including after optimized
        # note-offs that may have moved beyond the original EOT tick.
        ordered = sorted((e for e in events if not (e.kind=="meta" and e.data1==0x2F)), key=lambda e:(e.tick,e.order))
        ordered.append(Event(max((e.tick for e in ordered),default=0),10**9,"meta",data1=0x2F))
        for event in ordered:
            body.extend(write_vlq(event.tick - previous)); previous = event.tick
            if event.kind == "meta":
                body.extend((0xFF,int(event.data1 or 0))); body.extend(write_vlq(len(event.raw))); body.extend(event.raw)
            elif event.kind == "sysex":
                body.append(int(event.status or 0xF0)); body.extend(write_vlq(len(event.raw))); body.extend(event.raw)
            else:
                status = int(event.status or _status_for(event)); body.extend((status,int(event.data1 or 0)))
                if (status & 0xF0) not in (0xC0,0xD0): body.append(int(event.data2 or 0))
        chunks.append(b"MTrk" + struct.pack(">I",len(body)) + bytes(body))
    return header + b"".join(chunks)


def _status_for(event: Event) -> int:
    family = {"note_off":0x80,"note_on":0x90,"poly_pressure":0xA0,"control":0xB0,"program":0xC0,"pressure":0xD0,"pitch":0xE0}[event.kind]
    return family | int(event.channel or 0)


def note_rows(midi: MidiFile) -> list[dict]:
    rows = []
    for track_index, events in enumerate(midi.tracks):
        active = {}
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            key = (int(event.channel or 0),int(event.data1 or 0))
            if event.kind == "note_on" and event.data2:
                active.setdefault(key,[]).append(event)
            elif event.kind == "note_off" and active.get(key):
                start = active[key].pop(0)
                rows.append({"track":track_index,"channel":key[0],"note":key[1],"start":start.tick,
                    "duration":max(1,event.tick-start.tick),"velocity":int(start.data2 or 1),"on_event":start,"off_event":event})
    return rows


def validate_midi(midi: MidiFile) -> dict:
    """Return semantic invariants used before accepting an optimizer export."""
    unmatched_off=invalid_values=0; active={}; note_on=note_off=0
    for track_index,events in enumerate(midi.tracks):
        for event in sorted(events,key=lambda e:(e.tick,e.order)):
            for value in (event.data1,event.data2):
                if value is not None and not 0 <= int(value) <= 127: invalid_values+=1
            if event.channel is not None and not 0 <= int(event.channel) <= 15: invalid_values+=1
            if event.kind=="note_on" and int(event.data2 or 0)>0:
                key=(track_index,int(event.channel or 0),int(event.data1 or 0)); active[key]=active.get(key,0)+1; note_on+=1
            elif event.kind=="note_off":
                key=(track_index,int(event.channel or 0),int(event.data1 or 0)); note_off+=1
                if active.get(key,0): active[key]-=1
                else: unmatched_off+=1
    unmatched_on=sum(active.values())
    return {"note_on":note_on,"note_off":note_off,"unmatched_note_on":unmatched_on,
            "unmatched_note_off":unmatched_off,"invalid_values":invalid_values,
            "valid":invalid_values==0 and unmatched_on==0 and unmatched_off==0}


def to_mido_file(midi: MidiFile) -> "mido.MidiFile":
    """Konvertuj interni MidiFile format u mido.MidiFile za RX/Korg obradu."""
    import mido
    
    mid = mido.MidiFile(ticks_per_beat=midi.division)
    
    for track_events in midi.tracks:
        mido_track = mido.MidiTrack()
        mid.tracks.append(mido_track)
        
        # Sortiraj evente po tick i order
        sorted_events = sorted(track_events, key=lambda e: (e.tick, e.order))
        
        last_tick = 0
        for event in sorted_events:
            delta = event.tick - last_tick
            
            if event.kind == "note_on":
                mido_track.append(mido.Message(
                    'note_on', 
                    channel=event.channel, 
                    note=event.data1, 
                    velocity=event.data2 or 0,
                    time=delta
                ))
            elif event.kind == "note_off":
                mido_track.append(mido.Message(
                    'note_off',
                    channel=event.channel,
                    note=event.data1,
                    velocity=event.data2 or 0,
                    time=delta
                ))
            elif event.kind == "control":
                mido_track.append(mido.Message(
                    'control_change',
                    channel=event.channel,
                    control=event.data1,
                    value=event.data2 or 0,
                    time=delta
                ))
            elif event.kind == "program":
                mido_track.append(mido.Message(
                    'program_change',
                    channel=event.channel,
                    program=event.data1 or 0,
                    time=delta
                ))
            elif event.kind == "pitch":
                mido_track.append(mido.Message(
                    'pitchwheel',
                    channel=event.channel,
                    pitch=((event.data2 or 0) << 7) | (event.data1 or 0),
                    time=delta
                ))
            elif event.kind == "meta":
                if event.data1 == 0x51:  # Tempo
                    mido_track.append(mido.MetaMessage(
                        'set_tempo',
                        tempo=int.from_bytes(event.raw, 'big'),
                        time=delta
                    ))
                elif event.data1 == 0x58:  # Time signature
                    if len(event.raw) >= 4:
                        mido_track.append(mido.MetaMessage(
                            'time_signature',
                            numerator=event.raw[0],
                            denominator=2**event.raw[1],
                            clocks_per_click=event.raw[2],
                            notated_32nd_notes_per_beat=event.raw[3],
                            time=delta
                        ))
                elif event.data1 in (1, 3):  # Text
                    try:
                        text = event.raw.decode('latin1')
                        msg_type = 'text' if event.data1 == 1 else 'track_name'
                        mido_track.append(mido.MetaMessage(
                            msg_type,
                            text=text,
                            time=delta
                        ))
                    except:
                        pass
            else:
                # Ostali eventovi - preskoči ili dodaj kao generic
                if delta > 0:
                    mido_track.append(mido.Message('marker', time=delta))
            
            last_tick = event.tick
        
        # Dodaj End of Track
        mido_track.append(mido.MetaMessage('end_of_track', time=0))
    
    return mid


def from_mido_file(mid: "mido.MidiFile") -> MidiFile:
    """Konvertuj mido.MidiFile nazad u interni MidiFile format."""
    midi = MidiFile(format=mid.type, division=mid.ticks_per_beat)
    
    for mido_track in mid.tracks:
        track_events = []
        current_tick = 0
        
        for msg in mido_track:
            current_tick += msg.time
            
            if msg.type == 'note_on':
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='note_on',
                    channel=msg.channel,
                    data1=msg.note,
                    data2=msg.velocity
                ))
            elif msg.type == 'note_off':
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='note_off',
                    channel=msg.channel,
                    data1=msg.note,
                    data2=msg.velocity
                ))
            elif msg.type == 'control_change':
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='control',
                    channel=msg.channel,
                    data1=msg.control,
                    data2=msg.value
                ))
            elif msg.type == 'program_change':
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='program',
                    channel=msg.channel,
                    data1=msg.program
                ))
            elif msg.type == 'pitchwheel':
                pitch = msg.pitch
                data1 = pitch & 0x7F
                data2 = (pitch >> 7) & 0x7F
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='pitch',
                    channel=msg.channel,
                    data1=data1,
                    data2=data2
                ))
            elif msg.type == 'set_tempo':
                tempo_bytes = msg.tempo.to_bytes(3, 'big')
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='meta',
                    data1=0x51,
                    raw=tempo_bytes
                ))
            elif msg.type == 'time_signature':
                raw = bytes([
                    msg.numerator,
                    int(math.log2(msg.denominator)) if msg.denominator > 0 else 2,
                    msg.clocks_per_click,
                    msg.notated_32nd_notes_per_beat
                ])
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='meta',
                    data1=0x58,
                    raw=raw
                ))
            elif msg.type in ('text', 'track_name'):
                meta_type = 0x01 if msg.type == 'text' else 0x03
                track_events.append(Event(
                    tick=current_tick,
                    order=0,
                    kind='meta',
                    data1=meta_type,
                    raw=msg.text.encode('latin1')
                ))
        
        midi.tracks.append(track_events)
    
    return midi
    return {"note_on":note_on,"note_off":note_off,"unmatched_note_on":unmatched_on,
            "unmatched_note_off":unmatched_off,"invalid_values":invalid_values,
            "valid":invalid_values==0 and unmatched_on==0 and unmatched_off==0}