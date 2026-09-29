package com.akshaykadam.pixelboard.extension.rambler;

// TEST-ONLY STUB for the V29 JVM rig (tests/v29-rig). NOT the shipped class: the real one exists only in the
// shipped dex. It provides just the members GboardRamblerLoanSpell / GboardRamblerSentenceLang reference, backed
// by recorded outputs in tests/v29-rig/fixtures/shipped-outputs.tsv (plus rows a test adds at run time).

import java.util.HashSet;
import java.util.regex.Pattern;

final class GboardRamblerSegmentLock {
  private GboardRamblerSegmentLock() {}

  // Read by GboardRamblerSentenceLang.H through reflection, like the shipped private fields.
  private static final HashSet<String> BANGLA_FUNC = RigFixtures.LISTS.get("BANGLA_FUNC");
  private static final HashSet<String> PROTECT_BN = RigFixtures.LISTS.get("PROTECT_BN");
  private static final HashSet<String> GARBLE_ALLOWLIST = RigFixtures.LISTS.get("GARBLE_ALLOWLIST");
  private static final Pattern HANDLE_SPAN = Pattern.compile("(?<![A-Za-z0-9_])@[A-Za-z0-9_](?:[A-Za-z0-9_.]*[A-Za-z0-9_])?");
  private static final Pattern TIME_SUFFIX = Pattern.compile("(?i)\\b\\d{1,2}(?::\\d{2})?\\s?(?:am|pm)\\b");

  /** Shipped order: the WP-E hook (LoanSpell.voice2) first, then the recorded loan converter output (fixture fn "loan"). */
  private static String convertLoan(String disp, String lo) {
    String v = GboardRamblerLoanSpell.voice2(disp, lo);
    return v != null ? v : RigFixtures.get("loan", lo);
  }

  private static String singleVowel(String t) { return RigFixtures.get("vowel", t); }

  /** Conservative morphology stand-in: -ed/-ing/-s on a dictionary stem (doubled final consonant allowed). */
  private static boolean englishByInflection(String lo) {
    for (String suf : new String[] {"ing", "ed", "s"}) {
      if (lo.length() > suf.length() + 2 && lo.endsWith(suf)) {
        String st = lo.substring(0, lo.length() - suf.length());
        if (GboardRamblerScriptFix.ENGLISH.contains(st) || GboardRamblerScriptFix.ENGLISH.contains(st + "e")) return true;
        int k = st.length();
        if (k > 2 && st.charAt(k - 1) == st.charAt(k - 2) && GboardRamblerScriptFix.ENGLISH.contains(st.substring(0, k - 1))) return true;
      }
    }
    return false;
  }

  private static boolean nearEnglishED1(String lo) { return false; }
}
