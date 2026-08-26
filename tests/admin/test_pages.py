def _settings_form(**overrides) -> dict:
    data = {
        "name": "Test Name",
        "kurzprofil": "Profil.",
        "hinweis": "",
        "kontakt_email": "test@example.dev",
        "impressum_name": "Test Name",
        "impressum_anschrift": "Teststr. 1",
        "impressum_email": "test@example.dev",
        "impressum_bestaetigt": "on",
    }
    data.update(overrides)
    return data


def _post_settings(client, aliase: list[tuple[str, str, str]], **overrides):
    data = _settings_form(**overrides)
    return client.post(
        "/einstellungen",
        data=data | {
            "alias_plattform": [a[0] for a in aliase],
            "alias_anzeige": [a[1] for a in aliase],
            "alias_url": [a[2] for a in aliase],
        },
    )


def test_more_than_six_aliases_are_all_saved(logged_in_client, content_dir):
    """Regression test: aliase used to be capped at 6 fixed form rows."""
    aliase = [(f"Plattform{i}", f"user{i}", "") for i in range(9)]
    resp = _post_settings(logged_in_client, aliase)
    assert resp.status_code == 302

    import json
    saved = json.loads((content_dir / "site.config.json").read_text())
    assert len(saved["aliase"]) == 9
    assert saved["aliase"][8]["plattform"] == "Plattform8"


def test_empty_alias_rows_are_skipped(logged_in_client, content_dir):
    aliase = [("GitHub", "octocat", "https://github.com/octocat"), ("", "", "")]
    resp = _post_settings(logged_in_client, aliase)
    assert resp.status_code == 302

    import json
    saved = json.loads((content_dir / "site.config.json").read_text())
    assert len(saved["aliase"]) == 1
    assert saved["aliase"][0]["plattform"] == "GitHub"


def test_saved_aliases_are_prefilled_on_next_edit(logged_in_client):
    _post_settings(logged_in_client, [("Mastodon", "ada", "")])

    resp = logged_in_client.get("/einstellungen")
    body = resp.get_data(as_text=True)
    assert 'value="Mastodon"' in body
    assert 'value="ada"' in body


def test_alias_rows_survive_the_impressum_confirmation_error_rerender(logged_in_client):
    # No existing config yet -> impressum is always "changed" -> 400 without
    # the confirmation checkbox, but already-typed alias rows shouldn't vanish.
    data = _settings_form()
    del data["impressum_bestaetigt"]
    resp = logged_in_client.post(
        "/einstellungen",
        data=data | {
            "alias_plattform": ["GitHub"],
            "alias_anzeige": ["octocat"],
            "alias_url": [""],
        },
    )
    assert resp.status_code == 400
    assert 'value="GitHub"' in resp.get_data(as_text=True)
