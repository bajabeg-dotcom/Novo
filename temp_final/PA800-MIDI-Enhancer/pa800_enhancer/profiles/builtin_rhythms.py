from .models import RhythmProfile


def _profile(profile_id, name, meters, groupings=(), aliases=(), notes=""):
    return RhythmProfile(profile_id, name, tuple(meters), tuple(groupings), tuple(aliases), notes)


RHYTHM_PROFILES = {
    profile.profile_id: profile
    for profile in (
        _profile("rumba", "Rumba", ((4, 4),), ("3-2 clave", "2-3 clave")),
        _profile("beguine", "Beguine", ((4, 4),), aliases=("Begin",)),
        _profile("ballad", "Balada", ((4, 4), (6, 8), (12, 8))),
        _profile("beat", "Beat", ((4, 4),), ("8 Beat", "16 Beat", "shuffle")),
        _profile("sirtaki", "Sirtaki", ((4, 4), (2, 4)), notes="May accelerate from hasapiko to hasaposerviko feel."),
        _profile("six_eight", "6/8", ((6, 8),), ("3+3",)),
        _profile("seven_eight", "7/8", ((7, 8),), ("2+2+3", "2+3+2", "3+2+2")),
        _profile("nine_eight", "9/8", ((9, 8),), ("3+3+3", "2+2+2+3", "2+2+3+2", "2+3+2+2", "3+2+2+2")),
        _profile("disco", "Disco", ((4, 4),), ("four-on-the-floor",)),
        _profile("oriental", "Orijental", ((2, 4), (4, 4), (6, 8), (7, 8), (8, 4), (9, 8), (10, 8)), aliases=("Maqsum", "Baladi", "Saidi", "Ayyub", "Malfuf", "Wahda", "Masmudi", "Samai")),
    )
}