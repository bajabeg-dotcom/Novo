from __future__ import annotations

import json, random
from dataclasses import asdict, dataclass
from pathlib import Path

from .analysis.notes import pair_notes
from .corpus import CorpusRunner
from .dna import classify_note_roles

GENERATOR_SCHEMA_VERSION = 2
ROLES = ("solo", "accompaniment", "bass", "drums", "guitar")
ROLE_CHANNEL = {"solo": 0, "accompaniment": 1, "bass": 3, "drums": 9, "guitar": 2}
ROLE_PROGRAM = {"solo": 65, "accompaniment": 48, "bass": 33, "drums": 0, "guitar": 30}
ROLE_RANGE = {"solo": (48, 100), "accompaniment": (32, 88), "bass": (28, 67), "guitar": (40, 88)}
DRUM_NOTES = (35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,59)
KEYS = {name:index for index,name in enumerate(("C","C#","D","D#","E","F","F#","G","G#","A","A#","B"))}
SCALES = {"major":(0,2,4,5,7,9,11), "minor":(0,2,3,5,7,8,10)}

@dataclass(frozen=True, slots=True)
class GeneratorConfig:
    hidden_size: int = 192
    layers: int = 2
    sequence_length: int = 64
    ppq: int = 480
    step_ticks: int = 120

@dataclass(frozen=True, slots=True)
class TrainingReport:
    examples: int; epochs: int; final_loss: float; checkpoint: str; device: str

@dataclass(frozen=True, slots=True)
class SongForm:
    bars: int = 32
    steps_per_bar: int = 16
    phrase_bars: int = 8

@dataclass(frozen=True, slots=True)
class StylePreset:
    name: str; tempo: int; density: float; swing: float; fill_strength: int

STYLE_PRESETS = {
    "pop": StylePreset("pop",120,1.0,0.0,2),
    "ballad": StylePreset("ballad",76,0.68,0.0,1),
    "dance": StylePreset("dance",128,1.15,0.0,3),
    "folk": StylePreset("folk",108,1.05,0.08,3),
    "rock": StylePreset("rock",116,1.10,0.0,3),
}

