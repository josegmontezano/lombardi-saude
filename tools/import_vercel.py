#!/usr/bin/env python3
"""One-time import of the already deployed Lombardi Saúde v0.8.23 source.

Downloads immutable Vercel deployment assets by exact sha1; reconstructs the
runtime source, validates Django, removes historical credential fixtures,
and writes a sanitized, deployable source tree into ./site_export/.
Run this only on the trusted GitHub Actions runner (no write token).
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((REPO / "tools/vercel_source_manifest.json").read_text())
WORK = REPO / ".site-reconstruction"
OUT = REPO / "site_export"


def run(*cmd, cwd=None, env=None):
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    if OUT.exists():
        shutil.rmtree(OUT)
    WORK.mkdir()
    OUT.mkdir()
    manifest = MANIFEST["files"]
    if MANIFEST["version"] != "v0.8.23":
        raise RuntimeError("Unexpected source version")

    for i, item in enumerate(manifest, 1):
        name, sha1 = item["path"], item["sha1"]
        if (not re.fullmatch(r"[0-9a-f]{40}", sha1)
                or name.startswith("/")
                or ".." in Path(name).parts):
            raise RuntimeError("Invalid file manifest")
        target = WORK / name
        target.parent.mkdir(parents=True, exist_ok=True)
        req = Request(MANIFEST["cdnPrefix"] + sha1, headers={"User-Agent": "Lombardi-GitHub-Import/1"})
        with urlopen(req, timeout=50) as stream:
            payload = stream.read(8 * 1024 * 1024 + 1)
        if len(payload) > 8 * 1024 * 1024:
            raise RuntimeError("Unusually large deployment file: " + name)
        if hashlib.sha1(payload).hexdigest() != sha1:
            raise RuntimeError("Source checksum mismatch for " + name)
        target.write_bytes(payload)
        if i % 15 == 0:
            print("Verified", i, "source assets of", len(manifest), flush=True)

    # The source deploy relies on a local test settings module which was not
    # part of the deployed production files. Create it before any build step.
    test_settings = WORK / "lombardi/test_settings.py"
    test_settings.parent.mkdir(parents=True, exist_ok=True)
    test_settings.write_text(
        "from .settings import *\n"
        "DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}\n"
        "DEBUG = True\n"
        "SECURE_SSL_REDIRECT = False\n"
        "SESSION_COOKIE_SECURE = False\n"
        "CSRF_COOKIE_SECURE = False\n"
        "PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']\n",
        encoding="utf-8",
    )

    # Build against disposable SQLite test settings, not production PostgreSQL.
    env = dict(os.environ)
    env["DJANGO_SETTINGS_MODULE"] = "lombardi.test_settings"
    env["DJANGO_SECRET_KEY"] = "temporary-local-action-only-not-a-production-key"
    run(sys.executable, "-m", "pip", "install", "-r", "requirements.txt", cwd=WORK)
    run("bash", "build-v103.sh", cwd=WORK, env=env)

    for folder in ("clinic", "lombardi", "templates", "static", "api"):
        shutil.copytree(
            WORK / folder,
            OUT / folder,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pyo", ".env", "*.sqlite3", ".git", "*.db"
            ),
        )
    for filename in ("manage.py", "requirements.txt", "pyproject.toml",
                     ".python-version", "package.json"):
        source = WORK / filename
        if source.is_file():
            shutil.copy2(source, OUT / filename)

    # Remove an old initial admin password hash from a historical migration.
    # Real production accounts must instead arrive through an authorized DB
    # backup; fresh sites initialize admin interactively on the VPS.
    old_migration = OUT / "clinic/migrations/0019_add_master_account.py"
    old_migration.write_text(
        "from django.db import migrations\n\n"
        "# Do not seed real login credentials from source control.\n"
        "class Migration(migrations.Migration):\n"
        '    dependencies = [("clinic", "0018_remove_master_privileges")]\n'
        "    operations = [migrations.RunPython(migrations.RunPython.noop, migrations.RunPython.noop)]\n",
        encoding="utf-8",
    )

    # A test may not depend on the production user's personal credentials.
    test = OUT / "clinic/test_master_access.py"
    text = test.read_text(encoding="utf-8")
    text = text.replace(
        "class MasterAccessTests(TestCase):",
        'class MasterAccessTests(TestCase):\n'
        '    def setUp(self):\n'
        '        User.objects.create_superuser(\n'
        '            username="test-master@example.test",\n'
        '            email="test-master@example.test",\n'
        '            password="StrongTestPassword!2026",\n'
        '            role=User.ADMIN, must_change_password=True,\n'
        '        )\n',
    )
    text = text.replace("josegmontezano@gmail.com", "test-master@example.test")
    text = text.replace("test_master_created_by_migration", "test_master_is_provisioned_interactively")
    test.write_text(text, encoding="utf-8")

    # Ensure footer contains the currently published version.
    footer = OUT / "templates/clinic/base.html"
    text = footer.read_text(encoding="utf-8")
    if "v0.8.23" not in text:
        raise RuntimeError("Wrong source version exported")
    footer.write_text(text, encoding="utf-8")

    # Reproducible tests against the sanitized export.
    run(sys.executable, "manage.py", "check", cwd=OUT, env=env)
    run(sys.executable, "manage.py", "test",
        "clinic.test_master_access", "clinic.test_access",
        "clinic.test_doctor_admin", "clinic.test_admin_sidebar",
        "clinic.test_reviews", "--verbosity", "1", cwd=OUT, env=env)

    files = [p for p in OUT.rglob("*") if p.is_file()]
    for f in files:
        data = f.read_bytes()
        if b"pbkdf2_sha256$" in data or b"25061996" in data or b"250696" in data:
            raise RuntimeError("Possible historical master credential in source")
        if f.name.startswith(".env") and f.name != ".env.example":
            raise RuntimeError("Environment secret is not allowed in Git")
    print("Sanitized source ready:", len(files), "files,",
          sum(f.stat().st_size for f in files), "bytes")


if __name__ == "__main__":
    main()
