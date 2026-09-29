package com.akshaykadam.pixelboard.extension.rambler;

import java.util.Collection;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Native-word (non-loanword) Bangla spelling repair for voice dictation, applied to the letter converter's result for one
 * romanized token (LoanSpell.token calls it; Tier1 answers never come here, typing and paste never call it).
 *
 * In romanized Bangla "ch" is written for both চ and ছ; in the progressive, perfect and copula endings it is always ছ
 * (korche করছে, boleche বলেছে, acho আছো, geche গেছে), and the verb root "ash" (come) is আস (ashchi আসছি, ashte আসতে).
 * The converter gives চ/শ there. Only the ending's চ (or the root's শ) is changed, and only when the converter's own
 * output ends in exactly the expected shape; anything else, and any English dictionary word or capitalized token,
 * is returned unchanged. Never throws.
 */
final class GboardRamblerNativeSpell {
  private GboardRamblerNativeSpell() {}

  static volatile int diagFixes;
  static volatile int diagFailures;

  static final String ENDING = "(i|e|o|en|is|ilam|ilo|ile|ilen)";
  /** Progressive: a stem with a vowel, ending in a consonant (not c: "cch" is already চ্ছ), + ch + ending. */
  static final Pattern PROGRESSIVE = Pattern.compile("[a-z]*[aeiou][a-z]*[bdghklmnpr]ch" + ENDING);
  /** Perfect: a stem of two or more letters + ech + ending (korechi, boleche, peyeche, kinechi). */
  static final Pattern PERFECT = Pattern.compile("[a-z]{2,}ech" + ENDING);
  /** Copula ach- and the perfect of ja- (geche): too short for the two rules above. */
  static final Pattern SHORT = Pattern.compile("(?:a|ge)ch" + ENDING);
  /** Root ash- (come) before a verb ending. */
  static final Pattern ASH = Pattern.compile("ash(?:ch" + ENDING + "|le|te|tese|tesi|lam|lo|len|ten)");

  static String fix(String disp, String lo, String out) {
    try {
      if (lo == null || out == null || out.isEmpty()) return out;
      if (disp != null && !disp.isEmpty() && Character.isUpperCase(disp.charAt(0))) return out;
      String k = lo.toLowerCase(Locale.US);
      Collection<?> en = GboardRamblerScriptFix.ENGLISH;
      if (en != null && en.contains(k)) return out;
      String r = out;
      Matcher m = PROGRESSIVE.matcher(k);
      if (!m.matches()) { m = PERFECT.matcher(k); if (!m.matches()) { m = SHORT.matcher(k); if (!m.matches()) m = null; } }
      if (m != null) r = aspirate(r, m.group(1));
      Matcher a = ASH.matcher(k);
      if (a.matches() && r.length() > 2 && r.charAt(0) == '\u0986' && r.charAt(1) == '\u09b6') r = "\u0986\u09b8" + r.substring(2);
      if (!r.equals(out)) diagFixes++;
      return r;
    } catch (Throwable e) {
      diagFailures++;
      return out;
    }
  }

  /** The last চ becomes ছ when what follows it is exactly the Bangla form of the ending and it is not part of a conjunct. */
  static String aspirate(String w, String ending) {
    int c = w.lastIndexOf('\u099a');
    if (c <= 0 || w.charAt(c - 1) == '\u09cd' || (c + 1 < w.length() && w.charAt(c + 1) == '\u09cd')) return w;
    String tail = w.substring(c + 1);
    boolean ok;
    switch (ending) {
      case "i": ok = tail.equals("\u09bf"); break;
      case "e": ok = tail.equals("\u09c7"); break;
      case "o": ok = tail.equals("\u09cb"); break;
      case "en": ok = tail.equals("\u09c7\u09a8"); break;
      case "is": ok = tail.equals("\u09bf\u09b8") || tail.equals("\u09bf\u09b6"); break;
      case "ilam": ok = tail.equals("\u09bf\u09b2\u09be\u09ae"); break;
      case "ilo": ok = tail.equals("\u09bf\u09b2\u09cb") || tail.equals("\u09bf\u09b2"); break;
      case "ile": ok = tail.equals("\u09bf\u09b2\u09c7"); break;
      case "ilen": ok = tail.equals("\u09bf\u09b2\u09c7\u09a8"); break;
      default: ok = false;
    }
    return ok ? w.substring(0, c) + '\u099b' + tail : w;
  }
}
