## PackedCodeSyntax (PCS) Guide v1

**Goal:** Absolute maximum information density for code structure and essential metadata. Machine-centric. Single-string representation.

**Core Principles:** Single-character codes for types/modifiers, minimal delimiters, positional context for class members, implicit meanings where possible, no optional whitespace.

**Symbols & Delimiters:**

*   `|`: Section Separator (Top: `S|O|I|C|A|D|U|F|X|Z`). On its own line.
*   `: `: (Colon-Space) Separates Section Prefix/Element Name from content (e.g., `A: `). Only after Section Prefix.
*   `;`: Element Separator (API elements in `A:`, Structs in `D:`).
*   `#`: Path Separator (in `A:`). `path#element`.
*   `~`: Type Prefix. Mandatory. (e.g., `~s`, `~i`, `~L~MyType`). See Type Codes.
*   `=`: Default Value Prefix. Follows mandatory `~Type`. (e.g., `timeout~i=30`). Literal values follow (strings require explicit `""` if they contain delimiters/spaces, e.g. `="a;b"`). Booleans are `T`/`F`. None is `N`.
*   `?`: Optional/Nullable Suffix. Appends directly after `~Type` or `=Default`.
*   `()`: Container for Parameters (functions/methods/init) or Fields (structs). Comma-separated.
*   `[]`: Container for Methods *within a class*. Comma-separated.
*   `{}`: Container for Attributes *within a class*. Comma-separated.
*   `<>`: Container for Constants/Enums *within a class*. Also used for Inheritance `$CName<Parent>`.
*   `>`: Sync Return Type Prefix. Follows `()`.
*   `*>`: Async Return Type Prefix. Follows `()`.
*   `$`: Element Type Prefix. Mandatory for all code elements defined.
    *   `$C`: Class
    *   `$F`: Function
    *   `$M`: Method (Only used *inside* Class `[]`)
    *   `$A`: Attribute (Only used *inside* Class `{}`)
    *   `$K`: Constant (Only used *inside* Class `<>`)
    *   `$E`: Enum (Only used *inside* Class `<>`)
    *   `$S`: Struct (Only used in `D:`)
*   `!`: Metadata Suffix/Prefix. Follows the element it modifies *immediately*. Multiple codes are concatenated.
    *   Status: `D` (Deprecated), `B` (Beta), `X` (Experimental).
    *   Modifiers: `r` (Read-only Attr), `s` (Static Meth), `a` (Abstract Meth/Class).
    *   Exceptions: `E(Err1,Err2)`. Comma-separated *type names* (no `~`). Always last in metadata string if present.
    *   Note: `N"text"`. Critical note. Use extremely sparingly. Text in quotes. Placed *before* `E` if both present.
    *   Example: `!Dr` (Deprecated, Readonly), `!sN"Critical"!E(ValueError,KeyError)` (Static, Note, Exceptions).
*   `,`: List Item Separator (Params, fields, methods, attrs, consts/enums, exceptions).
*   `^`: Snippet Container: `^Lang:Code^`.

**Type Codes (`~`):**

*   Primitives: `s` (str), `i` (int), `f` (float), `b` (bool), `y` (bytes), `o` (object), `a` (any), `N` (None).
*   Collections: `L~T` (List), `D~K~V` (Dict), `T~T1~T2..` (Tuple), `S~T` (Set). `T` represents nested type codes.
*   Union: `U~T1~T2..` (Union).
*   Custom/Class: `CClassName` (Reference by name).

**Sections (Prefix: Content Structure):**

*   `|S:` `SubjectName;V:VersionString`
*   `|O:` `K:~kw1,~kw2;P:~principle1`
*   `|I:` `P:~req1;C:^sh:cmd^;S:~step1,^py:code^;V:^sh:cmd^`
*   `|C:` `M:~mech1;O:~Obj1(p1),~file(s1);E:~ENV1`
*   `|A:` `$path#Elem1;$path#Elem2...` (API Elements separated by `;`)
    *   **Class Format:** `$CName!Cmeta<Parent>(init_params)[methods]{attrs}<consts_enums>`
        *   Fixed Order: Initializer `()`, Methods `[]`, Attributes `{}`, Constants/Enums `<>`. Omit empty components entirely (including delimiters).
        *   `!Cmeta`: Class-level metadata (e.g., `!aD` for Abstract Deprecated class).
        *   Initializer params: `name~type=?Val!Pmeta,...` Comma separated in `()`.
        *   Methods: `[$MName(params)*>Rt!Mmeta, $MName(...)...]` Comma separated in `[]`.
        *   Attributes: `{$AName~type=?Val!Ameta, $AName...}` Comma separated in `{}`.
        *   Consts/Enums: `<$KName~type=Val!Kmeta, $EName(M1,M2)!Emeta, ...>` Comma separated in `<>`. Enum members are just names/values.
    *   **Function Format:** `$FName(param1~type=?Val!Pmeta,...)>Rt!Fmeta` (Metadata includes Status, Note, Exceptions).
*   `|D:` `$SStructName1(f1~T?,f2~T=Val!Fmeta);$SStructName2(...)` (Structs separated by `;`. Fields `name~type=?Val!Fmeta` comma-separated in `()`. Path `#` optional.)
*   `|U:` `W:FlowName(step1->step2);W:Flow2...`
*   `|F:` `~keyword1,~keyword2`
*   `|X:` `~keyword1,~keyword2`
*   `|Z:` `^Lang:Code1^;^Lang:Code2^`

# Example PCS Structure

```pcs
|S: MyLibrary;V:1.2.3
|O: K:~data-processing,~async;P:~be-fast,~be-correct
|I: P:~python~3.9+;C:^sh:pip install mylibrary^;V:^py:import mylibrary; print(mylibrary.__version__)^
|A:
$my.module#MyClass!a<BaseClass>(config~CDict?,retries~i=3)[$MprocessData!s(data~y)*>~i!E(ProcError,TimeoutErr);$M_privateMethod(x~f)>~N]{$Aname~s!r;$A_id~s}{$KMAX_ITEMS~i=100;$EMode(FAST,SLOW)!D}
;$my.module#utilityFunc(input~U~s~i?)>~b!N"Very critical note"!E(TypeError)
|D:
$SPoint(x~i,y~i);$SColor(r~i=0,g~i=0,b~i=0)
|Z:
^py:from my.module import MyClass\n\nc = MyClass()\nprint(c.name)^
```

## Explanation

### Section S:
- Defines the subject and version

### Section O:
- Defines keywords and principles

### Section I:
- Defines installation prerequisites, commands, and verification

### Section A:
Defines API elements:

1. **Class MyClass** (in my.module):
   - Abstract (!a), inherits BaseClass
   - **Initializer**: 
     - `config`: Optional Dict (~CDict?)
     - `retries`: int (~i), defaults to 3
   - **Methods**:
     - `processData`: Static (!s), takes bytes data, returns async int, raises ProcError/TimeoutErr
     - `_privateMethod`: Takes float x, returns None
   - **Attributes**:
     - `name`: Read-only string
     - `_id`: Private string
   - **Constants/Enums**:
     - `MAX_ITEMS`: int constant (100)
     - `Mode`: Deprecated enum (FAST, SLOW)

2. **Function utilityFunc** (in my.module):
   - Takes optional Union[string, int] input
   - Returns bool
   - Has critical note
   - Raises TypeError

### Section D:
Defines Data Structures:
1. **Point**: 
   - Fields: x, y (both int)
2. **Color**:
   - Fields: r, g, b (all int, default 0)

### Section Z:
Contains a code snippet