def encode_song(song, role: str) -> list[tuple[int,int,int,int,int]]:
    notes, _ = pair_notes(song); roles = classify_note_roles(song, notes)
    programs={}
    for track in song.tracks:
        for event in sorted(track.events,key=lambda item:(item.absolute_tick,item.order)):
            if event.channel and event.message_type==0xC0 and event.data: programs[event.channel]=event.data[0]
    def resolved(note):
        return "bass" if 32 <= programs.get(note.channel,-1) <= 39 else roles.get(note.on_event_id)
    selected = sorted((n for n in notes if resolved(n)==role), key=lambda n:(n.start_tick,n.note))
    ppq = song.header.ppq or 96; previous = 0; output=[]
    for note in selected:
        delta=max(0,min(64,round((note.start_tick-previous)/(ppq/4))))
        duration=max(1,min(64,round((note.end_tick-note.start_tick)/(ppq/4))))
        output.append((ROLES.index(role),note.note,delta,duration,min(15,note.velocity//8)))
        previous=note.start_tick
    return output

def build_sequences(sources: tuple[Path,...], config: GeneratorConfig, *, gold_weight: int=4,
                    limit: int|None=None) -> list[list[tuple[int,int,int,int,int]]]:
    runner=CorpusRunner(); result=[]
    for locator,data in runner.iter_midi(sources):
        folded=locator.casefold(); weight=gold_weight if "gold dna.zip" in folded else 1
        try: song=runner.reader.parse(data)
        except ValueError: continue
        for role in ROLES:
            encoded=encode_song(song,role)
            for start in range(0,max(0,len(encoded)-config.sequence_length),config.sequence_length):
                seq=encoded[start:start+config.sequence_length+1]
                if len(seq)==config.sequence_length+1: result.extend([seq]*weight)
                if limit and len(result)>=limit: return result[:limit]
    return result

def _torch():
    try: import torch
    except ImportError as error: raise RuntimeError("install generator dependencies: pip install -e .[generator]") from error
    return torch

def create_model(config: GeneratorConfig):
    torch=_torch(); nn=torch.nn
    class MidiGru(nn.Module):
        def __init__(self):
            super().__init__(); h=config.hidden_size
            self.emb=nn.ModuleList([nn.Embedding(len(ROLES),16),nn.Embedding(128,48),nn.Embedding(65,24),nn.Embedding(65,24),nn.Embedding(16,16)])
            self.gru=nn.GRU(128,h,config.layers,batch_first=True,dropout=.1 if config.layers>1 else 0)
            self.heads=nn.ModuleList([nn.Linear(h,n) for n in (len(ROLES),128,65,65,16)])
        def forward(self,x,state=None):
            z=torch.cat([e(x[:,:,i]) for i,e in enumerate(self.emb)],dim=-1)
            y,state=self.gru(z,state); return tuple(head(y) for head in self.heads),state
    return MidiGru()

def train_generator(sources: tuple[Path,...], checkpoint: Path, *, config=GeneratorConfig(), epochs=2,
                    batch_size=16, learning_rate=2e-3, threads=2, seed=0, limit=None, resume=False):
    torch=_torch(); torch.manual_seed(seed); torch.set_num_threads(max(1,threads))
    sequences=build_sequences(sources,config,limit=limit)
    if not sequences: raise ValueError("reference corpus produced no training sequences")
    tensor=torch.tensor(sequences,dtype=torch.long); dataset=torch.utils.data.TensorDataset(tensor[:,:-1],tensor[:,1:])
    loader=torch.utils.data.DataLoader(dataset,batch_size=batch_size,shuffle=True)
    model=create_model(config); optimizer=torch.optim.AdamW(model.parameters(),lr=learning_rate); start_epoch=0
    if resume and checkpoint.exists():
        saved=torch.load(checkpoint,map_location="cpu",weights_only=False)
        if saved.get("schema_version") != GENERATOR_SCHEMA_VERSION or tuple(saved.get("roles",())) != ROLES: raise ValueError("cannot resume an incompatible generator checkpoint")
        model.load_state_dict(saved["model"]); optimizer.load_state_dict(saved["optimizer"]); start_epoch=saved["epoch"]
    loss_value=0.0; model.train()
    for epoch in range(start_epoch,start_epoch+epochs):
        for x,y in loader:
            optimizer.zero_grad(); outputs,_=model(x); loss=sum(torch.nn.functional.cross_entropy(out.reshape(-1,out.shape[-1]),y[:,:,i].reshape(-1)) for i,out in enumerate(outputs))
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),1.0); optimizer.step(); loss_value=float(loss.detach())
        checkpoint.parent.mkdir(parents=True,exist_ok=True)
        torch.save({"schema_version":GENERATOR_SCHEMA_VERSION,"roles":ROLES,"model":model.state_dict(),"optimizer":optimizer.state_dict(),"epoch":epoch+1,"config":asdict(config)},checkpoint)
    return TrainingReport(len(sequences),epochs,round(loss_value,6),str(checkpoint),"cpu")

def _sample(logits, temperature, top_k, generator):
    torch=_torch(); logits=logits/max(.05,temperature)
    if top_k>0:
        values,_=torch.topk(logits,min(top_k,logits.numel())); logits=torch.where(logits<values[-1],torch.tensor(float("-inf")),logits)
    return int(torch.multinomial(torch.softmax(logits,dim=-1),1,generator=generator))

def generate_notes(checkpoint: Path, role: str, count: int, *, temperature=0.9, top_k=12, seed=0):
    if role not in ROLES: raise ValueError(f"unknown role {role}")
    torch=_torch(); saved=torch.load(checkpoint,map_location="cpu",weights_only=False)
    if saved.get("schema_version") != GENERATOR_SCHEMA_VERSION or tuple(saved.get("roles",())) != ROLES: raise ValueError("checkpoint generator schema/roles are incompatible; retrain with the current version")
    config=GeneratorConfig(**saved["config"])
    model=create_model(config); model.load_state_dict(saved["model"]); model.eval(); gen=torch.Generator().manual_seed(seed)
    current=torch.tensor([[[ROLES.index(role),60,0,4,10]]]); state=None; output=[]
    with torch.inference_mode():
        for _ in range(count):
            heads,state=model(current,state); values=[ROLES.index(role)]
            for i in range(1,5): values.append(_sample(heads[i][0,-1],temperature,top_k,gen))
            if role == "drums": values[1]=min(DRUM_NOTES,key=lambda note:abs(note-values[1]))
            else:
                low,high=ROLE_RANGE[role]; values[1]=max(low,min(high,values[1]))
            values[3]=max(1,values[3]); output.append(tuple(values)); current=torch.tensor([[values]])
    return output,config

def arrange_harmonically(notes, role: str, *, key: str="C", scale: str="major", progression=(0,4,5,3), steps_per_bar=16):
    if key not in KEYS or scale not in SCALES: raise ValueError("unsupported key or scale")
    allowed={(KEYS[key]+degree)%12 for degree in SCALES[scale]}; result=[]; position=0
    for role_id,pitch,delta,duration,velocity in notes:
        position+=delta; bar=position//steps_per_bar; degree=progression[bar%len(progression)]%7
        root=(KEYS[key]+SCALES[scale][degree])%12
        if role=="bass":
            pitch=max(28,min(67,36+root + (12 if pitch>=48 else 0)))
        elif role=="guitar":
            base=max(40,min(76,pitch-(pitch-root)%12)); result.append((role_id,base,delta,duration,velocity))
            result.append((role_id,min(88,base+7),0,duration,max(1,velocity-1)))
            if base+12<=88: result.append((role_id,base+12,0,duration,max(1,velocity-2)))
            continue
        elif role!="drums" and pitch%12 not in allowed:
            pitch=min(range(max(0,pitch-2),min(127,pitch+2)+1),key=lambda candidate:(candidate%12 not in allowed,abs(candidate-pitch)))
        result.append((role_id,pitch,delta,duration,velocity))
    return result

def fit_song_form(notes, role: str, form: SongForm=SongForm(), *, style: StylePreset=STYLE_PRESETS["pop"]):
    """Loop a learned phrase into a common form and add section-aware dynamics/fills."""
    if form.bars < 4 or form.steps_per_bar < 4: raise ValueError("song form is too short")
    source=[]; position=0
    for item in notes:
        position += item[2]; source.append((position,item))
    if not source: return []
    source_span=max(1,source[-1][0]); total=form.bars*form.steps_per_bar
    absolute=[]
    for source_position,item in source:
        at=min(total-1,round(source_position/source_span*(total-1)))
        bar=at//form.steps_per_bar; phase=bar/max(1,form.bars-1)
        section=(bar//form.phrase_bars)%4
        variation=(1,2,3,4)[section]
        keep_ratio=min(1.0,style.density*(0.55+variation*0.12))
        stable=((source_position*131 + item[2]*17 + ROLES.index(role)*29)%1000)/1000
        if stable>keep_ratio: continue
        if style.swing and at%4==2: at=min(total-1,at+max(1,round(style.swing*form.steps_per_bar/4)))
        adjustment=(-10 if section==0 else 4 if section in (1,3) else 0) + round(6*__import__("math").sin(__import__("math").pi*phase))
        velocity=max(1,min(15,item[4]+round(adjustment/8)))
        scaled_duration=max(1,round(item[3]*total/source_span))
        absolute.append([at,item[0],item[1],min(64,scaled_duration),velocity])
    if role=="drums":
        for bar in range(form.phrase_bars-1,form.bars,form.phrase_bars):
            start=bar*form.steps_per_bar+form.steps_per_bar-4
            fill=(38,) if style.fill_strength==1 else (45,47,38) if style.fill_strength==2 else (45,47,50,38)
            start=bar*form.steps_per_bar+form.steps_per_bar-len(fill)
            for offset,pitch in enumerate(fill):
                absolute.append([start+offset,ROLES.index("drums"),pitch,1,12+min(offset,3)])
    absolute.sort(key=lambda item:(item[0],item[2])); output=[]; previous=0
    for at,role_id,pitch,duration,velocity in absolute:
        output.append((role_id,pitch,max(0,at-previous),duration,velocity)); previous=at
    return output

def write_generated_midi(path: Path, role_notes: dict[str,list[tuple[int,int,int,int,int]]], config: GeneratorConfig, tempo=120, bars: int|None=None):
    import mido
    midi=mido.MidiFile(type=1,ticks_per_beat=config.ppq); meta=mido.MidiTrack(); midi.tracks.append(meta)
    song_ticks=(bars or 0)*config.ppq*4
    meta.append(mido.MetaMessage("set_tempo",tempo=mido.bpm2tempo(tempo),time=0)); meta.append(mido.MetaMessage("time_signature",numerator=4,denominator=4,time=0)); meta.append(mido.MetaMessage("end_of_track",time=song_ticks))
    for role,notes in role_notes.items():
        track=mido.MidiTrack(); midi.tracks.append(track); channel=ROLE_CHANNEL[role]
        if role=="drums": track.append(mido.Message("control_change",channel=channel,control=0,value=120,time=0)); track.append(mido.Message("program_change",channel=channel,program=4,time=0))
        else: track.append(mido.Message("program_change",channel=channel,program=ROLE_PROGRAM[role],time=0))
        records=[]; tick=0; active_by_pitch={}
        for _,pitch,delta,duration,velocity in notes:
            tick+=delta*config.step_ticks; end=tick+max(1,duration)*config.step_ticks
            if song_ticks: end=min(song_ticks,max(tick+1,end))
            vel=max(1,min(127,velocity*8+4))
            previous_index=active_by_pitch.get(pitch)
            if previous_index is not None and records[previous_index][0] == tick:
                records[previous_index][1]=max(records[previous_index][1],end)
                records[previous_index][3]=max(records[previous_index][3],vel)
                continue
            if previous_index is not None and records[previous_index][1] > tick:
                records[previous_index][1]=max(records[previous_index][0]+1,tick)
            records.append([tick,end,pitch,vel]); active_by_pitch[pitch]=len(records)-1
        events=[]
        for start,end,pitch,vel in records: events.extend([(start,1,pitch,vel),(end,0,pitch,0)])
        previous=0
        for at,on,pitch,vel in sorted(events,key=lambda x:(x[0],x[1])):
            track.append(mido.Message("note_on" if on else "note_off",channel=channel,note=pitch,velocity=vel,time=at-previous)); previous=at
        track.append(mido.MetaMessage("end_of_track",time=max(0,song_ticks-previous)))
    path.parent.mkdir(parents=True,exist_ok=True); midi.save(path)
