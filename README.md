A command-line Python script that reads a plain-text (`.txt`) file encoded in UTF-8 and synthesises it into an MP3 audio file using the **Google Text-to-Speech (gTTS)** API. The script is self-bootstrapping: it detects whether `gTTS` is installed at runtime and, if not, installs it silently before proceeding.

This script is the second stage of a two-script pipeline. It is designed to consume the `.txt` output produced by `pdf2text_via_PDFplumber.py`, but it accepts any valid UTF-8 `.txt` file as input.

## Overview

| Property | Value |
|---|---|
| **Script name** | `text2speech_via_Google_TTS.py` |
| **Input** | A UTF-8 encoded `.txt` file whose path is supplied as a positional CLI argument |
| **Output** | An MP3 file written to the **current working directory**, named after the stem of the input `.txt` file |
| **Language** | English (`lang='en'`) — hard-coded in the `gTTS` constructor call |
| **Network requirement** | Yes — gTTS transmits the text to Google's TTS servers; an active internet connection is mandatory |
| **Python version** | 3.x (uses f-strings, `subprocess`, `sys`, and `os` from the standard library) |
| **Pipeline role** | Stage 2 — accepts `.txt` output from `pdf2text_via_PDFplumber.py` or any other UTF-8 text source |

## Dependency and Auto-Installation Logic

The script manages its one non-standard dependency without requiring the user to pre-install it. The auto-installation block executes **before** any library-level import.

### Dependency Table

| Import name (key) | PyPI package name (value) | Purpose |
|---|---|---|
| `gtts` | `gTTS` | HTTP client wrapper for Google's Text-to-Speech endpoint; handles text chunking, HTTP request construction, and MP3 stream retrieval |

### Installation Mechanism

```python
required_packages = {
    'gtts': 'gTTS'
}

for import_name, package_name in required_packages.items():
    try:
        __import__(import_name)
    except ImportError:
        print(f"Installing {package_name}...")
        install_package(package_name)
```

The dictionary `required_packages` maps the **module import name** (`'gtts'`) to the **PyPI distribution name** (`'gTTS'`). These differ in capitalisation; using the wrong one with `pip install` would fail.

For each pair:

1. `__import__(import_name)` attempts a dynamic, runtime import of the module by its import name. The return value is discarded; the call is used purely for its side-effect of raising `ImportError` if the module is absent.
2. If `ImportError` is raised, `install_package(package_name)` is called:

   ```python
   subprocess.check_call([sys.executable, "-m", "pip", "install", package, "-q"])
   ```

   - `sys.executable` resolves to the **exact Python interpreter binary** that is currently running the script. This ensures the package is installed into the same environment (system Python, virtualenv, conda environment, etc.) that will subsequently import it. Using a hardcoded `python` string instead would risk installing into a different environment on machines with multiple Python installations.
   - `-m pip` invokes pip as a module of the running interpreter, which is the canonical, environment-safe way to invoke pip programmatically.
   - `-q` (quiet mode) suppresses pip's progress output.
   - `subprocess.check_call` raises `subprocess.CalledProcessError` if the `pip` subprocess exits with a non-zero return code (e.g., network failure, package not found on PyPI). This exception is **not caught** anywhere in the script; it propagates to the interpreter and produces a traceback, aborting execution.

