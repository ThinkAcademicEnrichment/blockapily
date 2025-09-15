import inspect
import re
from pathlib import Path
import xml.etree.ElementTree as ET

# --- Decorator and Defaults ---
def mced_block(label, **kwargs):
    def decorator(func):
        func._mced_block_meta = {'label': label, 'params': kwargs}
        return func
    return decorator

DEFAULT_TYPE_MAP = {int: "Number", float: "Number", str: "String", bool: "Boolean"}
DEFAULT_SHADOW_MAP = {
    int: '<shadow type="math_number"><field name="NUM">{default}</field></shadow>',
    float: '<shadow type="math_number"><field name="NUM">{default}</field></shadow>',
    str: '<shadow type="text"><field name="TEXT">{default}</field></shadow>',
    bool: '<shadow type="logic_boolean"><field name="BOOL">{default}</field></shadow>',
}

class BlocklyGenerator:
    # __init__ and all _generate_* methods remain the same as the previous version.
    def __init__(self, target_class, type_map=None, shadow_map=None, block_prefix=None, category_name=None, category_colour=None):
        self.target_class = target_class
        if block_prefix: self.block_prefix = block_prefix
        else: self.block_prefix = f"{self._camel_to_snake(self.target_class.__name__)}_"
        if category_name: self.category_name = category_name
        else: self.category_name = re.sub(r'(\w)([A-Z])', r'\1 \2', self.target_class.__name__)
        self.category_colour = category_colour
        self.type_map = DEFAULT_TYPE_MAP.copy()
        if type_map: self.type_map.update(type_map)
        self.shadow_map = DEFAULT_SHADOW_MAP.copy()
        if shadow_map: self.shadow_map.update(shadow_map)

    @staticmethod
    def update_toolbox(category_xml: str, toolbox_path: Path):
        """
        Updates a toolbox.xml file with a new or updated category.

        If a category with the same name exists, its contents are replaced.
        If it does not exist, the new category is appended to the toolbox.

        Args:
            category_xml (str): The XML fragment for the category.
            toolbox_path (Path): Pathlib object for the toolbox.xml file.
        """
        # Ensure the XML file and its parent directory exist
        toolbox_path.parent.mkdir(parents=True, exist_ok=True)
        if not toolbox_path.is_file():
            # Add the namespace to the boilerplate toolbox
            toolbox_path.write_text('<toolbox xmlns="https://developers.google.com/blockly/xml"></toolbox>')

        ET.register_namespace('', "https://developers.google.com/blockly/xml")

        tree = ET.parse(toolbox_path)
        root = tree.getroot()

        new_category_element = ET.fromstring(category_xml)
        category_name = new_category_element.get('name')

        # --- FIX APPLIED HERE ---
        # 1. Define the namespace dictionary. The empty key is for the default namespace.
        ns = {'': "https://developers.google.com/blockly/xml"}
        # 2. Use the namespace in the find query.
        existing_category = root.find(f"./category[@name='{category_name}']", namespaces=ns)
        if existing_category is not None:
            # Category exists, so clear it and update its contents
            existing_category.clear()
            existing_category.attrib = new_category_element.attrib
            for block in new_category_element:
                existing_category.append(block)
        else:
            # Category does not exist, so append the new one
            root.append(new_category_element)

        ET.indent(tree, space="  ", level=0)
        tree.write(toolbox_path, xml_declaration=True, encoding='utf-8')

    def generate(self, autogenerate=True):
        all_defs, all_gens, all_toolbox_blocks = [], [], []
        for name, method in inspect.getmembers(self.target_class, inspect.isfunction):
            unwrapped = inspect.unwrap(method)
            if hasattr(unwrapped, '_mced_block_meta'):
                sig, meta, block_name = inspect.signature(unwrapped), unwrapped._mced_block_meta, f"{self.block_prefix}{name}"
                block_def, py_gen, toolbox_xml = self._generate_single_block_code(block_name, sig, meta, autogenerate)
                all_defs.append(block_def)
                all_gens.append(py_gen)
                all_toolbox_blocks.append(toolbox_xml)

        joined_blocks = "\n    ".join(all_toolbox_blocks)
        colour_attr = f'colour="{self.category_colour}"' if self.category_colour else ''
        final_category_xml = f'<category name="{self.category_name}" {colour_attr}>\n    {joined_blocks}\n  </category>'
        return "\n".join(all_defs), "\n".join(all_gens), final_category_xml


    # All private helper methods (_camel_to_snake, _generate_*, etc.) are unchanged.
    def _camel_to_snake(self, name): return re.sub('([a-z0-9])([A-Z])', r'\1_\2', re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)).lower()
    def _generate_block_definition(self, block_name, sig, meta, autogenerate):
        # Unchanged from previous version
        inputs_js, shadow_config_js = [], []
        params = list(sig.parameters.values())[1:]
        for param in params:
            param_meta = meta['params'].get(param.name, {})
            input_name = param.name.upper()
            label = param_meta.get('label', param.name.replace('_', ' ').title())
            check_type = self.type_map.get(param.annotation)
            js_check_str = f'"{check_type}"' if check_type else "null"
            inputs_js.append(f'this.appendValueInput("{input_name}").setCheck({js_check_str}).setAlign("RIGHT").appendField("{label}");')
            shadow_template = self.shadow_map.get(param.annotation)
            if autogenerate and shadow_template:
                default_value = ""
                if param.default is not inspect.Parameter.empty: default_value = str(param.default).upper() if isinstance(param.default, bool) else param.default
                else:
                    if param.annotation in (int, float): default_value = 0
                    elif param.annotation is bool: default_value = "TRUE"
                shadow_xml = shadow_template.format(default=default_value)
                escaped_xml = shadow_xml.replace('\\', '\\\\').replace("'", "\\'")
                shadow_config_js.append(f"this.getInput('{input_name}').connection.setShadowDom(Blockly.utils.xml.textToDom(`{escaped_xml}`));")
        inputs_str, shadow_config_str, block_label = "\n        ".join(inputs_js), "\n        ".join(shadow_config_js), meta['label']
        output_type = meta.get('params', {}).get('output_type')
        connection_js = f'this.setOutput(true, "{output_type}");' if output_type else "this.setPreviousStatement(true, null);\n        this.setNextStatement(true, null);"
        return f"""Blockly.Blocks['{block_name}'] = {{\n    init: function() {{\n        this.appendDummyInput().appendField("{block_label}");\n        {inputs_str}\n        {connection_js}\n        this.setColour(65);\n        this.setTooltip("An auto-generated block for the '{block_label}' action.");\n        this.setInputsInline(false);\n\n        // Configure shadow blocks directly\n        {shadow_config_str}\n    }}\n}};"""

    def _generate_python_generator(self, block_name, sig, meta):
        # Unchanged from previous version
        value_declarations, params = [], list(sig.parameters.values())[1:]
        for param in params:
            default_value = "None"
            if param.default is not inspect.Parameter.empty:
                if isinstance(param.default, str): default_value = f"'{param.default}'"
                elif isinstance(param.default, bool): default_value = str(param.default).lower()
                else: default_value = param.default
            else:
                if param.annotation in (int, float): default_value = 0
                elif param.annotation == str: default_value = "''"
                elif param.annotation == bool: default_value = 'true'
            js_line = f"const {param.name} = generator.valueToCode(block, '{param.name.upper()}', generator.ORDER_ATOMIC) || {default_value};"
            value_declarations.append(js_line)
        declarations_str, method_name = "\n    ".join(value_declarations), block_name.replace(self.block_prefix, "")
        arg_list = [f"{p.name}=${{{p.name}}}" for p in params]
        python_call = f"self.action_implementer.{method_name}({', '.join(arg_list)})"
        output_type = meta.get('params', {}).get('output_type')
        return_statement = f"const code = `{python_call}`;\n    return [code, generator.ORDER_FUNCTION_CALL];" if output_type else f"return `{python_call}\\n`;"
        return f"""pythonGenerator.forBlock['{block_name}'] = function(block, generator) {{\n    {declarations_str}\n    {return_statement}\n}};"""

    def _generate_toolbox_xml_for_block(self, block_name): return f'<block type="{block_name}"></block>'

    def _generate_single_block_code(self, block_name, sig, meta, autogenerate):
        block_def = self._generate_block_definition(block_name, sig, meta, autogenerate)
        py_gen = self._generate_python_generator(block_name, sig, meta)
        toolbox_xml = self._generate_toolbox_xml_for_block(block_name)
        return block_def, py_gen, toolbox_xml
