import inspect
import typing
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union, Dict, Any, List, Optional, Tuple, Callable

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
    def __init__(self, cls: Any, type_map: Dict[str, str], shadow_map: Dict[str, str],category_colour: str = "#333", category_name:str = None):
        self.cls = cls
        self.type_map = type_map
        self.shadow_map = shadow_map
        self.category_colour = category_colour
        self.category_name = category_name if category_name is not None else self.cls.__name__

    def _getmembers_ordered(self,cls, predicate=None):
        """
        A drop-in replacement for inspect.getmembers that preserves 
        the definition order of class members.
        """
        results = {}
        
        # Walk the Method Resolution Order (MRO)
        for base in inspect.getmro(cls):
            # base.__dict__ preserves definition order in modern Python
            for key, value in base.__dict__.items():
                # Only add it if we haven't seen it yet (child overrides parent)
                if key not in results:
                    results[key] = value

        # Apply the optional predicate filter (e.g., inspect.isroutine)
        if predicate:
            return [(k, v) for k, v in results.items() if predicate(v)]
        
        return list(results.items())

    def _get_output_type(self, func: Callable) -> Optional[str]:
        """Maps Python return type hints to Blockly types using the provided type_map."""
        sig = inspect.signature(func)
        return_type = sig.return_annotation
        if return_type == inspect.Signature.empty:
            return None

        # Handle typing.Union or other typing generics
        if hasattr(return_type, '__origin__') and return_type.__origin__ is Union:
            # We take the first type in the Union
            type_obj = return_type.__args__[0]
            type_name = getattr(type_obj, '__name__', str(type_obj)).strip("'\"")
        else:
            # Handle string literals and actual type objects
            type_name = getattr(return_type, '__name__', str(return_type)).strip("'\"")

            if 'Union' in type_name:
                # Simple extraction for string-based Union types if needed (e.g. "Union[MCStructure, DigitalSet]")
                try:
                    type_name = type_name.split('[')[1].split(',')[0].strip()
                except: pass

        return self.type_map.get(type_name, type_name)

    def generate(self) -> Tuple[str, str, str]:
        """Generates JS definitions, Python generators, and the category XML."""
        blocks_js = []
        generators_py = []
        xml_blocks = []
        json_blocks = []

        # Get docstring for the class to use as category name if needed
        for name, method in self._getmembers_ordered(self.cls, predicate=inspect.isfunction):
            if not hasattr(method, "_is_mced_block"):
                continue

            block_type = f"{self.cls.__name__.lower()}_{name}"
            label = method._mced_label
            params = method._mced_params
            output_type = self._get_output_type(method)
            tooltip = inspect.getdoc(method) or ""

            blocks_js.append(self._generate_js_definition(block_type, label, params, output_type, tooltip, method))
            generators_py.append(self._generate_python_generator(block_type, name, params))
            xml_blocks.append(self._generate_xml_block(block_type, params, method))
            json_blocks.append(self._generate_json_block(block_type, params, method))

        category_xml = f'<category name="{self.category_name}" colour="{self.category_colour}">\n' + "\n".join(xml_blocks) + "\n</category>"

        # Build the category as a dictionary
        category_dict = {
            "kind": "category",
            "name": self.category_name,
            "colour": self.category_colour,
            "contents": json_blocks
        }
        return "\n".join(blocks_js), "\n".join(generators_py), category_xml, category_dict

    def _resolve_js_check_type(self, annotation):
        """
        Translates a Python type hint into a Blockly .setCheck() string argument.
        Returns a string like "'Number'" or "['Number', 'String']", or None.
        """
        if annotation == inspect.Signature.empty:
            return None

        # 1. Check if the annotation is a Union (or Optional)
        origin = typing.get_origin(annotation)
        
        # Note: type(annotation).__name__ == 'UnionType' handles Python 3.10+ (X | Y) syntax
        if origin is typing.Union or type(annotation).__name__ == 'UnionType':
            types_list = []
            
            for arg in typing.get_args(annotation):
                # Extract the clean name
                if isinstance(arg, typing.ForwardRef):
                    t_clean = arg.__forward_arg__
                elif hasattr(arg, '__name__'):
                    t_clean = arg.__name__
                else:
                    t_clean = str(arg)

                # Skip NoneType (Blockly doesn't use this; inputs are just left empty)
                if t_clean == 'NoneType':
                    continue
                    
                types_list.append(t_clean)
                
            # Apply your Blockly type mapping and remove duplicates
            mapped_types = list(set([self.type_map.get(mt, mt) for mt in types_list]))
            
            if not mapped_types:
                return None
            elif len(mapped_types) == 1:
                return f"'{mapped_types[0]}'" # e.g., "'MappedType'"
            else:
                return "[" + ", ".join(f"'{mt}'" for mt in mapped_types) + "]" # e.g., "['TypeA', 'TypeB']"

        # 2. Handle Single Types
        else:
            # Extract the clean name
            if isinstance(annotation, typing.ForwardRef):
                t_clean = annotation.__forward_arg__
            elif isinstance(annotation, str):
                t_clean = annotation # Handle raw string annotations if they slipped through
            elif hasattr(annotation, '__name__'):
                t_clean = annotation.__name__
            else:
                t_clean = str(annotation)
                
            mapped_type = self.type_map.get(t_clean, t_clean)
            return f"'{mapped_type}'" # e.g., "'MappedType'"

    def _generate_js_definition(self, block_type, label, params, output_type, tooltip, method):
        args_js_list = []
        sig = inspect.signature(method)
        for param_name, meta in params.items():
            # Only generate inputs for things actually in the method signature
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
            arg_collectors_list.append(f"const {p} = generator.valueToCode(block, '{p}', pythonGenerator.ORDER_ATOMIC) || 'None';")

        newline = '\n'
        arg_collectors_str = newline.join(arg_collectors_list)
        args_template = ", ".join([f"${{{p}}}" for p in params])

        return f"""
    pythonGenerator.forBlock['{block_type}'] = function(block, generator) {{
        {arg_collectors_str}
        const code = `{self.cls.__name__}.{method_name}({args_template})\\n`;
        return block.outputConnection ? [code.trim(), pythonGenerator.ORDER_ATOMIC] : code;
    }};"""

    def _generate_xml_block(self, block_type, params, method):
        """Generates the XML configuration for a block, automatically inferring shadows from type hints."""
        values_xml = []
        sig = inspect.signature(method)

        # Point to the XML-specific half of your dual-map
        xml_shadow_map = self.shadow_map.get('xml', {})

        for p_name, meta in params.items():
            if not isinstance(meta, dict): continue

            shadow_override = meta.get('shadow')
            full_shadow = None

            # 1. Check for Explicit Override in decorator metadata
            if shadow_override:
                # Handle the new dual-dict format safely
                if isinstance(shadow_override, dict):
                    # .get() returns None if 'xml' is missing, silently skipping it!
                    full_shadow = shadow_override.get('xml') 
                # Fallback: if it's a string key, look it up in the XML map
                elif isinstance(shadow_override, str):
                    full_shadow = xml_shadow_map.get(shadow_override, shadow_override)

            elif p_name in sig.parameters:
                param_type = sig.parameters[p_name].annotation
                if param_type != inspect.Signature.empty:

                    type_name = getattr(param_type, '__name__', str(param_type)).strip("'\"")
                    if '<class' in type_name:
                        type_name = type_name.split("'")[1].split('.')[-1]

                    # Handle Union by prioritizing the first type for shadows
                    if 'Union' in type_name:
                        try:
                            inner = type_name.split('[')[1].split(']')[0]
                            type_name = inner.split(',')[0].strip().strip("'\"")
                            if '<class' in type_name:
                                type_name = type_name.split("'")[1].split('.')[-1]
                        except: pass

                    if type_name in xml_shadow_map:
                        full_shadow = xml_shadow_map[type_name]

            if full_shadow:
                values_xml.append(f'<value name="{p_name}">{full_shadow}</value>')

        return f'<block type="{block_type}">{" ".join(values_xml)}</block>'

    def _generate_json_block(self, block_type, params, method):
        """Generates the JSON configuration for a block, automatically inferring shadows."""
        inputs_dict = {}
        sig = inspect.signature(method)
        
        # Point to the JSON-specific half of your dual-map
        json_shadow_map = self.shadow_map.get('json', {})

        for p_name, meta in params.items():
            if not isinstance(meta, dict): continue

            shadow_override = meta.get('shadow')
            full_shadow = None

            # 1. Check for Explicit Override in decorator metadata
            if shadow_override:
                # Handle the new dual-dict format: {'xml': ..., 'json': ...}
                if isinstance(shadow_override, dict) and 'json' in shadow_override:
                    full_shadow = shadow_override['json']
                # Fallback: if it's a string key, look it up in the JSON map
                elif isinstance(shadow_override, str):
                    full_shadow = json_shadow_map.get(shadow_override, shadow_override)
            
            # 2. Check for Implicit Match via Python type hint
            elif p_name in sig.parameters:
                param_type = sig.parameters[p_name].annotation
                if param_type != inspect.Signature.empty:

                    type_name = getattr(param_type, '__name__', str(param_type)).strip("'\"")
                    if '<class' in type_name:
                        type_name = type_name.split("'")[1].split('.')[-1]

                    # Handle Union by prioritizing the first type for shadows
                    if 'Union' in type_name:
                        try:
                            inner = type_name.split('[')[1].split(']')[0]
                            type_name = inner.split(',')[0].strip().strip("'\"")
                            if '<class' in type_name:
                                type_name = type_name.split("'")[1].split('.')[-1]
                        except: pass

                    # Resolve automatically via JSON shadow map
                    if type_name in json_shadow_map:
                        full_shadow = json_shadow_map[type_name]

            # 3. Assemble the inputs dictionary
            if full_shadow:
                inputs_dict[p_name] = {
                    "shadow": full_shadow
                }

        # 4. Build and return the final block dictionary
        block_dict = {
            "kind": "block",
            "type": block_type
        }
        
        if inputs_dict:
            block_dict["inputs"] = inputs_dict

        return block_dict

    @staticmethod
    def generate_picker(block_type: str, label: str, options: List[Tuple[str, str]],
                        output_type: str, colour: Any, tooltip: str = "") -> Dict[str, Any]:
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

        # XML and JSON toolbox representations
        xml = f'<block type="{block_type}"></block>'
        json_def = {
            "kind": "block",
            "type": block_type
        }

        return {"js": js_def, "py": py_gen, "xml": xml, "json": json_def}


    @staticmethod
    def generate_parameterized_block(block_type: str, label: str, input_name: str,
                                     input_type: str, output_type: str, colour: Any,
                                     template: str, shadow_block: Optional[str] = None) -> Dict[str, Any]:
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
        
        # Split the template to find the prefix and suffix (e.g. "{}_WOOL" -> prefix="", suffix="_WOOL")
        prefix, suffix = template.split('{}') if '{}' in template else (template, "")
        
        py_gen = f"""
    pythonGenerator.forBlock['{block_type}'] = function(block, generator) {{
        const rawVal = generator.valueToCode(block, '{input_name}', pythonGenerator.ORDER_NONE) || "''";
        let pyCode;
        
        // 1. Check if the incoming code is a simple quoted string (from a standard picker)
        if (/^'.*'$/.test(rawVal) || /^".*"$/.test(rawVal)) {{
            const unquoted = rawVal.substring(1, rawVal.length - 1);
            pyCode = `'{prefix}${{unquoted}}{suffix}'`;
        }} else {{
            // 2. It's dynamic code (like random.choice). Output Python string concatenation!
            pyCode = `'{prefix}' + str(${{rawVal}}) + '{suffix}'`;
        }}
        
        // Wrap in parens to guarantee order safety, return as ATOMIC
        return [`(${{pyCode}})`, pythonGenerator.ORDER_ATOMIC];
    }};"""
        
        xml = f'<block type="{block_type}"><value name="{input_name}"><shadow type="{shadow_block}"></shadow></value></block>' 
        
        # Safe JSON construction for parameterized blocks
        json_def = {
            "kind": "block",
            "type": block_type,
            "inputs": {
                input_name: {}
            }
        }
        
        if shadow_block:
            json_def["inputs"][input_name]["shadow"] = {
                "type": shadow_block
            }

        return {"js": js_def, "py": py_gen, "xml": xml, "json": json_def}
    
    @staticmethod
    def _strip_ns_prefix(root: ET.Element):
        for elem in root.iter():
            if '}' in elem.tag:
                elem.tag = elem.tag.split('}', 1)[1]
        return root

    @staticmethod
    def update_toolbox(category_xml: str, toolbox_path: Path, append_separator:bool = False):
        if not toolbox_path.exists():
            root = ET.Element('xml', {'xmlns': BLOCKLY_NS})
            tree = ET.ElementTree(root)
        else:
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
        if append_separator:
            root.append(ET.fromstring('<sep/>'))

        root.tag = "xml"
        BlocklyGenerator._strip_ns_prefix(root)

        toolbox_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(toolbox_path, encoding='utf-8', xml_declaration=True)

    @staticmethod
    def update_toolbox_json(category_json: dict, toolbox_path: Path, append_separator: bool = False):
        import json
        
        if not toolbox_path.exists():
            toolbox_data = {
                "kind": "categoryToolbox",
                "contents": []
            }
        else:
            with open(toolbox_path, 'r', encoding='utf-8') as f:
                toolbox_data = json.load(f)

        new_name = category_json.get('name')

        # Remove existing category with the same name if it exists
        if 'contents' in toolbox_data:
            toolbox_data['contents'] = [
                item for item in toolbox_data['contents']
                if not (item.get('kind') == 'category' and item.get('name') == new_name)
            ]
        else:
            toolbox_data['contents'] = []

        # Append new category and optional separator
        toolbox_data['contents'].append(category_json)
        if append_separator:
            toolbox_data['contents'].append({"kind": "sep"})

        toolbox_path.parent.mkdir(parents=True, exist_ok=True)
        with open(toolbox_path, 'w', encoding='utf-8') as f:
            json.dump(toolbox_data, f, indent=4)
