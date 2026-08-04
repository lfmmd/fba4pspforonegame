# Read entire file
undef $/;
open(F, "src/psp/input.cpp") or die;
$_ = <F>;
close(F);

# 1. Add new static vars after bForceTestMode
s/bool bForceTestMode = false;/bool bForceTestMode = false;\nstatic int nServiceInpIdx = -1;\nstatic bool bServiceOneShot = false;/;

# 2. Add one-shot check at the end of InpMake (in the else branch for dip switches)
s#(\t\t\} else \{\s+// dip switch \.\.\.\s+\s+\*\(GameInp\[i\]\.pVal\) = GameInp\[i\]\.nConst;\s+\})#$1\n\n\tif (bServiceOneShot \&\& nServiceInpIdx >= 0 \&\& nServiceInpIdx < (int)nGameInpCount) {\n\t\t*(GameInp[nServiceInpIdx].pVal) = 0xFF;\n\t\tbServiceOneShot = false;\n\t}#;

# 3. Overwrite InpForceTestMode - delete old and insert new after InpDIPSetOne
s/^void InpForceTestMode\(\).*?^\}/void InpForceTestMode()\n\{\n\tif (!GameInp) return;\n\n\tstruct BurnInputInfo bii;\n\n\t\/\/ Try Service 1 first\n\tfor (unsigned int i = 0; i < nGameInpCount; i++) \{\n\t\tmemset(\&bii, 0, sizeof(bii));\n\t\tBurnDrvGetInputInfo(\&bii, i);\n\t\tif (bii.nType == BIT_DIGITAL \&\& strcmp(bii.szInfo, \"service\") == 0) \{\n\t\t\tnServiceInpIdx = i;\n\t\t\tbServiceOneShot = true;\n\t\t\treturn;\n\t\t\}\n\t\}\n\t\/\/ Fallback: Diagnostics 1\n\tfor (unsigned int i = 0; i < nGameInpCount; i++) \{\n\t\tmemset(\&bii, 0, sizeof(bii));\n\t\tBurnDrvGetInputInfo(\&bii, i);\n\t\tif (bii.nType == BIT_DIGITAL \&\& strcmp(bii.szInfo, \"diag\") == 0) \{\n\t\t\tnServiceInpIdx = i;\n\t\t\tbServiceOneShot = true;\n\t\t\treturn;\n\t\t\}\n\t\}\n\}/ms;

# 4. Delete InpClearTestMode function
s/^void InpClearTestMode\(\).*?^\n// The function below is InpSaveDIPToIni/void InpSaveDIPToIni/ms;

open(G, ">src/psp/input.cpp") or die;
print G $_;
close(G);
