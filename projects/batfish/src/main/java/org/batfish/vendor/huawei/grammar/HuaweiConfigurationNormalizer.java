package org.batfish.vendor.huawei.grammar;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;

/** Huawei terminal capture cleanup, preserving real indentation and source line positions. */
public final class HuaweiConfigurationNormalizer {
  private static final Pattern PAGER_ERASE =
      Pattern.compile("  ---- More ----\u001b\\[16D {16}\u001b\\[16D");
  private static final Pattern ANSI = Pattern.compile("\u001b\\[[0-?]*[ -/]*[@-~]");
  private static final Pattern NOISE =
      Pattern.compile(
          "(?:<[^>]+>.*|\\[[~*][^]]+].*|(?:dis|display)\\s+(?:cur|current-configuration).*|!.*)");

  public record Result(String text, List<Integer> originalLines) {
    public int originalLine(int line) {
      return originalLines.get(line - 1);
    }
  }

  public static Result normalize(String input) {
    String text = PAGER_ERASE.matcher(input).replaceAll("");
    text = ANSI.matcher(text).replaceAll("").replace("---- More ----", "");
    text = text.replaceAll("\\r+\\n", "\n").replaceAll("\\r+", "\n");
    StringBuilder out = new StringBuilder();
    List<Integer> mapping = new ArrayList<>();
    String[] lines = text.split("\n", -1);
    for (int n = 0; n < lines.length; n++) {
      if (n == lines.length - 1 && lines[n].isEmpty()) {
        break;
      }
      StringBuilder line = new StringBuilder();
      for (char ch : lines[n].toCharArray()) {
        if (ch == '\b') {
          if (!line.isEmpty()) {
            line.setLength(line.length() - 1);
          }
        } else {
          line.append(ch);
        }
      }
      String clean = line.toString();
      if ((clean.isBlank() || NOISE.matcher(clean.strip()).matches() || clean.strip().equals("dis"))
          && !clean.strip().startsWith("!BATFISH")) {
        clean = "";
      }
      out.append(clean).append('\n');
      mapping.add(n + 1);
    }
    return new Result(out.toString(), List.copyOf(mapping));
  }

  private HuaweiConfigurationNormalizer() {}
}
