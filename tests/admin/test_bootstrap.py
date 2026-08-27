from admin.bootstrap import ensure_content_dir


def _write_demo_seed(seed_dir):
    post_dir = seed_dir / "beitraege" / "oeffentlich" / "2026-01-demo-projekt"
    post_dir.mkdir(parents=True)
    (post_dir / "meta.json").write_text("{}", encoding="utf-8")
    (post_dir / "inhalt.md").write_text("Text.", encoding="utf-8")

    seiten = seed_dir / "seiten"
    seiten.mkdir()
    (seiten / "impressum.md").write_text("Impressumstext.", encoding="utf-8")

    (seed_dir / "site.config.json").write_text('{"name": "Demo"}', encoding="utf-8")


def test_ensure_content_dir_actually_copies_seed_content_into_the_skeleton(tmp_path):
    # Regression test: the _SKELETON loop used to run *before* _seed(), so it
    # pre-created beitraege/oeffentlich, beitraege/privat and seiten as empty
    # dirs — _seed()'s shallow `target.exists()` check then saw those as
    # "already there" and silently skipped copying any demo content into
    # them, leaving a freshly bootstrapped instance with no posts and no
    # static pages at all (only site.config.json, via a separate code path).
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    _write_demo_seed(seed_dir)

    target = tmp_path / "data"
    ensure_content_dir(str(target), seed_from=str(seed_dir))

    assert (target / "beitraege" / "oeffentlich" / "2026-01-demo-projekt" / "meta.json").is_file()
    assert (target / "seiten" / "impressum.md").is_file()
    assert (target / "site.config.json").is_file()

    # The skeleton dirs the seed doesn't provide still get created.
    assert (target / "beitraege" / "privat").is_dir()
    assert (target / "zugang").is_dir()
    assert (target / ".papierkorb").is_dir()


def test_ensure_content_dir_does_not_reseed_an_already_populated_dir(tmp_path):
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    _write_demo_seed(seed_dir)

    target = tmp_path / "data"
    target.mkdir()
    (target / "beitraege" / "oeffentlich" / "eigener-beitrag").mkdir(parents=True)

    ensure_content_dir(str(target), seed_from=str(seed_dir))

    assert (target / "beitraege" / "oeffentlich" / "eigener-beitrag").is_dir()
    assert not (target / "beitraege" / "oeffentlich" / "2026-01-demo-projekt").exists()