3. After the loop, `from gtts import gTTS` executes unconditionally at the top level. If installation failed silently (which cannot happen given `check_call`'s behaviour), this import would raise `ImportError` and abort.

## Execution Flow and Internal Logic

### Step 1 — Argument Validation

```python
if len(sys.argv) < 2:
    print("Usage: python text2speech_via_Google_TTS.py <path_to_txt_file>")
    sys.exit(1)
```

- `sys.argv` is the list of whitespace-separated command-line tokens passed to the interpreter. By Python convention, `sys.argv[0]` is always the script name (or an empty string in certain embedded contexts).
- The boolean condition `len(sys.argv) < 2` is satisfied if and only if `len(sys.argv) == 1`, meaning the list contains only the script name and **no positional arguments were provided**.
- The script exits immediately with return code `1`, which is the POSIX convention for a user-caused invocation error (as distinct from return code `2` for usage errors in some conventions, or `0` for success). No further lines of the script are executed.

### Step 2 — File Existence and Type Guard

```python
file_path = sys.argv[1]

if not os.path.exists(file_path):
    print(f"Error: File '{file_path}' not found.")
    sys.exit(1)

if not file_path.lower().endswith('.txt'):
    print("Error: File must be a .txt file.")
    sys.exit(1)
```

`sys.argv[1]` is assigned to `file_path` as a raw string exactly as provided on the command line — no normalisation, no resolution of symlinks, no conversion to an absolute path.

Two sequential, independent guard clauses then apply:

**Guard 1 — Existence check:**

`os.path.exists(file_path)` makes a filesystem stat call and returns `True` if the path resolves to any existing filesystem object (regular file, directory, symlink target, etc.) and `False` otherwise. The script does **not** distinguish between "path does not exist" and "path exists but is a directory". A path pointing to a directory would pass this guard but fail later at `open()`.

**Guard 2 — Extension check:**

```python
file_path.lower().endswith('.txt')
```

This is a two-stage string operation:

1. `file_path.lower()` — creates a new string with all Unicode characters mapped to their lowercase equivalents. For the ASCII subset (which covers all file extensions in practice), this is the standard a–z lowercase mapping.
2. `.endswith('.txt')` — returns `True` if and only if the last four characters of the lowercased string are exactly `'.'`, `'t'`, `'x'`, `'t'` (0x2E, 0x74, 0x78, 0x74 in ASCII).

Together, this accepts `.txt`, `.TXT`, `.Txt`, `.tXt`, and all other capitalisation variants of the extension. It does **not** inspect MIME type or file magic bytes; a file named `data.txt` that contains binary data would pass this guard.

The extension check operates on the **full path string**, not just the basename. A path such as `/my.txt.folder/data.pdf` would pass the extension check because the full path string ends in `.pdf`, not `.txt`. Conversely, `/my.txt.data/file` would fail because the full string does not end in `.txt`. This is a consequence of calling `.endswith` on `file_path` directly rather than on `os.path.basename(file_path)`.

### Step 3 — Text File Reading

```python
with open(file_path, "r", encoding="utf-8") as f:
    text = f.read()
```

- `open(file_path, "r", encoding="utf-8")` opens the file in text mode with the UTF-8 codec. The `encoding="utf-8"` argument instructs Python's I/O layer to decode the raw bytes from disk using the UTF-8 variable-length encoding scheme before returning a Python `str` object.
- `f.read()` reads the **entire file contents** into a single `str` object in one call. There is no chunked or streaming read; the full file is loaded into memory at once. The resulting `str` is assigned to `text`.
- If the file contains a UTF-8 BOM (`\xef\xbb\xbf` as the first three bytes), Python's UTF-8 codec will **include** the BOM as the Unicode character `U+FEFF` in the resulting string (unlike the `utf-8-sig` codec, which strips it). This BOM character, if present and passed to gTTS, may affect the audio output of the very first word.
- The `with` block guarantees the file handle is closed on exit, regardless of whether the block exits normally or via an exception.
- Any `IOError`, `UnicodeDecodeError` (if the file contains bytes that are not valid UTF-8), or `PermissionError` is caught by the surrounding `except Exception as e` block, which prints the error message and calls `sys.exit(1)`.

**Character count diagnostic:**

```python
print(f"Text length: {len(text)} characters")
```

This executes after a successful read. `len(text)` returns the number of **Unicode code points** in the string — not the number of bytes on disk and not the number of glyphs. For pure ASCII content, all three measures are identical. For UTF-8 content with multibyte characters (e.g., accented Latin characters, CJK ideographs, emoji), `len(text)` will be **less than** the file's byte size, since those characters are encoded as 2–4 bytes each on disk but count as a single code point in the `str`.

### Step 4 — Output Filename Derivation

```python
output_file = os.path.splitext(os.path.basename(file_path))[0] + ".mp3"
```

This is a deterministic, two-stage string transformation applied to `file_path`:

**Stage A — Isolate the final path component (basename):**

```python
os.path.basename(file_path)
```

Returns the component after the last path separator (`/` on POSIX, `\` or `/` on Windows). Examples:

| `file_path` value | `os.path.basename(...)` result |
|---|---|
| `report.txt` | `report.txt` |
| `/home/user/docs/report.txt` | `report.txt` |
| `C:\Users\user\report.txt` | `report.txt` |
| `./subdir/my.report.v2.txt` | `my.report.v2.txt` |

**Stage B — Split off the extension and replace with `.mp3`:**

```python
os.path.splitext("report.txt")   →   ("report", ".txt")
                             [0]  →   "report"
                   + ".mp3"       →   "report.mp3"
```

`os.path.splitext` splits at the **last dot** in the basename string. For a filename like `my.notes.v3.txt`, the split produces `("my.notes.v3", ".txt")`, and the output filename becomes `my.notes.v3.mp3`.

**Critical behavioural consequence:** The resulting `output_file` is a **bare filename with no directory prefix**. Therefore, the MP3 is always written to the **current working directory** — the directory from which the script is invoked — regardless of where the input `.txt` file is located. If the current working directory differs from the input file's directory, input and output will reside in different directories.

### Step 5 — Text-to-Speech Synthesis and Persistence

```python
tts = gTTS(text, lang='en')
tts.save(output_file)
```

**Construction — `gTTS(text, lang='en')`:**

Instantiates a `gTTS` object. This call does **not** make any network request. It stores the text string and language tag internally. The `lang='en'` argument selects the English language TTS model on Google's servers. This parameter is hard-coded and applies unconditionally, regardless of the actual language of the text content.

Internally, gTTS partitions the text into segments before submission. Google's TTS endpoint enforces a per-request character limit (the exact limit is internal to gTTS's implementation, but it operates around ~100 characters per token boundary based on sentence/phrase boundaries). gTTS handles this chunking automatically, splitting on punctuation and whitespace, so the caller does not need to manage text segmentation.

**Synthesis and persistence — `tts.save(output_file)`:**

Triggers the actual synthesis pipeline:

1. gTTS iterates over its internally computed text chunks.
2. For each chunk, it constructs an HTTPS GET request to Google's TTS endpoint with the chunk text and language as query parameters.
3. The server returns a stream of MP3-encoded audio bytes.
4. gTTS concatenates the binary MP3 data from all chunk responses in sequence.
5. The concatenated binary data is written to the file at path `output_file`.

This operation is **synchronous and blocking**: `tts.save()` does not return until all HTTP requests have completed and the file has been fully written to disk. There is no per-chunk progress update emitted by the script; the `"Converting text to speech..."` message is printed once before this call, and `"Audio file saved as '...'"` is printed once after it returns.

The resulting file is a standard **MP3** (MPEG-1 Audio Layer III) binary file. It is the direct concatenation of the MP3 streams returned by Google's TTS API for each text chunk, meaning the file may contain multiple concatenated MP3 frames — one set per chunk. This is still a valid, playable MP3 stream.

## Algorithmic Operations

### Character Count Reporting

```python
print(f"Text length: {len(text)} characters")
```

`len(text)` computes the number of Unicode code points in the string `text`. For a file of size `B` bytes encoded in UTF-8:

- If all characters are ASCII (code points U+0000–U+007F), each occupies exactly 1 byte, so `len(text) = B`.
- If the file contains multibyte UTF-8 sequences, then `len(text) < B`, because each such character occupies 2–4 bytes on disk but is counted as 1 by `len`.

This value is printed for diagnostic purposes only and does not influence any downstream computation. It is not used to decide whether to proceed, to partition the text, or to set any parameter of the `gTTS` call.

### Output Filename Construction

The mapping from the CLI argument string `file_path` to the output filename `output_file` is the deterministic two-composition function:

```
f(file_path) = os.path.splitext( os.path.basename(file_path) )[0]  +  ".mp3"
```

This function is:

- **Not injective (not one-to-one):** Multiple distinct input paths that share the same stem component — e.g., `/dir_a/notes.txt` and `/dir_b/notes.txt` — both produce `notes.mp3`. Successive invocations from the same working directory will cause the second run to **silently overwrite** the MP3 produced by the first.
- **Deterministic:** Given the same `file_path` string, the output filename is always identical, independent of file contents, system state, or time.
- **Path-oblivious:** No path component of `file_path` other than the final basename contributes to `output_file`. The output is always a bare filename relative to CWD.

## Error Handling Strategy

The script uses a fail-fast strategy. Every recoverable failure path prints a diagnostic message and calls `sys.exit(1)`. Unrecoverable failures (package installation) are allowed to propagate as unhandled exceptions.

| Location in script | Failure condition | Caught by | Exit mechanism |
|---|---|---|---|
| `install_package` | `pip` exits with non-zero return code | `subprocess.check_call` raises `CalledProcessError` — **not caught**, propagates to interpreter | Unhandled exception traceback + interpreter exit |
| `from gtts import gTTS` | Installation succeeded but import still fails | Unhandled `ImportError` | Unhandled exception traceback |
| Argument count check | `len(sys.argv) < 2` | Explicit `if` guard (lines 24–26) | `sys.exit(1)` |
| File existence check | `os.path.exists(file_path)` returns `False` | Explicit `if` guard (lines 32–34) | `sys.exit(1)` |
| Extension check | `file_path.lower().endswith('.txt')` returns `False` | Explicit `if` guard (lines 37–39) | `sys.exit(1)` |
| File read | Any exception from `open()` or `f.read()` | `except Exception as e` (lines 46–48) | `sys.exit(1)` + error message |
| TTS synthesis / save | Any exception from `gTTS()` or `tts.save()` | `except Exception as e` (lines 62–64) | `sys.exit(1)` + error message |

**Scope of `except Exception`:** This catch clause intercepts all exceptions that are subclasses of `Exception`. It does **not** catch `BaseException` subclasses that are not `Exception` subclasses — specifically `KeyboardInterrupt` and `SystemExit`. Therefore:

- A `Ctrl+C` issued during file reading or during the (potentially lengthy) `tts.save()` call will **escape** the `try/except` block, propagate normally, and terminate the interpreter with a `KeyboardInterrupt` traceback.
- A `sys.exit()` call inside the `try` block would also escape (since `SystemExit` is a subclass of `BaseException`, not `Exception`), though no such call exists in these blocks.

## Usage Instructions

### Prerequisites

- Python 3.x installed and reachable on the system `PATH`.
- An **active internet connection** is required; gTTS transmits text to Google's servers and retrieves the audio stream over HTTPS.
- No manual package installation is required — the script installs `gTTS` automatically on first run if it is absent.
- A UTF-8 encoded `.txt` file. If using the companion script `pdf2text_via_PDFplumber.py`, its output is UTF-8 by construction.

### Running the Script

```bash
python text2speech_via_Google_TTS.py <path_to_txt_file>
```

`<path_to_txt_file>` must be the path (absolute or relative to CWD) of an existing file whose name ends in `.txt` (case-insensitive). The output MP3 is always written to the **current working directory**, not the directory of the input file.

#### Examples

**Relative path — input file in current directory:**
```bash
python text2speech_via_Google_TTS.py report.txt
```
Produces `report.mp3` in the current working directory.

**Absolute path on Linux / macOS:**
```bash
python text2speech_via_Google_TTS.py /home/user/documents/report.txt
```
Produces `report.mp3` in the directory from which the command is run.

**Absolute path on Windows (PowerShell):**
```bash
python text2speech_via_Google_TTS.py "C:\Users\user\Documents\report.txt"
```
Produces `report.txt`'s stem + `.mp3` in the PowerShell working directory.

**Path with spaces — must be quoted:**
```bash
python text2speech_via_Google_TTS.py "C:\Users\user\My Documents\lecture notes.txt"
```
Produces `lecture notes.mp3` in the current working directory.

#### Two-Script Pipeline (with `pdf2text_via_PDFplumber.py`)

```bash
# Stage 1: Extract text from PDF (outputs report.txt in CWD)
python pdf2text_via_PDFplumber.py report.pdf

# Stage 2: Convert extracted text to speech (outputs report.mp3 in CWD)
python text2speech_via_Google_TTS.py report.txt
```

Both scripts must be run from the same working directory for the stem-name linkage (`report.txt` → `report.mp3`) to be preserved without manual renaming.

### Expected Console Output (Successful Run)

```
Reading text from 'report.txt'...
Text length: 42381 characters
Converting text to speech...
Audio file saved as 'report.mp3'
```

The character count will vary depending on the content of the input file. The `Converting text to speech...` line may be followed by a delay of several seconds to several minutes for large files, during which no further output is printed.

### Expected Console Output (Failure Cases)

| Scenario | Printed output |
|---|---|
| No argument supplied | `Usage: python text2speech_via_Google_TTS.py <path_to_txt_file>` |
| File not found | `Error: File 'x.txt' not found.` |
| File extension is not `.txt` | `Error: File must be a .txt file.` |
| File cannot be read (permissions, encoding error, etc.) | `Error reading text file: <exception message>` |
| Network unavailable or TTS API error | `Error converting to speech: <exception message>` |

All failure paths terminate with exit code `1`.

### Verifying the Output

After the script completes, verify the MP3 exists in the current working directory:

```bash
# Linux / macOS
ls -lh report.mp3

# Windows (PowerShell)
Get-Item report.mp3 | Select-Object Name, Length
```

Play the file with any MP3-capable player (VLC, ffplay, Windows Media Player, etc.) to confirm audio content.

## Limitations and Behavioural Notes

1. **Hard-coded English language:** `gTTS` is called with `lang='en'` unconditionally. Text files containing content in languages other than English are submitted as English to the TTS engine. Pronunciation may be incorrect or unintelligible for non-English text, and the API's behaviour for mixed-language input is undefined by this script.

2. **Entire file loaded into memory at once:** `f.read()` reads the complete file into a single string. For very large text files (hundreds of megabytes), this may exhaust available RAM. There is no streaming or line-by-line read path.

3. **Output always in CWD:** The output filename is derived from the stem of the input filename (via `os.path.basename`) with no directory prefix. The MP3 is always written to the current working directory. There is no option to specify an output directory or output filename.

4. **Silent overwrite of existing MP3:** If an MP3 with the same stem name already exists in the current working directory (e.g., from a previous run), `tts.save(output_file)` will overwrite it without warning or confirmation prompt.

5. **No synthesis progress reporting:** Once `tts.save()` is called, no output is printed until it completes. For long documents, this involves many sequential HTTP requests, each retrieving one audio chunk. The script provides no indication of completion percentage or chunk count during this phase.

6. **UTF-8 BOM handling:** If the input `.txt` file was saved with a UTF-8 BOM (`\xef\xbb\xbf`) — as some Windows editors produce — the BOM byte sequence is decoded by Python's `utf-8` codec as the Unicode character `U+FEFF` (Zero Width No-Break Space) and included in `text`. This character is then submitted to gTTS, potentially causing an inaudible artefact or brief pause at the very start of the audio. Use `encoding="utf-8-sig"` instead of `encoding="utf-8"` in the `open()` call to strip it automatically if this is a concern.

7. **Dependency on Google's TTS servers:** The script has no local speech synthesis capability. All synthesis is performed server-side by Google. Changes to Google's TTS API, endpoint URLs, or rate-limiting policies are outside the script's control and will surface as exceptions caught by the `except Exception` block in Step 5.

8. **Extension check operates on full path string:** The `.endswith('.txt')` check is applied to the full `file_path` string, not just the basename. A path ending in a directory component that contains `.txt` followed by a non-`.txt` final component could produce unexpected results in edge cases, though this is unlikely in standard usage.
