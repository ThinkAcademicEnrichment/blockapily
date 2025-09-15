import unittest
from blockapily import *

class Vec3: pass
CUSTOM_TYPE_MAP = {'Vec3': '3DVector'}
CUSTOM_SHADOW_MAP = {'Vec3': '<shadow type="vector_3d_zero"></shadow>'}

class MockActions:
    @mced_block(label="Move Robot")
    def move(self, speed: float = 1.5, forward: bool = True): pass
    @mced_block(label="Get Position", output_type='3DVector')
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
        block_defs, _, _ = self.generator.generate()
        self.assertIn("Blockly.Blocks['mock_actions_move']", block_defs)
        self.assertIn('.appendField("Move Robot")', block_defs)
        self.assertIn('.setCheck("Number")', block_defs)
        self.assertIn("1.5</field></shadow>", block_defs) # Check dynamic shadow value

        # Isolate the specific block definition for precise testing
        move_block_def = next((s for s in block_defs.split('Blockly.Blocks') if "'mock_actions_move']" in s), "")
        self.assertTrue(move_block_def, "Move block definition not found.")
        self.assertIn("setPreviousStatement", move_block_def)
        self.assertNotIn("setOutput", move_block_def)

    def test_block_definition_for_output_block(self):
        """Tests the block definition of a block that returns a value."""
        block_defs, _, _ = self.generator.generate()
        self.assertIn("Blockly.Blocks['mock_actions_get_position']", block_defs)
        self.assertIn('.appendField("Get Position")', block_defs)
        self.assertIn("0</field></shadow>", block_defs) # Check fallback shadow value

        # Isolate the specific block definition for precise testing
        get_pos_block_def = next((s for s in block_defs.split('Blockly.Blocks') if "'mock_actions_get_position']" in s), "")
        self.assertTrue(get_pos_block_def, "Get Position block definition not found.")
        self.assertIn("setOutput(true, \"3DVector\")", get_pos_block_def)
        self.assertNotIn("setPreviousStatement", get_pos_block_def)

    def test_python_generator_for_statement_block(self):
        """Tests the Python generator for a statement block."""
        _, py_gens, _ = self.generator.generate()
        self.assertIn("pythonGenerator.forBlock['mock_actions_move']", py_gens)
        self.assertIn("const speed = generator.valueToCode(block, 'SPEED', generator.ORDER_ATOMIC) || 1.5;", py_gens)
        self.assertIn("return `self.action_implementer.move(speed=${speed}, forward=${forward})\\n`;", py_gens)

    def test_python_generator_for_output_block(self):
        """Tests the Python generator for an output block."""
        _, py_gens, _ = self.generator.generate()
        self.assertIn("pythonGenerator.forBlock['mock_actions_get_position']", py_gens)
        self.assertIn("const target_id = generator.valueToCode(block, 'TARGET_ID', generator.ORDER_ATOMIC) || 0;", py_gens)
        self.assertIn("return [code, generator.ORDER_FUNCTION_CALL];", py_gens)

    def test_undecorated_methods_are_ignored(self):
        """Ensures that methods without the decorator are not processed."""
        block_defs, py_gens, _ = self.generator.generate()
        self.assertNotIn("internal_helper", block_defs)
        self.assertNotIn("internal_helper", py_gens)

    def test_toolbox_xml_generation_default_name(self):
        """Tests the generated toolbox XML with a default category name."""
        generator = BlocklyGenerator(MockActions)
        _, _, toolbox_xml = generator.generate()

        self.assertTrue(toolbox_xml.startswith('<category name="Mock Actions"'))
        self.assertTrue(toolbox_xml.endswith('</category>'))
        self.assertIn('<block type="mock_actions_move"></block>', toolbox_xml)
        self.assertIn('<block type="mock_actions_get_position"></block>', toolbox_xml)
        self.assertNotIn('internal_helper', toolbox_xml)

    def test_toolbox_xml_generation_custom_name_and_colour(self):
        """Tests the generated toolbox XML with a custom name and colour."""
        generator = BlocklyGenerator(
            MockActions,
            category_name="Robot Control",
            category_colour="#FF0000"
        )
        _, _, toolbox_xml = generator.generate()

        self.assertIn('<category name="Robot Control"', toolbox_xml)
        self.assertIn('colour="#FF0000"', toolbox_xml)

    # ... other tests for block defs and py gens remain the same ...
    def test_block_and_generator_outputs(self):
        """Confirms the other outputs are still correct."""
        generator = BlocklyGenerator(MockActions)
        block_defs, py_gens, _ = generator.generate()
        self.assertIn("Blockly.Blocks['mock_actions_move']", block_defs)
        self.assertIn("pythonGenerator.forBlock['mock_actions_move']", py_gens)


# def create_suite():
#     return unittest.makeSuite(TestBlocklyGenerator)

if __name__ == '__main__':
    # runner = unittest.TextTestRunner()
    print("Running tests including Toolbox XML generation...")
    # runner.run(create_suite())
    unittest.main()