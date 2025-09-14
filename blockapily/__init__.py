# --- Block API Generation

TYPE_MAP = {
    float: "Number", int: "Number", str: "String", bool: "Boolean",
    'Vec3': "3DVector", 'Matrix3': "3DMatrix", 'Block': "Block"
}
def generate_block_definition(block_name, sig, meta):
    """
    Generates the Blockly.Blocks[...] JavaScript, now with support for
    creating blocks with output connections if `output_type` is specified.
    """
    inputs_js = []
    shadow_calls_js = []
    defaults_js = []

    params = list(sig.parameters.values())[1:]

    for param in params:
        # ... (parameter processing logic remains the same)
        param_meta = meta['params'].get(param.name, {})
        label = param_meta.get('label', param.name.replace('_', ' ').title())
        input_name = param.name.upper()
        check_type = TYPE_MAP.get(param.annotation)
        js_check_str = f'"{check_type}"' if check_type else "null"

        inputs_js.append(f"""this.appendValueInput("{input_name}")
                .setCheck({js_check_str})
                .setAlign('RIGHT')
                .appendField("{label}");""")
        shadow_calls_js.append(f'MCED.BlocklyUtils.configureShadow(this, "{input_name}");')

        shadow = param_meta.get('shadow', 'null')
        if shadow.startswith('<'):
            shadow_value = f"'{shadow}'"
        else:
            shadow_value = f"MCED.{shadow}"
        defaults_js.append(f'            {input_name}: {{ shadow: {shadow_value} }}')

    inputs_str = "\n            ".join(inputs_js)
    shadow_calls_str = "\n            ".join(shadow_calls_js)
    defaults_str = ",\n".join(defaults_js)
    block_label = meta['label']

    # --- NEW: Logic to handle output blocks ---
    connection_js = ""
    output_type = meta.get('params').get('output_type')
    if output_type:
        connection_js = f'this.setOutput(true, "{output_type}");'
    else:
        connection_js = """this.setPreviousStatement(true, null);
            this.setNextStatement(true, null);"""

    return f"""
    Blockly.Blocks['{block_name}'] = {{
        init: function() {{
            this.appendDummyInput().appendField("{block_label}");
            {inputs_str}
            {connection_js}
            this.setColour(65);
            this.setTooltip("An auto-generated block for the {block_label} action.");
            this.setInputsInline(false);

            MCED.Defaults.values['{block_name}'] = {{
    {defaults_str}
            }};

            {shadow_calls_str}
        }}
}};"""

def generate_python_generator(block_name, sig, meta):
    """
    Generates the pythonGenerator.forBlock[...] JavaScript, now correctly
    handling blocks that return values by returning a [code, order] tuple.
    """
    value_declarations = []
    params = list(sig.parameters.values())[1:]

    for param in params:
        # This part remains the same
        default_value = "null"
        if param.annotation in ['Vec3', 'Matrix3']:
            default_value = "Matrix3.identity()" if param.annotation == 'Matrix3' else "Vec3(0,0,0)"
        elif isinstance(param.default, str):
            default_value = f"'{param.default}'"
        elif param.default is not inspect.Parameter.empty:
            default_value = str(param.default)

        js_line = f"const {param.name} = generator.valueToCode(block, '{param.name.upper()}', generator.ORDER_ATOMIC) || {default_value};"
        value_declarations.append(js_line)

    value_declarations_str = "\n        ".join(value_declarations)
    action_method_name = block_name.replace("minecraft_action_", "")

    # Construct the Python method call
    arg_list = [f"{p.name}=${{{p.name}}}" for p in params]
    python_call = f"self.action_implementer.{action_method_name}({', '.join(arg_list)})"

    # --- NEW: Logic to determine the return type ---
    output_type = meta.get('params').get('output_type')
    if output_type:
        # For blocks with an output, wrap the call in `` and return a tuple
        return_statement = f"const code = `{python_call}`;\n        return [code, generator.ORDER_FUNCTION_CALL];"
    else:
        # For statement blocks, add the newline and return a simple string
        return_statement = f"return `{python_call}\n`;"

    return f"""
    pythonGenerator.forBlock['{block_name}'] = function(block, generator) {{
            {value_declarations_str}
            {return_statement}
    }};"""

def generate_api_block_code(actions_class):
    """
    Main function to generate all JS code for decorated methods.
    Now generates only the block definition and the python generator.
    """
    _block_defs = []
    for name, method in inspect.getmembers(actions_class, inspect.isfunction):
        unwrapped_method = inspect.unwrap(method)
        if not hasattr(unwrapped_method, '_mced_block_meta'):
            continue

        print(f"⚙️  Generating code for method: {name}")
        sig = inspect.signature(unwrapped_method)
        meta = unwrapped_method._mced_block_meta
        block_name = f"minecraft_action_{name}"

        # --- MODIFIED: No longer calls generate_defaults_config ---
        _block_defs.append((generate_block_definition(block_name, sig, meta),generate_python_generator(block_name, sig, meta)))

    return _block_defs

def generate_mcactions_blocks():
    output_blocks_dir = MC_APP_SRC_DIR / 'blocks'
    output_python_dir = MC_APP_SRC_DIR / 'generators' / 'python'

    from mcshell.mcactions import MCActions
    for _api_class in MCActions.__bases__:
        _block_output_path = output_blocks_dir / f'{_api_class.__name__}.mjs'
        _gens_output_path = output_python_dir / f'{_api_class.__name__}.mjs'
        _block_output = 'import { MCED } from "../lib/constants.mjs";\n\n' + \
                        f"export function define{_api_class.__name__}Blocks(Blockly) " + "{\n"
        _gens_output = 'import { MCED } from "../../lib/constants.mjs";\n\n' + \
                       f"\n\nexport function define{_api_class.__name__}Generators(pythonGenerator) " + "{\n"

        for _block_defs,_python_gens in generate_api_block_code(_api_class):
            _block_output += _block_defs + "\n"
            _gens_output += _python_gens + "\n"

        _block_output_path.write_text(_block_output + "\n}", 'utf-8')
        print(f"Successfully generated {_block_output_path}")
        _gens_output_path.write_text(_gens_output + "\n}", 'utf-8')
        print(f"Successfully generated {_gens_output_path}" )
