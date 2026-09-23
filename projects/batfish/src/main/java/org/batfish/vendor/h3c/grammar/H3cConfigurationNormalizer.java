package org.batfish.vendor.h3c.grammar;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** Removes terminal capture artifacts without consuming configuration indentation. */
public final class H3cConfigurationNormalizer {
  private static final Pattern ANSI = Pattern.compile("\u001b\\[[0-?]*[ -/]*[@-~]");
  private static final Pattern PAGER =
      Pattern.compile("---- More ----(?:\\r+[ \\t]+\\r| {16}| {15})?");
  private static final Pattern NOISE =
      Pattern.compile(
          "(?:<[^>]+>.*|\\[[^]]+].*|(?:dis|display)(?:\\s+.*)?|Building configuration.*|Current"
              + " configuration.*)");

  public record Result(String text, List<Integer> originalLines) {
    public int originalLine(int normalizedLine) {
      return originalLines.get(normalizedLine - 1);
    }
  }

  public static Result normalize(String input) {
    // Pager erasure occurs before CR normalization: its CRs are cursor motion, not lines.
    String text = PAGER.matcher(ANSI.matcher(input).replaceAll("")).replaceAll("");
    text = text.replaceAll("\\r+\\n", "\n").replaceAll("\\r+", "\n");
    String[] lines = text.split("\n", -1);
    StringBuilder out = new StringBuilder();
    List<Integer> originalLines = new ArrayList<>();
    for (int i = 0; i < lines.length; i++) {
      if (i == lines.length - 1 && lines[i].isEmpty()) {
        break;
      }
      String line = lines[i];
      if (line.isBlank() || NOISE.matcher(line.trim()).matches()) {
        line = "";
      }
      out.append(line).append('\n');
      originalLines.add(i + 1);
    }
    return new Result(out.toString(), List.copyOf(originalLines));
  }

  private H3cConfigurationNormalizer() {}
}
