package com.akshaykadam.pixelboard.extension.rambler;

// TEST-ONLY STUB for the V29 JVM rig (tests/v29-rig). NOT the shipped class: the real one exists only in the
// shipped dex. It provides just the members GboardRamblerLoanSpell / GboardRamblerSentenceLang reference, backed
// by recorded outputs in tests/v29-rig/fixtures/shipped-outputs.tsv (plus rows a test adds at run time).

import java.util.HashMap;

final class GboardRamblerDiag {
  private GboardRamblerDiag() {}

  static final HashMap<String, Integer> COUNTS = new HashMap<>();

  static void bump(String k) { COUNTS.merge(k, 1, Integer::sum); }
}
