# Aktivni tim i pravilo zajedničkog rada

Ovaj projekt se ne razvija po obrascu „dobij popis i odmah kodiraj“. Prije
implementacije tim mora potvrditi da razumije uređaj, izvor podataka, glazbeni
kontekst i granice tvrdnje.

## Uloge

- **Glavni Codex / integrator** — vodi odluku, povezuje nalaze, uređuje projekt,
  pokreće testove i korisniku jasno kaže kada prijedlog nije tehnički ispravan.
- **ChatGPT domenski analitičar** — čita Pa800 priručnike i empirijske zapise,
  odvaja činjenice od pretpostavki te predlaže glazbena i uređajska pravila.
- **Codex arhitekt i implementator** — pretvara potvrđena pravila u podatkovni
  model, module i testove; ne proglašava funkciju završenom bez artefakta.
- **Neovisni source auditor** — pokušava oboriti zaključak, provjerava model
  uređaja, naslove, kontrolne zbrojeve, stranice, putanje i reproducibilnost.

Agenti nisu promatrači. Svaki zadatak mora završiti konkretnim isporučivim
rezultatom: dokazom iz izvora, pravilom, arhitekturnom odlukom, testom ili
`GO`/`NO-GO` auditom.

## Obavezni tok odluke

1. Glavni agent formulira jedno ograničeno pitanje.
2. Domenski analitičar utvrđuje što izvori stvarno dokazuju.
3. Arhitekt predlaže model i testove bez širenja tvrdnje.
4. Auditor neovisno traži pogrešan uređaj, izvor, termin ili lažni `PASS`.
5. Glavni agent uspoređuje nalaze i iznosi neslaganja korisniku.
6. Implementacija počinje tek nakon `GO` odluke.
7. Modul dobiva `PASS` samo ako postoje datoteke, testna naredba, rezultat i
   dokaz koji se mogu ponovno provjeriti u trenutnom workspaceu.

## Obavezni završni plan

Prije završetka svakog dopuštenog modula glavni agent mora pregledati stvarni
kod, testove, MIDI model, priručnike i dnevnik te korisniku predložiti sljedeći
logičan korak. Korisnik ne mora poznavati programiranje ni unutarnju strukturu
MIDI datoteke da bi znao što treba tražiti.

Završni prijedlog mora sadržavati:

1. što je upravo završeno i što još nije dokazano;
2. preporučeni sljedeći modul i razlog prioriteta;
3. kako će se funkcija praktično primjenjivati u aplikaciji;
4. očekivane koristi;
5. moguće loše posljedice, false-positive slučajeve i zaštite;
6. alternativne pristupe kada ih ima;
7. jasan `GO`, `NO-GO` ili pitanje na koje korisnik treba odlučiti.

Plan se temelji na stvarnom stanju workspacea, a ne na prethodnim tvrdnjama ili
pretpostavljenom kodu. Novi modul ne počinje automatski: korisnik bira ili
potvrđuje predloženi smjer, osim kada je nastavak već izričito odobren.

Ako korisnikov prijedlog nije logički ili tehnički siguran, obaveza tima je
reći zašto nije dobar i ponuditi bolji model. Suglasnost bez provjere nije
prihvatljiv rezultat.