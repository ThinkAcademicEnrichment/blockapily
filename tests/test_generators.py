from blockapily import mced_category
import unittest
from blockapily import *

class Vec3: pass

CUSTOM_TYPE_MAP = {
    'Vec3': '3DVector',
    'float': 'Number',
    'int': 'Number',
    'str': 'String',
    'bool': 'Boolean'
}

CUSTOM_SHADOW_MAP = {
    'xml': {
        'float': '<shadow type="math_number"><field name="NUM">0.0</field></shadow>',
        'int': '<shadow type="math_number"><field name="NUM">0</field></shadow>',
        'Vec3': '<shadow type="vector_3d_zero"></shadow>'
    },
    'json': {
        'float': {'type': 'math_number', 'fields': {'NUM': 0.0}},
        'int': {'type': 'math_number', 'fields': {'NUM': 0}},
        'Vec3': {'type': 'vector_3d_zero'}
    }
}

@mced_category(name='MockActions',colour='#222')
class MockActions:
    @mced_block(label="Move Robot", speed={'label': 'Speed'}, forward={'label': 'Forward'})
    def move(self, speed: float = 1.5, forward: bool = True): pass

    @mced_block(label="Get Position", target_id={'label': 'Target ID'})
    def get_position(self, target_id: int) -> 'Vec3': pass

    def internal_helper(self): pass


class TestBlocklyGenerator(unittest.TestCase):
    """Test suite for the BlocklyGenerator class."""

    def setUp(self):
        """Initializes the generator before each test. Does not generate code."""
        self.generator = BlocklyGenerator(
            MockActions,
            type_map=CUSTOM_TYPE_MAP,
            shadow_map=CUSTOM_SHADOW_MAP
        )

    def test_block_definition_for_statement_block(self):
        """Tests the block definition of a standard statement block."""
        block_defs, _, _, _ = self.generator.generate()
        self.assertIn("Blockly.Blocks['mockactions_move']", block_defs)
        self.assertIn('.appendField("Move Robot")', block_defs)
        self.assertIn(".setCheck('Number')", block_defs)

        # Isolate the specific block definition for precise testing
        move_block_def = next((s for s in block_defs.split('Blockly.Blocks') if "'mockactions_move']" in s), "")
        self.assertTrue(move_block_def, "Move block definition not found.")
        self.assertIn("setPreviousStatement", move_block_def)
        self.assertNotIn("setOutput", move_block_def)

    def test_block_definition_for_output_block(self):
        """Tests the block definition of a block that returns a value."""
        block_defs, _, _, _ = self.generator.generate()
        self.assertIn("Blockly.Blocks['mockactions_get_position']", block_defs)
        self.assertIn('.appendField("Get Position")', block_defs)

        # Isolate the specific block definition for precise testing
        get_pos_block_def = next((s for s in block_defs.split('Blockly.Blocks') if "'mockactions_get_position']" in s), "")
        self.assertTrue(get_pos_block_def, "Get Position block definition not found.")
        self.assertIn("setOutput(true, '3DVector')", get_pos_block_def)
        self.assertNotIn("setPreviousStatement", get_pos_block_def)

    def test_python_generator_for_statement_block(self):
        """Tests the Python generator for a statement block."""
        _, py_gens, _, _ = self.generator.generate()
        self.assertIn("pythonGenerator.forBlock['mockactions_move']", py_gens)
        self.assertIn("const speed = generator.valueToCode(block, 'speed', pythonGenerator.ORDER_ATOMIC) || 'None';", py_gens)
        self.assertIn("const code = `MockActions.move(${speed}, ${forward})\\n`;", py_gens)

    def test_python_generator_for_output_block(self):
        """Tests the Python generator for an output block."""
        _, py_gens, _, _ = self.generator.generate()
        self.assertIn("pythonGenerator.forBlock['mockactions_get_position']", py_gens)
        self.assertIn("const target_id = generator.valueToCode(block, 'target_id', pythonGenerator.ORDER_ATOMIC) || 'None';", py_gens)
        self.assertIn("return block.outputConnection ? [code.trim(), pythonGenerator.ORDER_ATOMIC] : code;", py_gens)

    def test_undecorated_methods_are_ignored(self):
        """Ensures that methods without the decorator are not processed."""
        block_defs, py_gens, _, _ = self.generator.generate()
        self.assertNotIn("internal_helper", block_defs)
        self.assertNotIn("internal_helper", py_gens)

    def test_toolbox_generation_default_name(self):
        """Tests the generated toolbox XML and JSON with a default category name."""
        generator = BlocklyGenerator(MockActions, type_map=CUSTOM_TYPE_MAP, shadow_map=CUSTOM_SHADOW_MAP)
        _, _, toolbox_xml, toolbox_json = generator.generate()

        # XML Assertions
        self.assertTrue(toolbox_xml.startswith('<category name="MockActions"'))
        self.assertTrue(toolbox_xml.endswith('</category>'))
        self.assertIn('<block type="mockactions_move">', toolbox_xml)
        self.assertIn('<block type="mockactions_get_position">', toolbox_xml)
        self.assertNotIn('internal_helper', toolbox_xml)
        self.assertIn('<shadow type="math_number"><field name="NUM">0.0</field></shadow>', toolbox_xml)

        # JSON Assertions
        self.assertEqual(toolbox_json.get("kind"), "category")
        self.assertEqual(toolbox_json.get("name"), "MockActions")
        
        # Verify JSON block inclusion
        block_types = [block.get("type") for block in toolbox_json.get("contents", [])]
        self.assertIn("mockactions_move", block_types)
        self.assertIn("mockactions_get_position", block_types)
        self.assertNotIn("internal_helper", block_types)

        # Verify JSON shadows were properly injected
        move_block = next((b for b in toolbox_json.get("contents", []) if b.get("type") == "mockactions_move"), None)
        self.assertIsNotNone(move_block, "move block not found in JSON contents")
        self.assertIn("speed", move_block.get("inputs", {}))
        
        speed_shadow = move_block["inputs"]["speed"].get("shadow", {})
        self.assertEqual(speed_shadow.get("type"), "math_number")
        self.assertEqual(speed_shadow.get("fields", {}).get("NUM"), 0.0)

    def test_toolbox_generation_custom_colour(self):
        """Tests the generated toolbox XML and JSON with a custom colour."""
        generator = BlocklyGenerator(
            MockActions,
            type_map=CUSTOM_TYPE_MAP,
            shadow_map=CUSTOM_SHADOW_MAP,
            category_colour="#FF0000"
        )
        _, _, toolbox_xml, toolbox_json = generator.generate()

        # XML Assertions
        self.assertIn('<category name="MockActions"', toolbox_xml)
        self.assertIn('colour="#FF0000"', toolbox_xml)

        # JSON Assertions
        self.assertEqual(toolbox_json.get("colour"), "#FF0000")

    def test_block_and_generator_outputs(self):
        """Confirms the other outputs are still correct."""
        generator = BlocklyGenerator(MockActions, type_map=CUSTOM_TYPE_MAP, shadow_map=CUSTOM_SHADOW_MAP)
        block_defs, py_gens, _, _= generator.generate()
        self.assertIn("Blockly.Blocks['mockactions_move']", block_defs)
        self.assertIn("pythonGenerator.forBlock['mockactions_move']", py_gens)

if __name__ == '__main__':
    print("Running tests including Toolbox XML and JSON generation...")
    unittest.main()