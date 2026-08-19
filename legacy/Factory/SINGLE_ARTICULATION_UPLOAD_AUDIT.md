# Single-Articulation Upload — Proof Audit

Datum: 12. august 2026.  
Release uticaj: `NOT PROVEN`

## Executive verdict

Uploadovani paket dokazuje dio konstrukcije probe fajlova, ali ne dokazuje nijedan Pa800 artikulacijski naziv. `articulation-results.json` nema rezultate, promotion queue je prazna, a CSV ima šest `pending_hardware` redova bez Pa800 OS-a, Musical Resources/SET verzije ili opisa čutog zvuka.

```text
SOFTWARE PROBE ENCODING = PARTIALLY PROVEN
HARDWARE ARTICULATION CLAIMS = UNPROVEN
AUTOMATIC EVIDENCE PROMOTION = NOT ALLOWED
```

## Fajlovi i SHA-256

| Probe | Fajl | Izračunati SHA-256 | Rezultat |
|---|---|---|---|
| 1 | `Finger_Bass_RX__Gliss__453b9e2487.mid` | `453b9e2487bb752138a4265c663d24c62ab7a11d01f320e17961b59051c32eda` | `PROVEN` artifact |
| 2 | `Pop_Std._Kit_RX__B1_C2__395b2bc518.mid` | `395b2bc51811cd9282b1c949603a19cc1175987b67cac57f60c950604327cf00` | `PROVEN` artifact |
| 3 | `Pop_Std._Kit_RX__D2_E2_layers__d77f63c504.mid` | `d77f63c50418c97c4c594dd128a3f027daed610f7a25b9f09edf35e46bc180f0` | `PROVEN` artifact |
| 4 | `Pop_Std._Kit_RX__F_2_layers__d388f5884d.mid` | `d388f5884dac4e0481059e05346127e8d4a3976965f2717cb9d274f05c8bf2e4` | `FAILED` manifest duration parity |
| 5 | `Pop_Std._Kit_RX__Single_layer__f253eff2b9.mid` | `f253eff2b9aa754fccf9d05e4290f7bd478644050c00b26aa7093152183a7bc3` | `FAILED` manifest duration parity |
| 6 | `Pop_Std._Kit_RX__G_2_A_2__ba9fd3d63a.mid` | `ba9fd3d63a149b206f683aeccf3eba9a7f3680a2a87182f572034486bb385c42` | `PROVEN` artifact |

Manifest ne sadrži posebno `output_sha256` polje. Deset heksadecimalnih znakova u filenameu odgovara početku izračunatog SHA-256 za svih šest fajlova, ali puni hash nije canonicalno commitovan manifestom.

## Dokazana MIDI svojstva

- Svih šest fajlova su validan SMF format 1 sa PPQ 384.
- Note-on/off parovi su balansirani; EOT je posljednji događaj i nema trailing bytesa.
- Svaki fajl ima tačno jedan manifestni trigger note-on; nema sweepa ni dodatnog trigger note-ona.
- Probe 1 ima tačno deklarisanu prethodnu i sljedeću context notu; probe 2–6 imaju samo trigger notu.
- Bank/Program adrese odgovaraju manifestu: `121/13/33` za Finger Bass RX i `120/0/4` za Pop Std. Kit RX.
- Izvorni Gold članovi postoje u `prism-uploads/DNA.zip`; njihov SHA, track/channel/tick, adresa, trigger nota i velocity odgovaraju manifestu.

## Neuspjele i kontradiktorne tvrdnje

### Probe 4 i 5 — duration mismatch

Manifest i izvor navode trajanje:

```text
43 / 384 = 0.1119791667 quarters
```

Oba probe MIDI fajla sadrže:

```text
48 / 384 = 0.125 quarters
```

Zato probe 4 i 5 nisu byte/event-vjerne manifestnom trigger durationu.

### Probe 4 i 5 — isti muzički payload

Oba fajla imaju istu adresu, kanal, notu 42, velocity 110, onset, duration, tempo i odsustvo context nota. Razlikuju se samo u metadata/nazivu. Trenutni MIDI sadržaj ne može dokazati da testiraju dvije različite artikulacije (`F#2 layers` i `Single layer`).

## UNPROVEN tvrdnje

- `Gliss`, `B1/C2`, `D2/E2 layers`, `F#2 layers`, `Single layer` i `G#2/A#2` kao stvarno čute Pa800 artikulacije.
- Manifestni `occurrence_count`, `file_count` i `candidates=39`, jer upload nema puni builder/config/corpus digest potreban za nezavisnu reprodukciju agregata.
- Tvrdnja da kompletna generacija nije koristila šest Delay/Terca pjesama; izabrani izvori jesu Gold članovi, ali kompletna candidate lineage nije commitovana ovim paketom.
- Veza ovog šest-fajlnog Gold paketa sa ranijim report claimom o 30 Factory-evidence probe fajlova. To su različite generacije i trenutni upload ne dokazuje tu tvrdnju.
- Production/trusted authority potpis cijelog paketa.

## Rezultati i promotion status

```text
articulation-results.json: history=0, latest=0
evidence-promotion-queue.json: ready=0, contradictions=0
SINGLE_ARTICULATION_CONFIRMATION.csv: 6 x pending_hardware
```

Nijedan claim nije spreman za Evidence Registry ili runtime promociju.

## Obavezni naredni koraci

1. Prije hardware testa riješiti probe 4/5: generisati dokazivo različite trigger uslove ili spojiti/ukloniti duplikat.
2. Regenerisati probe 4/5 bez duration clampa ili ažurirati manifest/source contract uz eksplicitno objašnjenje transformacije.
3. U canonical manifest dodati puni output SHA-256, builder/config/corpus digest i kompletnu candidate lineage.
4. Na Pa800 za svaki validni Probe ID zabilježiti status, stvarno čuti zvuk, Pa800 OS, Musical Resources/SET verziju, vrijeme testa i po mogućnosti audio-chain/recording dokaz.
5. Tek `confirmed` rezultat ide u `READY_FOR_EVIDENCE_REVIEW`; nikad direktno u runtime.
