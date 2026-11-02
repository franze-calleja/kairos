from fastapi.testclient import TestClient

from kairos.api.app import create_app


def test_spa_served_with_fallback(settings, tmp_path):
    static = tmp_path / "static"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>kairos-index</html>")
    (static / "assets" / "app.js").write_text("console.log('hi')")
    with TestClient(create_app(settings, static_dir=static)) as c:
        assert "kairos-index" in c.get("/").text
        assert "kairos-index" in c.get("/some/client/route").text
        assert c.get("/assets/app.js").text == "console.log('hi')"
        assert c.get("/api/health").json() == {"status": "ok"}
        assert c.get("/api/nope").status_code == 404


def test_no_static_dir_is_fine(settings, tmp_path):
    with TestClient(create_app(settings, static_dir=tmp_path / "missing")) as c:
        assert c.get("/api/health").status_code == 200


def test_static_fallback_blocks_path_traversal(settings, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "index.html").write_text("<html>kairos-index</html>")
    (tmp_path / "secret.txt").write_text("top-secret")
    with TestClient(create_app(settings, static_dir=static)) as c:
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"):
            assert "top-secret" not in c.get(path).text
