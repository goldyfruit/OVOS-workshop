"""Resource lookup memoizes package directory listings without going stale."""
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from ovos_workshop import resource_files
from ovos_workshop.resource_files import (ResourceType, match_lang_directories,
                                          locate_lang_directories)


def _touch(path: Path, text: str = "x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestResourceLookupCache(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.skill = Path(self.tmp.name)
        for lang in ("en-US", "fr-FR", "de-DE", "es-ES"):
            _touch(self.skill / "locale" / lang / "intents" / "hello.intent")
        resource_files._subdir_cache.clear()
        resource_files._file_index_cache.clear()

    def tearDown(self):
        self.tmp.cleanup()

    def test_same_result_as_uncached(self):
        self.assertEqual(locate_lang_directories("fr-FR", str(self.skill)),
                         [self.skill / "locale" / "fr-FR"])
        self.assertEqual(locate_lang_directories("en-US", str(self.skill)),
                         [self.skill / "locale" / "en-US"])

    def test_listing_is_reused(self):
        locate_lang_directories("fr-FR", str(self.skill))
        with mock.patch.object(resource_files.os, "scandir",
                               side_effect=AssertionError("relisted")):
            for lang in ("fr-FR", "de-DE", "en-US"):
                locate_lang_directories(lang, str(self.skill))

    def test_new_language_directory_is_seen(self):
        self.assertEqual(locate_lang_directories("it-IT", str(self.skill)), [])
        time.sleep(0.01)
        _touch(self.skill / "locale" / "it-IT" / "intents" / "hello.intent")
        # the locale directory's mtime moved, so the listing is refreshed
        self.assertEqual(locate_lang_directories("it-IT", str(self.skill)),
                         [self.skill / "locale" / "it-IT"])

    def test_resource_file_located_once_per_directory(self):
        rt = ResourceType("intent", ".intent", "fr-FR")
        rt.locate_base_directory(str(self.skill))
        first = resource_files.IntentFile(rt, "hello").file_path
        self.assertEqual(first, self.skill / "locale" / "fr-FR" / "intents" / "hello.intent")
        with mock.patch.object(resource_files, "walk",
                               side_effect=AssertionError("walked again")):
            again = resource_files.IntentFile(rt, "hello.intent").file_path
            missing = resource_files.IntentFile(rt, "nope").file_path
        self.assertEqual(again, first)
        self.assertIsNone(missing)

    def test_missing_directory(self):
        self.assertEqual(match_lang_directories("en-US", [self.skill / "absent"]), [])


if __name__ == "__main__":
    unittest.main()


class TestLocaleVocabulariesMemo(unittest.TestCase):
    def setUp(self):
        from ovos_workshop.resource_files import SkillResources
        self.tmp = tempfile.TemporaryDirectory()
        self.skill = Path(self.tmp.name)
        _touch(self.skill / "locale" / "en-US" / "vocab" / "colour.voc", "Red\nblue\n")
        _touch(self.skill / "locale" / "en-US" / "intents" / "paint.intent", "paint it <colour>\n")
        resource_files._subdir_cache.clear()
        resource_files._file_index_cache.clear()
        self.resources = SkillResources(str(self.skill), "en-US", skill_id="test.skill")

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_once_and_copied(self):
        first = self.resources._locale_vocabularies()
        self.assertEqual(first["colour"], ["red", "blue"])  # workshop's own .voc ride along
        expected = {name: list(members) for name, members in first.items()}
        first["colour"].append("mutated")
        with mock.patch.object(resource_files, "walk",
                               side_effect=AssertionError("walked again")):
            second = self.resources._locale_vocabularies()
        self.assertEqual(second, expected)

    def test_user_override_directory_is_not_cached(self):
        self.resources._locale_vocabularies()
        self.resources.types.vocabulary.user_directory = self.skill / "locale" / "en-US"
        with mock.patch.object(resource_files, "walk", wraps=resource_files.walk) as spy:
            self.resources._locale_vocabularies()
        self.assertTrue(spy.called)
