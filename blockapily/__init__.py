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

        # Handle string literals and actual type objects
        type_name = getattr(return_type, '__name__', str(return_type)).strip("'\"")

        if 'Union' in type_name:
            # Simple extraction for Union types if needed
            try:
                type_name = type_name.split('[')[1].split(',')[0].strip()
            except: pass

        return self.type_map.get(type_name, type_name)

    def generate(self) -> Tuple[str, str, str]:
        """Generates JS definitions, Python generators, and the category XML."""
        blocks_js = []
        generators_py = []
        xml_blocks = []

        # Get docstring for the class to use as category name if needed
        for name, method in inspect.getmembers(self.cls, predicate=inspect.isfunction):
            if not hasattr(method, "_is_mced_block"):
                continue

            block_type = f"{self.cls.__name__.lower()}_{name}"
            label = method._mced_label
            params = method._mced_params
            output_type = self._get_output_type(method)
            tooltip = inspect.getdoc(method) or ""

            blocks_js.append(self._generate_js_definition(block_type, label, params, output_type, tooltip, method))
            generators_py.append(self._generate_python_generator(block_type, name, params))
            xml_blocks.append(self._generate_xml_block(block_type, params))

        category_xml = f'<category name="{self.cls.__name__}" colour="{self.category_colour}">\n' + "\n".join(xml_blocks) + "\n</category>"

        return "\n".join(blocks_js), "\n".join(generators_py), category_xml

    def _resolve_js_check_type(self, param_type) -> Optional[str]:
        """Helper to resolve Python type hints into JS array or string strings for .setCheck()"""
        param_str = str(param_type).strip("'\"")

        # Handle Union[TypeA, TypeB] -> "['MappedA', 'MappedB']"
        if 'Union' in param_str:
            try:
                inner = param_str.split('[')[1].split(']')[0]
                types = []
                for t in inner.split(','):
                    t_clean = t.strip().strip("'\"")
                    if '<class' in t_clean:
                        t_clean = t_clean.split("'")[1]
                    types.append(t_clean)
                mapped_types = [self.type_map.get(mt, mt) for mt in types]
                return "[" + ", ".join(f"'{mt}'" for mt in mapped_types) + "]"
            except Exception:
                pass

        # Handle single types/classes
        type_name = getattr(param_type, '__name__', param_str).strip("'\"")
        if '<class' in type_name:
            type_name = type_name.split("'")[1]

        mapped = self.type_map.get(type_name, type_name)
        return f"'{mapped}'" if mapped else None

    def _generate_js_definition(self, block_type, label, params, output_type, tooltip, method):
        args_js_list = []
        sig = inspect.signature(method)

        for param_name, meta in params.items():
            # CRITICAL FIX: Only generate inputs for things actually in the method signature
            if param_name not in sig.parameters:
                continue

            # Ensure meta is a dictionary
            if not isinstance(meta, dict):
                meta = {}

            arg_label = meta.get('label', param_name.title())
            input_js = f"this.appendValueInput('{param_name}').appendField('{arg_label}')"

            # Extract and map the type hint from the method signature
            param_type = sig.parameters[param_name].annotation
            if param_type != inspect.Signature.empty:
                check_str = self._resolve_js_check_type(param_type)
                if check_str:
                    input_js += f".setCheck({check_str})"

            args_js_list.append(input_js + ";")

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
            # Simple check to avoid generating code for non-params like 'tooltip'
            # Note: The JS definition loop already filters these, but we do it here for symmetry
            arg_collectors_list.append(f"const {p} = generator.valueToCode(block, '{p}', pythonGenerator.ORDER_ATOMIC) || 'None';")

        newline = '\n'
        arg_collectors_str = newline.join(arg_collectors_list)
        # Filter logic here would be redundant as the block itself won't have the input fields
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
            if not isinstance(meta, dict): continue
            shadow = meta.get('shadow')
            if shadow:
                full_shadow = self.shadow_map.get(shadow, shadow)
                values_xml.append(f'<value name="{p_name}">{full_shadow}</value>')

        return f'<block type="{block_type}">{" ".join(values_xml)}</block>'

    @staticmethod
    def generate_picker(block_type: str, label: str, options: List[Tuple[str, str]],
                      output_type: str, colour: Any, tooltip: str = "") -> Dict[str, str]:
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
        xml = f'<block type="{block_type}"><value name="{input_name}"><shadow type="{shadow_block}"></shadow></value></block>'
        return {"js": js_def, "py": py_gen, "xml": xml}

    @staticmethod
    def _strip_ns_prefix(root: ET.Element):
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
        return root

    @staticmethod
    def update_toolbox(category_xml: str, toolbox_path: Path):
        if not toolbox_path.exists(): return
        tree = ET.parse(toolbox_path)
        root = tree.getroot()
        temp_xml = ET.fromstring(f'<xml xmlns="{BLOCKLY_NS}">{category_xml}</xml>')
        new_cat = temp_xml[0]
        new_name = new_cat.get('name')
        to_remove = [cat for cat in root.findall('.//{*}category') if cat.get('name') == new_name]
        for cat in to_remove:
            for parent in root.iter():
                if cat in parent:
                    parent.remove(cat)
                    break
        root.append(new_cat)
        root.tag = "xml"
        BlocklyGenerator._strip_ns_prefix(root)
        tree.write(toolbox_path, encoding='utf-8', xml_declaration=True)