from ox1audio_backend.services.artists import resolve_artist_names, split_artist_names


def test_split_artist_names_from_tag_separators():
    assert split_artist_names("Halvorsen, Division One & JJD") == [
        "Halvorsen",
        "Division One",
        "JJD",
    ]
    assert split_artist_names("Arcando feat. Vanessa Campagna") == [
        "Arcando",
        "Vanessa Campagna",
    ]


def test_space_glued_tag_stays_one_name():
    # Source TPE1 is often a single string with no separators.
    assert split_artist_names("Cajama Tisoki") == ["Cajama Tisoki"]
    assert split_artist_names("Alex Skrindo JJD") == ["Alex Skrindo JJD"]
    assert split_artist_names("Zeus X Crona") == ["Zeus X Crona"]


def test_resolve_prefers_multi_value_tags():
    assert resolve_artist_names(["Molly Ann", "JJD"]) == ["Molly Ann", "JJD"]
    assert resolve_artist_names(["Molly Ann, JJD"]) == ["Molly Ann", "JJD"]
