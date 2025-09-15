# blockapily

`blockapily` is a Python utility that automatically generates Google Blockly assets from decorated class methods. It inspects a Python class and converts type-annotated methods into JavaScript block definitions, Python code generators, and toolbox XML.

-----

## Core Concept

The main idea is to keep your Python code as the **single source of truth**. You define the logic and parameters for an action in a Python method, add type hints, and use a simple decorator. `blockapily` then handles the boilerplate of creating the corresponding Blockly assets, ensuring they stay in sync with your Python implementation.

-----

## Quickstart

### 1\. Define your Actions Class

Create a Python class and decorate the methods you want to expose in Blockly with `@mced_block`. Use standard type hints for parameters.

```python
# my_robot.py
from blockapily import mced_block

class RobotActions:
    """Defines actions a robot can perform."""

    @mced_block(label="Move Robot")
    def move(self, speed: float = 1.0, forward: bool = True):
        """A simple statement block."""
        pass

    @mced_block(label="Get Position", output_type='3DVector')
    def get_position(self, target_id: int) -> 'Vec3':
        """A block that returns a value."""
        pass
```

### 2\. Write your Generation Script

Create a script to run the generator. You only need to provide mappings for any custom types you used (like `'Vec3'`).

```python
# generate_blocks.py
from pathlib import Path
from blockapily import BlocklyGenerator
from my_robot import RobotActions

# 1. Define mappings for any custom types
CUSTOM_TYPE_MAP = {'Vec3': '3DVector'}
CUSTOM_SHADOW_MAP = {'Vec3': '<shadow type="vector_3d_zero"></shadow>'}

# 2. Instantiate the generator
generator = BlocklyGenerator(
    RobotActions,
    type_map=CUSTOM_TYPE_MAP,
    shadow_map=CUSTOM_SHADOW_MAP,
    category_colour="210"
)

# 3. Generate the assets
block_defs_js, py_gen_js, toolbox_xml = generator.generate()

# 4. Save the generated files
output_dir = Path("./generated_assets")
output_dir.mkdir(exist_ok=True)

(output_dir / "block_definitions.js").write_text(block_defs_js)
(output_dir / "python_generators.js").write_text(py_gen_js)

# 5. Update the main toolbox XML file
toolbox_path = output_dir / "toolbox.xml"
generator.update_toolbox(toolbox_xml, toolbox_path)

print(f"✅ Blockly assets generated in '{output_dir}'")
```

### 3\. Run the Script

```bash
python generate_blocks.py
```

This will create a `generated_assets` directory containing your JavaScript files and an updated `toolbox.xml` ready to be used in your Blockly application.

-----

## Key Features

  * **Decorator-based:** Simply mark methods for export with a clear `@mced_block` decorator.
  * **Type Hint Driven:** Automatically infers Blockly types, shadows, and default values from standard Python type annotations.
  * **Automatic Toolbox Management:** Intelligently creates and updates your `toolbox.xml` file, adding or replacing categories as needed.
  * **Highly Configurable:** Easily customize block prefixes, category names, colors, and mappings for custom types.