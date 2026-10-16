
from django.conf import settings


def test_no_direct_now_calls_outside_clock():
    base_apps_dir = settings.BASE_DIR / "apps"
    allowed_file = (base_apps_dir / "core" / "clock.py").resolve()

    violations = []
    for py_file in base_apps_dir.rglob("*.py"):
        if py_file.resolve() == allowed_file:
            continue

        content = py_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        for idx, line in enumerate(lines, start=1):
            # Exclude comments
            stripped = line.strip()
            if stripped.startswith("#"):
                continue

            if "timezone.now()" in line or "datetime.now()" in line:
                violations.append(f"{py_file.relative_to(settings.BASE_DIR)}:L{idx}: {line.strip()}")

    assert not violations, (
        "Found forbidden direct now() calls outside apps/core/clock.py:\n"
        + "\n".join(violations)
    )
