package com.akshaykadam.pixelboard.extension.rambler;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;

/**
 * V29 JVM rig: compiles main's GboardRamblerLoanSpell + GboardRamblerSentenceLang against test-only stubs
 * (tests/v29-rig/stubs) and checks their pure logic. Run: bash tests/v29-rig/run.sh
 * Prints "V29 RIG: N passed, M failed". Stubbed classes answer only from tests/v29-rig/fixtures/shipped-outputs.tsv.
 */
public class V29RigTest {
  static int pass, fail;

  static void eq(String name, Object want, Object got) {
    if (want == null ? got == null : want.equals(got)) { pass++; System.out.println("  PASS: " + name); }
    else { fail++; System.out.println("  FAIL: " + name + "\n        want: " + show(want) + "\n        got:  " + show(got)); }
  }

  static void ok(String name, boolean c) { eq(name, Boolean.TRUE, c); }

  static String show(Object o) {
    if (o == null) return "null";
    String s = String.valueOf(o);
    StringBuilder b = new StringBuilder(s).append("  [");
    for (int i = 0; i < s.length(); i++) { if (i > 0) b.append(' '); b.append(String.format("%04X", (int) s.charAt(i))); }
    return b.append(']').toString();
  }

  static String inVoice(java.util.function.Supplier<String> f) {
    GboardRamblerLoanSpell.enterVoice();
    try { return f.get(); } finally { GboardRamblerLoanSpell.exitVoice(); }
  }

  public static void main(String[] a) throws Exception {
    String root = a.length > 0 ? a[0] : ".";
    GboardRamblerLoanSpell.loadNow();

    System.out.println("== rig wiring");
    List<String> table = Files.readAllLines(Paths.get(root, "data/loanspell/loan-table.tsv"), StandardCharsets.UTF_8);
    ok("loan table loaded (" + table.size() + " rows in data/loanspell/loan-table.tsv)", GboardRamblerLoanSpell.loadMs >= 0 && GboardRamblerScriptFix.ENGLISH.size() >= table.size());
    eq("voice2 hook answers the table only inside voice", null, GboardRamblerLoanSpell.voice("type"));

    System.out.println("== LoanSpell (voice only)");
    eq("override wins: office", "\u0985\u09ab\u09bf\u09b8", inVoice(() -> GboardRamblerLoanSpell.spell("office")));
    eq("table: type", "\u099f\u09be\u0987\u09aa", inVoice(() -> GboardRamblerLoanSpell.spell("type")));
    eq("Bangla word never takes the loan path: kotha", null, inVoice(() -> GboardRamblerLoanSpell.spell("kotha")));
    eq("Bangla word never takes the loan path: kintu", null, inVoice(() -> GboardRamblerLoanSpell.spell("kintu")));
    eq("one letter goes to the old path", null, inVoice(() -> GboardRamblerLoanSpell.spell("a")));
    eq("apostrophe goes to the old path", null, inVoice(() -> GboardRamblerLoanSpell.spell("don't")));
    eq("tier1 wrap outside voice returns Tier1 unchanged", "X", GboardRamblerLoanSpell.tier1("office", "X"));
    eq("tier1 wrap in voice prefers the override", "\u0985\u09ab\u09bf\u09b8", inVoice(() -> GboardRamblerLoanSpell.tier1("office", "X")));
    eq("brand token in voice: whatsapp", GboardRamblerLoanSpell.OVERRIDE.get("whatsapp"), inVoice(() -> GboardRamblerLoanSpell.token("whatsapp", "whatsapp")));
    eq("token outside voice is the converter's result", "\u09aa\u09be\u09b0\u099a\u09c7", GboardRamblerLoanSpell.token("parche", "parche"));
    eq("glide repair: o + sign gets ya-nukta", "\u0993\u09df\u09be", GboardRamblerLoanSpell.glide("\u0993\u09be"));
    eq("nfc: precomposed ya becomes ya + nukta", "\u0986\u09ae\u09bf \u09af\u09bc\u09be", GboardRamblerLoanSpell.nfc("ami ya", "\u0986\u09ae\u09bf \u09df\u09be"));
    eq("nfc: a Bangla token already in the input is kept byte for byte", "\u09df\u09be \u09af\u09bc\u09c7", GboardRamblerLoanSpell.nfc("\u09df\u09be ye", "\u09df\u09be \u09df\u09c7"));
    eq("nfc: Latin-only output untouched", "hello world", GboardRamblerLoanSpell.nfc("hello world", "hello world"));
    eq("hashtag back to Latin", "\u09ad\u09be\u09b2\u09cb #blessed", GboardRamblerLoanSpell.hashtags("valo #blessed", "\u09ad\u09be\u09b2\u09cb #\u09ac\u09cd\u09b2\u09c7\u09b8\u09c7\u09a1"));
    eq("handle back to Latin", "\u09ad\u09be\u09b2\u09cb @rafi_bd", GboardRamblerLoanSpell.hashtags("valo @rafi_bd", "\u09ad\u09be\u09b2\u09cb @\u09b0\u09be\u09ab\u09bf_bd"));

    System.out.println("== SentenceLang");
    ok("bnWord: korchi (grammar list)", GboardRamblerSentenceLang.bnWord("korchi"));
    ok("bnWord: dekhchi (suffix rule)", GboardRamblerSentenceLang.bnWord("dekhchi"));
    ok("bnWord: bhalobashi (digraph rule)", GboardRamblerSentenceLang.bnWord("bhalobashi"));
    ok("bnWord: office is not Bangla", !GboardRamblerSentenceLang.bnWord("office"));
    ok("wellFormed: sign after consonant", GboardRamblerSentenceLang.wellFormed("\u0995\u09be"));
    ok("wellFormed: leading sign rejected", !GboardRamblerSentenceLang.wellFormed("\u09be\u09ae"));
    eq("repair: leading sign becomes the independent vowel", "\u0986\u09ae", GboardRamblerSentenceLang.repair("\u09be\u09ae"));
    eq("English sentence stays byte-identical", "i will call you tomorrow", GboardRamblerSentenceLang.process("i will call you tomorrow"));
    eq("Bangla sentence: Tier1 first (taratari), converter for the rest",
        "\u09ad\u09be\u09b2\u09cb \u0995\u09a5\u09be \u09a4\u09be\u09a1\u09bc\u09be\u09a4\u09be\u09a1\u09bc\u09bf",
        inVoice(() -> GboardRamblerSentenceLang.process("valo kotha taratari")));
    eq("URL inside a Bangla sentence is copied byte for byte",
        "\u098f\u0996\u09a8 https://example.com \u0995\u09bf\u09a8\u09cd\u09a4\u09c1 \u0995\u09a5\u09be",
        inVoice(() -> GboardRamblerSentenceLang.process("ekhon https://example.com kintu kotha")));

    System.out.println();
    System.out.println("V29RigTest: " + pass + " passed, " + fail + " failed");
    if (System.getProperty("rig.trace") != null) for (String s : System.getProperty("rig.trace").split("\\|")) System.out.println("trace " + s + " -> " + GboardRamblerSentenceLang.trace(s));
    System.exit(fail == 0 ? 0 : 1);
  }
}
