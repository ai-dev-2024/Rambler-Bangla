package com.akshaykadam.pixelboard.extension.rambler;

// TEST-ONLY STUB for the V29 JVM rig (tests/v29-rig). NOT the shipped class: the real one exists only in the
// shipped dex. It provides just the members GboardRamblerLoanSpell / GboardRamblerSentenceLang reference, backed
// by recorded outputs in tests/v29-rig/fixtures/shipped-outputs.tsv (plus rows a test adds at run time).

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.HashSet;

/** Loads tests/v29-rig/fixtures/*.tsv once. Path comes from -Drig.fixtures=DIR (run.sh sets it). */
final class RigFixtures {
  private RigFixtures() {}

  /** fn -> (key -> recorded output). fn is one of: token, loan, tier1, vowel. */
  static final HashMap<String, HashMap<String, String>> OUT = new HashMap<>();
  /** Word lists the shipped SegmentLock carries (BANGLA_FUNC, PROTECT_BN, GARBLE_ALLOWLIST); empty until recorded. */
  static final HashMap<String, HashSet<String>> LISTS = new HashMap<>();

  static {
    String dir = System.getProperty("rig.fixtures", "tests/v29-rig/fixtures");
    for (String fn : new String[] {"token", "loan", "tier1", "vowel"}) OUT.put(fn, new HashMap<>());
    for (String l : new String[] {"BANGLA_FUNC", "PROTECT_BN", "GARBLE_ALLOWLIST"}) LISTS.put(l, new HashSet<>());
    try (BufferedReader r = new BufferedReader(new InputStreamReader(new FileInputStream(dir + "/shipped-outputs.tsv"), StandardCharsets.UTF_8))) {
      String line;
      while ((line = r.readLine()) != null) {
        if (line.isEmpty() || line.startsWith("#")) continue;
        String[] c = line.split("\t", -1);
        if (c.length < 3) throw new IllegalStateException("bad fixture row: " + line);
        if (c[0].startsWith("list:")) { LISTS.get(c[0].substring(5)).add(c[1]); continue; }
        HashMap<String, String> m = OUT.get(c[0]);
        if (m == null) throw new IllegalStateException("unknown fixture fn: " + c[0]);
        m.put(c[1], c[2]);
      }
    } catch (java.io.IOException e) {
      throw new IllegalStateException("rig fixtures not readable in " + dir, e);
    }
  }

  static String get(String fn, String key) { return key == null ? null : OUT.get(fn).get(key); }

  /** Test hook: record one more shipped output for this run. */
  static void put(String fn, String key, String out) { OUT.get(fn).put(key, out); }
}
