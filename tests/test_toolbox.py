import unittest
import json
from blockapily import *
import tempfile
from pathlib import Path

class Vec3: pass
CUSTOM_TYPE_MAP = {'Vec3': '3DVector'}
CUSTOM_SHADOW_MAP = {
    'xml':{'Vec3': '<shadow type="vector_3d_zero"></shadow>'},
    'json':{'Vec3': {'type': 'vector_3d_zero'}},
}

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
        self.toolbox_json_path = Path(self.temp_dir.name) / "toolbox.json"
        
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
        """Tests adding a new category to empty XML and JSON toolbox files."""
        _, _, category_xml, category_json = self.generator.generate()
        
        self.generator.update_toolbox(category_xml, self.toolbox_path)
        self.generator.update_toolbox_json(category_json, self.toolbox_json_path)

        # XML assertions
        content = self.toolbox_path.read_text()
        self.assertIn('<category name="MockActions" colour="210">', content)
        self.assertIn('<block type="mockactions_move"', content)
        self.assertIn('<block type="mockactions_get_position"', content)

        # JSON assertions
        json_content = json.loads(self.toolbox_json_path.read_text())
        self.assertEqual(json_content.get("kind"), "categoryToolbox")
        
        categories = json_content.get("contents", [])
        self.assertEqual(len(categories), 1)
        
        mock_cat = categories[0]
        self.assertEqual(mock_cat.get("name"), "MockActions")
        self.assertEqual(mock_cat.get("colour"), "210")
        
        block_types = [b.get("type") for b in mock_cat.get("contents", [])]
        self.assertIn("mockactions_move", block_types)
        self.assertIn("mockactions_get_position", block_types)

    def test_update_existing_category(self):
        """Tests replacing the contents of an existing category in both formats."""
        
        # 1. Setup Initial XML
        initial_content = """<toolbox xmlns="https://developers.google.com/blockly/xml">
  <category name="MockActions" colour="120">
    <block type="old_deprecated_block"></block>
  </category>
</toolbox>"""
        self.toolbox_path.write_text(initial_content)

        # 2. Setup Initial JSON
        initial_json = {
            "kind": "categoryToolbox",
            "contents": [
                {
                    "kind": "category",
                    "name": "MockActions",
                    "colour": "120",
                    "contents": [
                        {"kind": "block", "type": "old_deprecated_block"}
                    ]
                }
            ]
        }
        self.toolbox_json_path.write_text(json.dumps(initial_json))

        # 3. Generate and Apply Updates
        _, _, category_xml, category_json = self.generator.generate()
        self.generator.update_toolbox(category_xml, self.toolbox_path)
        self.generator.update_toolbox_json(category_json, self.toolbox_json_path)

        # 4. Assert XML was updated correctly
        content = self.toolbox_path.read_text()
        self.assertIn('<category name="MockActions" colour="210">', content)
        self.assertIn('<block type="mockactions_move"', content)
        self.assertNotIn('old_deprecated_block', content)
        self.assertEqual(content.count('<category name="MockActions"'), 1, "Category should not be duplicated in XML")

        # 5. Assert JSON was updated correctly
        json_content = json.loads(self.toolbox_json_path.read_text())
        categories = [c for c in json_content.get("contents", []) if c.get("kind") == "category"]
        self.assertEqual(len(categories), 1, "Category should not be duplicated in JSON")
        
        mock_cat = categories[0]
        self.assertEqual(mock_cat.get("colour"), "210")
        
        block_types = [b.get("type") for b in mock_cat.get("contents", [])]
        self.assertIn("mockactions_move", block_types)
        self.assertNotIn("old_deprecated_block", block_types)

if __name__ == '__main__':
    print("Running tests for Toolbox XML and JSON Updater...")
    unittest.main()