package com.akshaykadam.pixelboard.extension.rambler;

// TEST-ONLY STUB for the V29 JVM rig (tests/v29-rig). NOT the shipped class: the real one exists only in the
// shipped dex. It provides just the members GboardRamblerLoanSpell / GboardRamblerSentenceLang reference, backed
// by recorded outputs in tests/v29-rig/fixtures/shipped-outputs.tsv (plus rows a test adds at run time).

final class GboardRamblerTier1 {
  private GboardRamblerTier1() {}

  /** Shipped: get(k) is wrapped by LoanSpell.tier1(k, getOrig(k)) (v29.3 smali hook). Mirror that. */
  static String get(String k) { return GboardRamblerLoanSpell.tier1(k, getOrig(k)); }

  /** The shipped 2,265-pair table: recorded pairs only (fixture fn "tier1"). */
  static String getOrig(String k) { return RigFixtures.get("tier1", k); }
}
