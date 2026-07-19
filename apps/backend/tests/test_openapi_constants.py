from ox1audio_backend.main import app
from ox1audio_backend.shared_constants import build_openapi_constants


def test_openapi_includes_shared_constants():
    schema = app.openapi()
    constants = schema["x-ox1audio-constants"]
    expected = build_openapi_constants()

    assert constants["fallbackCoverColor"] == expected["fallbackCoverColor"]
    assert constants["allowedAudioExtensions"] == expected["allowedAudioExtensions"]
    assert constants["allowedImageMimeTypes"] == expected["allowedImageMimeTypes"]
    assert constants["coverColorRanking"] == expected["coverColorRanking"]
    assert constants["password"]["minLength"] == expected["password"]["minLength"]
    assert constants["password"]["maxLength"] == expected["password"]["maxLength"]
    assert [r["id"] for r in constants["password"]["rules"]] == [
        r["id"] for r in expected["password"]["rules"]
    ]
    assert len(constants["playlistColors"]) == len(expected["playlistColors"])
    assert constants["playlistColors"][0]["value"] == "light_blue"
    assert len(constants["playlistColors"][0]["hexes"]) == 3
