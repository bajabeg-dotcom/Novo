# legacy/ — arhiva prethodnih repozitorija

Ovaj folder je **nepromjenjiv**. Sluzi kao dokaz da nista iz ranijeg
rada nije izgubljeno pri konsolidaciji na v0.28.0.

Kod, testovi i dokumentacija su arhivirani u git. Veliki binarni
fajlovi nisu — ali je svaki zapisan ispod sa SHA-256, pa se moze
provjeriti i ponovo nabaviti iz izvornog repozitorija.

## Sazetak

| Repo | Arhivirano | Velicina | Izuzeto | Izuzeta velicina |
|---|---|---|---|---|
| `DNA` | 6 | 0.1 MB | 0 | 0.0 MB |
| `Factory` | 232 | 2.9 MB | 2 | 43.2 MB |
| `Jap` | 584 | 15.7 MB | 10 | 76.1 MB |
| `a` | 27 | 2.5 MB | 0 | 0.0 MB |
| `beg` | 3836 | 34.1 MB | 0 | 0.0 MB |
| **ukupno** | **4685** | **55.3 MB** | **12** | **119.2 MB** |

## Sadrzaj po repozitoriju

### `DNA`

song_midi_optimizer i song_midi_optimizer_pro skripte.

Izvor: https://github.com/bajabeg-dotcom/DNA

Nista nije izuzeto.

### `Factory`

GM->RX Studio: rxoptimizer (40 modula), 25 DNA baza, web GUI.

Izvor: https://github.com/bajabeg-dotcom/Factory

Izuzeto 2 velikih fajlova (43.2 MB):

| Fajl | Velicina | SHA-256 |
|---|---|---|
| `Pa800-201UM-ENG.pdf` | 22.3 MB | `b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b` |
| `prism-uploads/DNA.zip` | 20.9 MB | `125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a` |

### `Jap`

python-midi-enhancer: 30 modula M01-M10/K01-K03, 28 testova, K01 registar.

Izvor: https://github.com/bajabeg-dotcom/Jap

Izuzeto 10 velikih fajlova (76.1 MB):

| Fajl | Velicina | SHA-256 |
|---|---|---|
| `python-midi-enhancer/prism-uploads/Pa800-201UM-ENG.pdf` | 22.3 MB | `b7df16fb0113d998a6411ea1c28971707021da8bc0b728aff98eafcceb57c71b` |
| `python-midi-enhancer/prism-uploads/DNA.zip` | 20.9 MB | `125f4486625db44f7cdd49bd670aff252a961c88ea14741ec970ec3ae5eec85a` |
| `python-midi-enhancer/prism-uploads/Split Factory Styles.zip` | 14.8 MB | `ffb95cc191ba2bfc0c9b2b09494adaeb61c61bcda0fa4a9e4d83302e281d8f5e` |
| `python-midi-enhancer/prism-uploads/Pa800_AE_E.pdf` | 4.2 MB | `6bcda56658a89eda31e9fe62a2b744df5cecaaf478e050d3256ad6440c0d413e` |
| `python-midi-enhancer/loaded-data/xvfb-runtime/packages/xvfb_2%3a21.1.16-1.3+deb13u3_amd64.deb` | 3.0 MB | `365da2b6c93339f34337c434a9489bb6411a240fa47b9f49693d3091745f28c2` |
| `python-midi-enhancer/loaded-data/xvfb-runtime/packages/xserver-common_2%3a21.1.16-1.3+deb13u3_all.deb` | 2.3 MB | `dc1d37303c103b23c40cd1ea694c5c6561e0e8dc1734a73c7a0ae0ef080e7fcc` |
| `python-midi-enhancer/loaded-data/xvfb-runtime/root/usr/share/doc/xserver-common/changelog.gz` | 2.3 MB | `ec5f0e2507c1114b1d9901a63edb69e60d403465c905347a78d52d236563ab23` |
| `python-midi-enhancer/loaded-data/xvfb-runtime/root/usr/share/doc/xvfb/changelog.gz` | 2.3 MB | `ec5f0e2507c1114b1d9901a63edb69e60d403465c905347a78d52d236563ab23` |
| `python-midi-enhancer/loaded-data/xvfb-runtime/root/usr/bin/Xvfb` | 2.0 MB | `14e8ec7d8209bbaf105f9ade27a80b65f01709346690d18fbadb6116ada34912` |
| `python-midi-enhancer/loaded-data/xvfb-runtime/root/usr/bin/Xvfb-local` | 2.0 MB | `55f1307458dca0da274dd54b8d3f6532ee5ca8b1c6f617b5176e2fca55276e22` |

### `a`

Prva generacija: midi_optimizer CLI/GUI/core, forenzicki izvjestaji.

Izvor: https://github.com/bajabeg-dotcom/a

Nista nije izuzeto.

### `beg`

korg_pa800_optimizer + x10_think_midi + factory_intelligence.

Izvor: https://github.com/bajabeg-dotcom/beg

Nista nije izuzeto.
