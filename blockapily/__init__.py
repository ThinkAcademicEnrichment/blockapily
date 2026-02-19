import inspect
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

# Register the standard Blockly namespace to prevent 'ns0:' prefixing
BLOCKLY_NS = "https://developers.google.com/blockly/xml"
ET.register_namespace('', BLOCKLY_NS)

def mced_block(label: str, **kwargs):
    """Decorator to mark a method as a Blockly block."""
    def decorator(func):
        func._is_mced_block = True
        func._mced_label = label
        func._mced_params = kwargs
        return func
    return decorator

class BlocklyGenerator:
    """
    Generates Blockly block definitions (JS) and Python generators (JS)
    from Python classes, and manages toolbox XML injection.
    """
    def __init__(self, cls: Any, type_map: Dict[str, str], shadow_map: Dict[str, str], category_colour: str = "#333"):
        self.cls = cls
        self.type_map = type_map
        self.shadow_map = shadow_map
        self.category_colour = category_colour

    def _get_output_type(self, func: Callable) -> Optional[str]:
        """Maps Python return type hints to Blockly types using the provided type_map."""
        sig = inspect.signature(func)
        return_type = sig.return_annotation
        if return_type == inspect.Signature.empty:
            return None

        type_name = getattr(return_type, '__name__', str(return_type))
        if 'Union' in str(return_type):
            type_name = str(return_type).split('[')[1].split(',')[0].strip()

        return self.type_map.get(type_name, type_name)

    def generate(self) -> Tuple[str, str, str]:
        """Generates JS definitions, Python generators, and the category XML."""
        blocks_js = []
        generators_py = []
        xml_blocks = []

        for name, method in inspect.getmembers(self.cls, predicate=inspect.isfunction):
            if not hasattr(method, "_is_mced_block"):
                continue

            block_type = f"{self.cls.__name__.lower()}_{name}"
            label = method._mced_label
            params = method._mced_params
            output_type = self._get_output_type(method)
            tooltip = inspect.getdoc(method) or ""

            blocks_js.append(self._generate_js_definition(block_type, label, params, output_type, tooltip))
            generators_py.append(self._generate_python_generator(block_type, name, params))
            xml_blocks.append(self._generate_xml_block(block_type, params))

        category_xml = f'<category name="{self.cls.__name__}" colour="{self.category_colour}">\n' + "\n".join(xml_blocks) + "\n</category>"

        return "\n".join(blocks_js), "\n".join(generators_py), category_xml

    def _generate_js_definition(self, block_type, label, params, output_type, tooltip):
        args_js_list = []
        for param_name, meta in params.items():
            arg_label = meta.get('label', param_name.title())
            args_js_list.append(f"this.appendValueInput('{param_name}').appendField('{arg_label}');")

        newline = '\n'
        args_js_str = newline.join(args_js_list)
        clean_tooltip = tooltip.replace('"', '\\"').replace('\n', ' ')
        output_js = f"this.setOutput(true, '{output_type}');" if output_type else "this.setPreviousStatement(true); this.setNextStatement(true);"

        return f"""
    Blockly.Blocks['{block_type}'] = {{
        init: function() {{
            this.appendDummyInput().appendField("{label}");
            {args_js_str}
            {output_js}
            this.setColour("{self.category_colour}");
            this.setTooltip("{clean_tooltip}");
        }}
    }};"""

    def _generate_python_generator(self, block_type, method_name, params):
        arg_collectors_list = []
        for p in params:
            arg_collectors_list.append(f"const {p} = generator.valueToCode(block, '{p}', pythonGenerator.ORDER_ATOMIC) || 'None';")

        newline = '\n'
        arg_collectors_str = newline.join(arg_collectors_list)
        args_template = ", ".join([f"${{{p}}}" for p in params])

        return f"""
    pythonGenerator.forBlock['{block_type}'] = function(block, generator) {{
        {arg_collectors_str}
        const code = `.{method_name}({args_template})\\n`;
        return block.outputConnection ? [code.trim(), pythonGenerator.ORDER_ATOMIC] : code;
    }};"""

    def _generate_xml_block(self, block_type, params):
        values_xml = []
        for p_name, meta in params.items():
            shadow = meta.get('shadow')
            if shadow:
                full_shadow = self.shadow_map.get(shadow, shadow)
                values_xml.append(f'<value name="{p_name}">{full_shadow}</value>')

        return f'<block type="{block_type}">{" ".join(values_xml)}</block>'

    @staticmethod
    def _get_clean_tag(element: ET.Element) -> str:
        """Helper to get tag name without namespace for comparison."""
        return element.tag.split('}')[-1]

    @staticmethod
    def generate_picker(block_type: str, label: str, options: List[Tuple[str, str]],
                      output_type: str, colour: Any, tooltip: str = "") -> Dict[str, str]:
        """Creates a standard dropdown picker block."""
        formatted_options = ',\n'.join([f'                ["{opt[0]}", "{opt[1]}"]' for opt in options])
        clean_tooltip = tooltip.replace('"', '\\"').replace('\n', ' ')

        js_def = f"""
    Blockly.Blocks['{block_type}'] = {{
        init: function() {{
            this.appendDummyInput()
                .appendField("{label}")
                .appendField(new Blockly.FieldDropdown([
{formatted_options}
                ]), "VALUE");
            this.setOutput(true, "{output_type}");
            this.setColour("{colour}");
            this.setTooltip("{clean_tooltip}");
        }}
    }};"""

        py_gen = f"""
    pythonGenerator.forBlock['{block_type}'] = function(block, generator) {{
        return [`'${{block.getFieldValue('VALUE')}}'`, pythonGenerator.ORDER_ATOMIC];
    }};"""

        return {"js": js_def, "py": py_gen, "xml": f'<block type="{block_type}"></block>'}

    @staticmethod
    def generate_parameterized_block(block_type: str, label: str, input_name: str,
                                   input_type: str, output_type: str, colour: Any,
                                   template: str, shadow_block: Optional[str] = None) -> Dict[str, str]:
        """Creates a block that takes an input and wraps it in a string template."""
        js_def = f"""
    Blockly.Blocks['{block_type}'] = {{
        init: function() {{
            this.appendValueInput('{input_name}')
                .setCheck('{input_type}')
                .appendField('{label}');
            this.setOutput(true, '{output_type}');
            this.setColour("{colour}");
        }}
    }};"""

        safe_template = template.replace('{}', f'${{val}}')
        py_template = f"`'{safe_template}'`"

        py_gen = f"""
    pythonGenerator.forBlock['{block_type}'] = function(block, generator) {{
        const rawVal = generator.valueToCode(block, '{input_name}', pythonGenerator.ORDER_ATOMIC) || "''";
        const val = rawVal.replace(/['"]/g, '');
        return [{py_template}, pythonGenerator.ORDER_ATOMIC];
    }};"""

        xml = f'<block type="{block_type}">'
        if shadow_block:
            xml += f'<value name="{input_name}"><shadow type="{shadow_block}"></shadow></value>'
        xml += '</block>'

        return {"js": js_def, "py": py_gen, "xml": xml}

    @staticmethod
    def update_toolbox(category_xml: str, toolbox_path: Path):
        """Standard append-or-replace category update logic, handling namespaces correctly."""
        if not toolbox_path.exists(): return

        tree = ET.parse(toolbox_path)
        root = tree.getroot()

        # Ensure snippet is parsed in the correct namespace
        new_cat = ET.fromstring(f'<xml xmlns="{BLOCKLY_NS}">{category_xml}</xml>')[0]
        new_name = new_cat.get('name')

        # Find and remove existing category with same name (namespace agnostic)
        to_remove = []
        for cat in root.findall('.//{*}category'):
            if cat.get('name') == new_name:
                to_remove.append(cat)

        for cat in to_remove:
            # Finding the parent in ElementTree to perform removal
            for parent in root.findall('.//*'):
                if cat in parent:
                    parent.remove(cat)
                elif cat in root:
                    root.remove(cat)

        root.append(new_cat)
        tree.write(toolbox_path, encoding='utf-8', xml_declaration=True)

    @staticmethod
    def inject_into_category(category_name: str, block_xml_snippet: str, toolbox_path: Path):
        """Finds a category by name and appends block XML to it, namespace-safely."""
        if not toolbox_path.exists(): return

        tree = ET.parse(toolbox_path)
        root = tree.getroot()

        # Find target category (namespace agnostic)
        target_cat = None
        for cat in root.findall('.//{*}category'):
            if cat.get('name') == category_name:
                target_cat = cat
                break

        if target_cat is not None:
            # Parse snippet in standard namespace
            snippet = ET.fromstring(f'<xml xmlns="{BLOCKLY_NS}">{block_xml_snippet}</xml>')
            for block in snippet:
                target_cat.append(block)
            tree.write(toolbox_path, encoding='utf-8', xml_declaration=True)