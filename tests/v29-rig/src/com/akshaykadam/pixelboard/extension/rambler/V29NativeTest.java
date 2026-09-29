package com.akshaykadam.pixelboard.extension.rambler;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

/**
 * V29 native-word spelling targets (tests/v29-rig/fixtures/native-targets.tsv) on the voice token path:
 * recorded shipped converter output -> main's LoanSpell.token -> LoanSpell.nfc (voice exit) vs the canonical spelling.
 * Prints "V29NativeTest: N passed, M failed (X xfail)". xfail rows are known gaps; an unexpected pass (XPASS) fails.
 */
public class V29NativeTest {
  static int pass, fail, xfail;

  static String hex(String s) {
    StringBuilder b = new StringBuilder();
    for (int i = 0; i < s.length(); i++) { if (i > 0) b.append(' '); b.append(String.format("%04X", (int) s.charAt(i))); }
    return b.toString();
  }

  static String voiceToken(String w) {
    GboardRamblerLoanSpell.enterVoice();
    try { return GboardRamblerLoanSpell.nfc(w, GboardRamblerLoanSpell.token(w, w)); } finally { GboardRamblerLoanSpell.exitVoice(); }
  }


  static void check(String name, String want, String got) {
    if (want == null ? got == null : want.equals(got)) { pass++; System.out.println("  PASS: " + name); }
    else { fail++; System.out.println("  FAIL: " + name + "\n        want: " + want + (want == null ? "" : "  [" + hex(want) + "]") + "\n        got:  " + got + (got == null ? "" : "  [" + hex(got) + "]")); }
  }

  static String voiceSentence(String s) {
    GboardRamblerLoanSpell.enterVoice();
    try { return GboardRamblerLoanSpell.exitText(s, GboardRamblerSentenceLang.process(s)); } finally { GboardRamblerLoanSpell.exitVoice(); }
  }

  public static void main(String[] a) throws Exception {
    String fx = System.getProperty("rig.fixtures", "tests/v29-rig/fixtures");
    GboardRamblerLoanSpell.loadNow();
    System.out.println("== native-word targets (voice token path)");
    for (String line : Files.readAllLines(Paths.get(fx, "native-targets.tsv"), StandardCharsets.UTF_8)) {
      if (line.isEmpty() || line.startsWith("#")) continue;
      String[] c = line.split("\t", -1);
      String w = c[0], shipped = c[1], canon = c[2], status = c[3];
      RigFixtures.put("token", w, shipped);
      String got = voiceToken(w);
      boolean hit = canon.equals(got);
      String tag = w + " " + shipped + " -> " + canon;
      switch (status) {
        case "main":
        case "keep":
          if (hit) { pass++; System.out.println("  PASS: " + tag + " [" + status + "]"); }
          else { fail++; System.out.println("  FAIL: " + tag + " [" + status + "]\n        got: " + got + "  [" + hex(got) + "]"); }
          break;
        case "open":
        case "needs-source":
          if (hit) { fail++; System.out.println("  FAIL: XPASS " + tag + " [" + status + "] now passes; promote it to main"); }
          else { xfail++; System.out.println("  XFAIL: " + tag + " [" + status + "] got " + got); }
          break;
        default:
          fail++; System.out.println("  FAIL: unknown status " + status + " for " + w);
      }
    }

    System.out.println("== native-word repair: sentences and edges");
    for (String[] c : new String[][] {
        {"tumi", "\u09a4\u09c1\u09ae\u09bf"}, {"kemon", "\u0995\u09c7\u09ae\u09a8"}, {"ashbe", "\u0986\u09b8\u09ac\u09c7"}}) RigFixtures.put("token", c[0], c[1]);
    RigFixtures.put("vowel", "o", "\u0993");
    check("k2 sentence cv3: tumi kemon acho", "\u09a4\u09c1\u09ae\u09bf \u0995\u09c7\u09ae\u09a8 \u0986\u099b\u09cb", voiceSentence("tumi kemon acho"));
    check("k2 sentence cv22: o boleche ashbe", "\u0993 \u09ac\u09b2\u09c7\u099b\u09c7 \u0986\u09b8\u09ac\u09c7", voiceSentence("o boleche ashbe"));
    check("typing (outside voice) is unchanged: korche", "\u0995\u09b0\u099a\u09c7", GboardRamblerLoanSpell.token("korche", "korche"));
    check("capitalized token (a name) is unchanged", "\u09b0\u09be\u09a8\u099a\u09bf", GboardRamblerNativeSpell.fix("Ranchi", "ranchi", "\u09b0\u09be\u09a8\u099a\u09bf"));
    check("English dictionary word is unchanged: rancho", "\u09b0\u09be\u09a8\u099a\u09cb", GboardRamblerNativeSpell.fix("rancho", "rancho", "\u09b0\u09be\u09a8\u099a\u09cb"));
    check("conjunct is left alone", "\u0995\u09b0\u09cd\u099a\u09bf", GboardRamblerNativeSpell.fix("korchi", "korchi", "\u0995\u09b0\u09cd\u099a\u09bf"));
    check("unexpected tail is left alone", "\u0995\u09b0\u099a\u09be", GboardRamblerNativeSpell.fix("korchi", "korchi", "\u0995\u09b0\u099a\u09be"));
    check("null in, null out", null, GboardRamblerNativeSpell.fix("korchi", "korchi", null));
    System.out.println();
    System.out.println("V29NativeTest: " + pass + " passed, " + fail + " failed (" + xfail + " xfail)");
    System.exit(fail == 0 ? 0 : 1);
  }
}
