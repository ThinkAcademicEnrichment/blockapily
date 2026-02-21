import unittest
from blockapily import *
import tempfile
from pathlib import Path

class Vec3: pass
CUSTOM_TYPE_MAP = {'Vec3': '3DVector'}
CUSTOM_SHADOW_MAP = {'Vec3': '<shadow type="vector_3d_zero"></shadow>'}

class MockActions: # Defined here for test context
    @mced_block(label="Move Robot")
    def move(self, speed: float = 1.5, forward: bool = True): pass
    @mced_block(label="Get Position", output_type='3DVector')
    def get_position(self, target_id: int): pass

class TestToolboxUpdater(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory and a generator for each test."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.toolbox_path = Path(self.temp_dir.name) / "toolbox.xml"
        self.generator = BlocklyGenerator(
            MockActions,
            type_map=CUSTOM_TYPE_MAP,
            shadow_map=CUSTOM_SHADOW_MAP,
            category_colour="210"
        )

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_insert_new_category(self):
        """Tests adding a new category to an empty toolbox file."""
        _, _, category_xml = self.generator.generate()
        self.generator.update_toolbox(category_xml, self.toolbox_path)

        content = self.toolbox_path.read_text()
        self.assertIn('<category name="MockActions" colour="210">', content)
        self.assertIn('<block type="mockactions_move"', content)
        self.assertIn('<block type="mockactions_get_position"', content)

    def test_update_existing_category(self):
        """Tests replacing the contents of an existing category."""
        initial_content = """<toolbox xmlns="https://developers.google.com/blockly/xml">
  <category name="MockActions" colour="120">
    <block type="old_deprecated_block"></block>
  </category>
</toolbox>"""
        self.toolbox_path.write_text(initial_content)

        _, _, category_xml = self.generator.generate()
        self.generator.update_toolbox(category_xml, self.toolbox_path)

        content = self.toolbox_path.read_text()
        self.assertIn('<category name="MockActions" colour="210">', content)
        self.assertIn('<block type="mockactions_move"', content)
        self.assertNotIn('old_deprecated_block', content)
        self.assertEqual(content.count('<category name="MockActions"'), 1, "Category should not be duplicated")

if __name__ == '__main__':
    print("Running tests for Toolbox XML Updater...")
    unittest.main()