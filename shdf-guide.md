SHDF Guide: Parse & Represent Software Data
Goal: Max density, unambiguous single-string format. Machine-optimized for generation & parsing. Symbols define structure/type.
Core Principles: Consistent rules, minimal whitespace, explicit structure.
Delimiters & Symbols:
| : Section Separator (Top level: S|O|A|...)
: : Prefix/Name Separator. Always used after Section Prefix (e.g., A:) or Element Name (e.g., MyClass:) before details/content, except at string start or immediately after | or ;.
; : Element Separator. Separates items within Sections (API elements in A; Structs in D; KV pairs in O,I,C; Flows in U; Snippets in Z; Version in S).
§ : Component Separator (New). Used only within an API element definition in A: to separate I, M, T, K components. (e.g., I(...)§M:...§T:...)
, : List Item Separator. For items within a logical group: parameters in I(), fields in D(), method args in M(), keywords, errors in E(), constants/enum members in K.
# : Path Separator. Precedes ElementName only in A:. Mandatory in A:. (e.g., path.mod#Elem)
~ : Type Prefix. Mandatory before any type name. (e.g., ~str, ~int, ~List~MyType)
= : Default Value Prefix. Follows mandatory ~Type. (e.g., timeout~int=30) Optional.
() : Parameter/Field/Error/Enum Member List Container.
> : Sync Return Type Prefix. Follows ().
*> : Async Return Type Prefix. Follows ().
^T...^ : Code Snippet Container. T = I(Init/Import), E(Exec/Example), C(Config).
-> : Workflow Step Separator (Only in U > W: flows).
!D, !B, !X : Status Suffix Markers. Append directly after return type (>Rt or *>Rt) or () if no return type. (Deprecated, Beta, Experimental).
Sections (Prefix:Content Structure):
S: S:SubjectName;V:VersionString
O: O:K:~kw1,~kw2;P:~principle1,~principle2 (K=Purpose KWs, P=Principle KWs)
I: I:P:~req1;C:~install_cmd;S:~step1,^cmd^;V:~^verify_cmd^ (P=Prereqs, C=InstallCmd, S=Setup, V=Verify)
C: C:M:~mech1;O:~Obj1(p1),~file.ext(s1);E:~ENV1 (M=Mechanisms, O=Objects/Files, E=EnvVars)
A: A:path#Elem1§Comp1;path#Elem2... (API Elements: Classes, Modules, Functions sep by ';')
Class Format: path#ClassName:I(param1~Type=Default,param2~Type)§M:meth1(p~T)*>Rt!B,E(Err1,Err2),meth2()>None§T:attr1~Type=Default§K:CONST1~Type=Val,Enum1(M1,M2)
I(...): Initializer. Params , separated.
M:...: Methods block. Methods , separated.
E(Err1,Err2): Exceptions for the preceding method, enclosed in (), , separated.
T:...: Attributes block. Attributes , separated.
K:...: Constants/Enums block. Items , separated. Enum members in ().
Module Format: path#ModName:F:func1(...)§K:CONST1~Type (Use F: for functions if needed, else list directly like funcs). Components separated by §.
Func Format: path#FuncName(param1~Type)>Rt!D,E(ErrType1,ErrType2)
D: D:StructName1:f1~Type,f2~Type=Default;Struct2:f~T (Data Structs sep by ';'. Fields , sep in struct body - () removed for consistency). Path optional (use if primary importable).
U: U:W:FlowName(step1->step2);W:Flow2... (Workflows W: prefixed, sep by ';')
F: F:~keyword1,~keyword2 (Feature Keywords, , separated)
X: X:~keyword1,~keyword2 (Deployment Keywords, , separated)
Z: Z:^ICode1^;^ECode2^;^CConfig1^ (Snippets sep by ';')
Example Snippet Interpretation (SHDF v4):
A:api.svc#Client:I(url~str,tok~str)§M:getData(id~int)*>Result!B,E(AuthErr,NotFoundErr)§T:timeout~int=30§K:MAX_RETRIES~int=5;utils#parseData(d~bytes)>ParsedData!D,E(ParseErr)
Means: API Section (A:).
Element 1: Class Client in api.svc#.
Initializer (I:): Takes url (~str), tok (~str).
Methods (M:): Has method getData. Takes id (~int). Returns async (*>) Result. Is Beta (!B). Can raise (E()) AuthErr, NotFoundErr. (Note comma separates methods, E() attaches to getData).
Attributes (T:): Has attribute timeout (~int, default 30).
Constants (K:): Has constant MAX_RETRIES (~int, value 5).
Element 2 (separated by ;): Function parseData in utils#.
Takes d (~bytes). Returns sync (>) ParsedData. Is Deprecated (!D). Can raise (E()) ParseErr.