import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings


class ConsoleTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.dist = self.base / "dist"
        (self.dist / "assets").mkdir(parents=True)
        (self.dist / "index.html").write_text("<title>console</title>")
        (self.dist / "assets" / "app.js").write_text("export {}")
        (self.base / "secret.txt").write_text("private")
        override = override_settings(FRONTEND_DIST=self.dist)
        override.enable()
        self.addCleanup(override.disable)

    def body(self, response):
        return b"".join(response.streaming_content)

    def test_serves_the_console_and_its_scripts_as_javascript(self):
        self.assertIn(b"console", self.body(self.client.get("/")))
        script = self.client.get("/assets/app.js")
        self.assertEqual(script.status_code, 200)
        self.assertTrue(script["Content-Type"].startswith("text/javascript"))
        self.body(script)  # closes the file, which Windows requires before the cleanup

    def test_unknown_paths_get_the_console(self):
        self.assertIn(b"console", self.body(self.client.get("/some/page")))

    def test_files_outside_the_build_are_not_served(self):
        for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/..%2f..%2fsecret.txt"):
            response = self.client.get(path)
            content = self.body(response) if response.streaming else response.content
            self.assertNotIn(b"private", content)

    def test_api_paths_are_not_swallowed(self):
        self.assertEqual(self.client.get("/api/health").json(), {"status": "ok"})
        self.assertEqual(self.client.get("/api/unknown").status_code, 404)

    def test_explains_a_missing_build(self):
        with override_settings(FRONTEND_DIST=self.base / "nothing"):
            response = self.client.get("/")
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"npm run build", response.content)
