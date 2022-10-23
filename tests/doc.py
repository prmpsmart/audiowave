import sys

sys.path.append(
    r"C:\Users\Administrator\Desktop\GITHUB_PROJECTS\audiowave\examples\mimi_wave_ui\mimi_wave"
)
import pydoc, py_audiowave as py_audiowave

p = pydoc.render_doc(
    py_audiowave, title="AudioWave Library Documentation: %s", renderer=pydoc.plaintext
)
open("audiowave.MD", "w").write(f"```\n{p}\n```")
