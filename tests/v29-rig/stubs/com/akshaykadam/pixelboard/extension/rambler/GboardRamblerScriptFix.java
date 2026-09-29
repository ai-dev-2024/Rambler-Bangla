package com.akshaykadam.pixelboard.extension.rambler;

// TEST-ONLY STUB for the V29 JVM rig (tests/v29-rig). NOT the shipped class: the real one exists only in the
// shipped dex. It provides just the members GboardRamblerLoanSpell / GboardRamblerSentenceLang reference, backed
// by recorded outputs in tests/v29-rig/fixtures/shipped-outputs.tsv (plus rows a test adds at run time).

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashSet;
import java.util.regex.Pattern;

final class GboardRamblerScriptFix {
  private GboardRamblerScriptFix() {}

  static volatile int jvmLayoutKind = 1;
  static final Pattern URL_SPAN = Pattern.compile("(?:https?://|www\\.)\\S+");
  static final ArrayList<String> DIAG = new ArrayList<>();

  /**
   * Stand-in English dictionary: the keys of data/loanspell/loan-table.tsv (English words from CMU, Bangla words pruned
   * out) plus the override keys. The shipped 20,010-word set is not in main.
   */
  static final Collection<String> ENGLISH = english();

  private static Collection<String> english() {
    HashSet<String> s = new HashSet<>(24000);
    for (String c : GboardRamblerLoanTable.chunks()) {
      int p = 0, n = c.length();
      while (p < n) {
        int sep = c.indexOf('\t', p), nl = c.indexOf('\n', p);
        if (sep < 0 || nl < 0 || sep > nl) break;
        s.add(c.substring(p, sep));
        p = nl + 1;
      }
    }
    s.addAll(GboardRamblerLoanSpell.OVERRIDE.keySet());
    return s;
  }

  static boolean isLatinLetter(char c) { return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z'); }

  static boolean hasInternalUpper(String t) {
    for (int i = 1; i < t.length(); i++) if (Character.isUpperCase(t.charAt(i))) return true;
    return false;
  }

  /** In the shipped build convertToken is replaced by LoanSpell.token (smali hook); mirror that. */
  static String convertToken(String disp, String lo) { return GboardRamblerLoanSpell.token(disp, lo); }

  /** The shipped letter converter: recorded outputs only (fixture fn "token"); unknown words return null. */
  static String convertTokenOrig(String disp, String lo) { return RigFixtures.get("token", lo); }

  static void addDiag(String s) { DIAG.add(s); }

  /** Rig helper: run f the way ScriptFix.processVoice does (enterVoice, f, exitText, exitVoice). */
  static String voice(String in, java.util.function.Function<String, String> f) {
    GboardRamblerLoanSpell.enterVoice();
    try { return GboardRamblerLoanSpell.exitText(in, f.apply(in)); } finally { GboardRamblerLoanSpell.exitVoice(); }
  }
}
