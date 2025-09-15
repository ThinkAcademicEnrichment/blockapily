import unittest
from blockapily import *
import tempfile

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
        self.generator = BlocklyGenerator(MockActions, category_colour="210")

    def tearDown(self):
        """Clean up the temporary directory."""
        self.temp_dir.cleanup()

    def test_insert_new_category(self):
        """Tests adding a new category to an empty toolbox file."""
        _, _, category_xml = self.generator.generate()
        self.generator.update_toolbox(category_xml, self.toolbox_path)

        content = self.toolbox_path.read_text()
        self.assertIn('<category name="Mock Actions" colour="210">', content)
        self.assertIn('<block type="mock_actions_move"', content)
        self.assertIn('<block type="mock_actions_get_position"', content)

    def test_update_existing_category(self):
        """Tests replacing the contents of an existing category."""
        # --- FIX APPLIED HERE ---
        # Add the xmlns attribute to make the test file realistic.
        initial_content = """<toolbox xmlns="https://developers.google.com/blockly/xml">
  <category name="Mock Actions" colour="120">
    <block type="old_deprecated_block"></block>
  </category>
</toolbox>"""
        self.toolbox_path.write_text(initial_content)

        _, _, category_xml = self.generator.generate()
        self.generator.update_toolbox(category_xml, self.toolbox_path)

        content = self.toolbox_path.read_text()
        self.assertIn('<category name="Mock Actions" colour="210">', content)
        self.assertIn('<block type="mock_actions_move"', content)
        self.assertNotIn('old_deprecated_block', content)
        self.assertEqual(content.count('<category name="Mock Actions"'), 1, "Category should not be duplicated")

# def create_suite():
#     return unittest.makeSuite(TestToolboxUpdater)

if __name__ == '__main__':
    # runner = unittest.TextTestRunner()
    print("Running tests for Toolbox XML Updater...")
    unittest.main()
    # runner.run(create_suite())