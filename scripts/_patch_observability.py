#!/usr/bin/env python3
"""One-time patch: add wrap_main import and usage to all vault tools."""
import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
SKIP = {"vault_errors.py", "_patch_observability.py"}

patched = []
skipped = []
errors = []

for f in sorted(SCRIPTS_DIR.glob("*.py")):
    if f.name in SKIP:
        continue

    try:
        content = f.read_text(encoding="utf-8")
        original = content
        tool_name = f.stem  # e.g. "vault_write"

        # 1. Add import if not present
        if "from vault_errors import wrap_main" not in content:
            # Insert right after "import sys" line
            if "import sys\n" in content:
                content = content.replace("import sys\n", "import sys\nfrom vault_errors import wrap_main\n", 1)
            elif "import sys\r\n" in content:
                content = content.replace("import sys\r\n", "import sys\r\nfrom vault_errors import wrap_main\r\n", 1)
            else:
                # No sys import — add both after shebang line
                content = re.sub(
                    r'^(#!/usr/bin/env python3\n)',
                    r'\1import sys\nfrom vault_errors import wrap_main\n',
                    content
                )

        # 2. Replace sys.exit(main()) -> sys.exit(wrap_main(main, "toolname"))
        content = re.sub(
            r'sys\.exit\(main\(\)\)',
            f'sys.exit(wrap_main(main, "{tool_name}"))',
            content
        )

        # 3. Replace bare main() in __main__ block
        # Pattern: if __name__ == "__main__":\n    main()
        content = re.sub(
            r'(if __name__ == "__main__":\n)    main\(\)',
            rf'\1    sys.exit(wrap_main(main, "{tool_name}"))',
            content
        )

        if content != original:
            f.write_text(content, encoding="utf-8")
            patched.append(f.name)
        else:
            skipped.append(f.name)

    except Exception as e:
        errors.append(f"{f.name}: {e}")

print(f"Patched: {len(patched)}")
for n in patched:
    print(f"  + {n}")
print(f"Skipped (no change): {len(skipped)}")
if errors:
    print(f"Errors: {len(errors)}")
    for e in errors:
        print(f"  ! {e}")
