"""Bulk-loaded vocabulary reaches the adapt engine only for the intents that use it."""
import json
import unittest

from ovos_utils.fakebus import FakeBus
from ovos_workshop.intents import IntentBuilder, IntentServiceInterface, munge_intent_parser


class TestLazyLegacyVocab(unittest.TestCase):
    def setUp(self):
        self.bus = FakeBus()
        self.sent = []
        self.bus.on("message", lambda m: self.sent.append(json.loads(m)))
        self.iface = IntentServiceInterface(self.bus)
        self.iface.set_id("test.skill")
        self.sid = "test_skill"

    def _topics(self, topic):
        return [m for m in self.sent if m["type"] == topic]

    def test_deferred_vocab_is_not_sent_without_an_adapt_intent(self):
        self.iface.register_keyword(self.sid + "Colour", "red", ["crimson"], "en-US")
        self.assertEqual(self._topics("register_vocab"), [])
        # the samples are still known to the spec registration path
        self.assertEqual(list(self.iface._get_keyword_samples(self.sid + "Colour", "en-US")),
                         ["red", "crimson"])

    def test_adapt_intent_flushes_its_vocab_before_the_intent(self):
        self.iface.register_keyword(self.sid + "Colour", "red", ["crimson"], "en-US")
        self.iface.register_keyword(self.sid + "Unused", "nothing", None, "en-US")
        parser = IntentBuilder("paint").require("Colour").build()
        munge_intent_parser(parser, "paint", "test.skill")
        self.iface.register_intent("paint", parser)
        types = [m["type"] for m in self.sent]
        vocab = self._topics("register_vocab")
        self.assertEqual([v["data"]["entity_value"] for v in vocab], ["red", "crimson"])
        self.assertLess(types.index("register_vocab"), types.index("register_intent"))
        self.assertTrue(all(v["context"]["skill_id"] == "test.skill" for v in vocab))

    def test_vocab_registered_after_its_intent_is_sent_at_once(self):
        parser = IntentBuilder("paint").require("Colour").build()
        munge_intent_parser(parser, "paint", "test.skill")
        self.iface.register_intent("paint", parser)
        self.iface.register_keyword(self.sid + "Colour", "blue", None, "en-US")
        self.assertEqual([v["data"]["entity_value"] for v in self._topics("register_vocab")],
                         ["blue"])

    def test_aliases_and_languages_flush_together(self):
        self.iface.register_keyword(self.sid + "Colour", "red", ["crimson"], "en-US")
        self.iface.register_keyword(self.sid + "Colour", "rouge", None, "fr-FR")
        self.assertEqual(self._topics("register_vocab"), [])
        parser = IntentBuilder("paint").require("Colour").build()
        munge_intent_parser(parser, "paint", "test.skill")
        self.iface.register_intent("paint", parser)
        self.assertEqual(sorted((v["data"]["entity_value"], v["data"]["lang"])
                                for v in self._topics("register_vocab")),
                         [("crimson", "en-US"), ("red", "en-US"), ("rouge", "fr-FR")])

    def test_a_large_vocabulary_registers_in_linear_time(self):
        import time
        start = time.monotonic()
        for n in range(20000):
            self.iface.register_keyword(self.sid + "City", f"city{n}", [f"town{n}"], "en-US")
        self.assertLess(time.monotonic() - start, 5)
        samples = self.iface._get_keyword_samples(self.sid + "City", "en-US")
        self.assertEqual(len(samples), 40000)
        self.assertEqual(list(samples)[:3], ["city0", "town0", "city1"])
        # a repeat adds nothing
        self.iface.register_keyword(self.sid + "City", "city0", ["town0"], "en-US")
        self.assertEqual(len(self.iface._get_keyword_samples(self.sid + "City", "en-US")), 40000)


if __name__ == "__main__":
    unittest.main()
