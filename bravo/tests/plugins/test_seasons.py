from twisted.trial import unittest

import bravo.blocks
import bravo.chunk
import bravo.ibravo
import bravo.plugin
import bravo.protocols.beta

class TestWinter(unittest.TestCase):

    def setUp(self):
        self.p = bravo.plugin.retrieve_plugins(bravo.ibravo.ISeason)

        if "winter" not in self.p:
            raise unittest.SkipTest("Plugin not present")

        self.hook = self.p["winter"]
        self.c = bravo.chunk.Chunk(0, 0)

    def test_trivial(self):
        pass

    def test_spring_to_ice(self):
        self.c.set_block((0, 0, 0), bravo.blocks.blocks["spring"].slot)
        self.hook.transform(self.c)
        self.assertEqual(self.c.get_block((0, 0, 0)),
            bravo.blocks.blocks["ice"].slot)

    def test_snow_on_stone(self):
        self.c.set_block((0, 0, 0), bravo.blocks.blocks["stone"].slot)
        self.hook.transform(self.c)
        self.assertEqual(self.c.get_block((0, 1, 0)),
            bravo.blocks.blocks["snow"].slot)

    def test_no_snow_on_snow(self):
        """
        Test whether snow is spawned on top of other snow.
        """

        self.c.set_block((0, 0, 0), bravo.blocks.blocks["snow"].slot)
        self.hook.transform(self.c)
        self.assertNotEqual(self.c.get_block((0, 1, 0)),
            bravo.blocks.blocks["snow"].slot)

    def test_no_floating_snow(self):
        """
        Test whether snow is spawned in the correct y-level over populated
        chunks.
        """

        self.c.set_block((0, 0, 0), bravo.blocks.blocks["grass"].slot)
        self.c.populated = True
        self.c.dirty = False
        self.c.clear_damage()
        self.hook.transform(self.c)
        self.assertEqual(self.c.get_block((0, 1, 0)),
            bravo.blocks.blocks["snow"].slot)
        self.assertNotEqual(self.c.get_block((0, 2, 0)),
            bravo.blocks.blocks["snow"].slot)

    def test_bad_heightmap_floating_snow(self):
        """
        Test whether snow is spawned in the correct y-level over populated
        chunks, if the heightmap is incorrect.
        """

        self.c.set_block((0, 0, 0), bravo.blocks.blocks["grass"].slot)
        self.c.populated = True
        self.c.dirty = False
        self.c.clear_damage()
        self.c.heightmap[0, 0] = 2
        self.hook.transform(self.c)
        self.assertEqual(self.c.get_block((0, 1, 0)),
            bravo.blocks.blocks["snow"].slot)
        self.assertNotEqual(self.c.get_block((0, 2, 0)),
            bravo.blocks.blocks["snow"].slot)
