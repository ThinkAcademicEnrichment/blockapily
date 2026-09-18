import unittest
import re
import tempfile
import os
import subprocess
from pathlib import Path

class TestReadmeDocs(unittest.TestCase):
    def test_readme_code_blocks(self):
        # Resolve repo root relative to this test file (tests/test_readme_code_blocks.py)
        repo_root = Path(__file__).parent.parent.absolute()
        readme_path = repo_root / 'README.md'
        
        self.assertTrue(readme_path.exists(), "README.md not found.")
        content = readme_path.read_text(encoding='utf-8')
        
        # Extract all python code blocks
        blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
        self.assertGreater(len(blocks), 0, "No Python blocks found in README.md")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            script_to_run = None

            for block in blocks:
                lines = block.split('\n')
                first_line = lines[0].strip()
                
                if first_line.startswith('#') and first_line.endswith('.py'):
                    filename = first_line.lstrip('#').strip()
                    file_path = tmp_path / filename
                    file_path.write_text(block, encoding='utf-8')
                    
                    if 'generate' in filename:
                        script_to_run = file_path

            self.assertIsNotNone(script_to_run, "No executable generator script found in README blocks.")

            # Inject the repository root into PYTHONPATH so the subprocess finds 'blockapily'
            env = os.environ.copy()
            env["PYTHONPATH"] = f"{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"

            result = subprocess.run(
                ['python', script_to_run.name],
                cwd=tmpdir,
                env=env,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                self.fail(f"README code execution failed:\n{result.stderr}")

            output_dir = tmp_path / "generated_assets"
            self.assertTrue(output_dir.exists(), "Output directory was not created.")
            self.assertTrue((output_dir / "block_definitions.js").exists())
            self.assertTrue((output_dir / "python_generators.js").exists())
            self.assertTrue((output_dir / "toolbox.xml").exists())
            self.assertTrue((output_dir / "toolbox.json").exists())

if __name__ == '__main__':
    unittest.main()