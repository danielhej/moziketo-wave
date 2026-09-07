from app.services.media import extract_wp_media, resolve_audio_url, resolve_cover_url


def test_extract_wp_media_prefers_stream_url() -> None:
    audio, cover, duration = extract_wp_media(
        {
            "stream_url": "https://example.com/track.mp3",
            "download_url": "https://example.com/download.mp3",
            "_moziketo_cover_source": "https://example.com/cover.jpg",
            "_moziketo_duration_sec": "210",
        }
    )
    assert audio == "https://example.com/track.mp3"
    assert cover == "https://example.com/cover.jpg"
    assert duration == 210


def test_extract_wp_media_empty_meta() -> None:
    assert extract_wp_media(None) == (None, None, None)
    assert extract_wp_media({}) == (None, None, None)


def test_resolve_urls_never_synthesize_dl_placeholders() -> None:
    assert resolve_audio_url("any-slug", None) is None
    assert resolve_cover_url("any-slug", None) is None
    assert resolve_audio_url("x", "https://dl.moziketo.ir/music/x.mp3") is None
    assert resolve_cover_url("x", "https://dl.moziketo.ir/music/x.jpg") is None


def test_resolve_urls_return_stored_real_media() -> None:
    audio = "https://moziketo.s3.ir-thr-at1.arvanstorage.ir/music/test.mp3"
    cover = "https://i.scdn.co/image/example"
    assert resolve_audio_url("test", audio) == audio
    assert resolve_cover_url("test", cover) == cover
