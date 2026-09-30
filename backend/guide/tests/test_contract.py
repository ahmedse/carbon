"""Every shipped pack passes the contract, and the engine stays domain-free."""
from __future__ import annotations

from pathlib import Path

from django.test import SimpleTestCase

import guide
from guide import contract

DOMAIN_WORDS = ("carbon", "emission", "period", "leave", "payslip", "loan", "gosi", "nibras", "eduos")
ENGINE_FILES = ("engine.py", "registry.py", "packs.py", "views.py", "urls.py", "models.py", "contract.py")


class GuideContractTests(SimpleTestCase):
    def test_all_packs_pass(self):
        self.assertEqual(contract.check_all(), [])

    def test_platform_and_carbon_packs_exist(self):
        self.assertIn("_platform", contract.pack_ids())
        self.assertIn("carbon", contract.pack_ids())

    def test_engine_has_no_domain_words(self):
        root = Path(guide.__file__).parent
        for name in ENGINE_FILES:
            text = (root / name).read_text(encoding="utf-8").lower()
            for word in DOMAIN_WORDS:
                self.assertNotIn(word, text, f"{name} mentions {word!r}")

    def test_engine_imports_no_host_domain(self):
        root = Path(guide.__file__).parent
        for name in ENGINE_FILES:
            text = (root / name).read_text(encoding="utf-8")
            for banned in ("import people", "from people", "ai.engine", "from emissions", "import emissions"):
                self.assertNotIn(banned, text, f"{name} imports {banned!r}")
