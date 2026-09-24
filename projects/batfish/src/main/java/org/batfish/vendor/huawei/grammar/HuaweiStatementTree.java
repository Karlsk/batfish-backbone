package org.batfish.vendor.huawei.grammar;

import java.util.ArrayDeque;
import java.util.Deque;
import org.batfish.vendor.huawei.representation.HuaweiStatement;

/** View tree: a separator closes its own indentation level, never its enclosing view. */
public final class HuaweiStatementTree {
  public static HuaweiStatement build(
      HuaweiCombinedParser parser, HuaweiParser.Huawei_configurationContext tree) {
    HuaweiStatement root = new HuaweiStatement("", 0, -1);
    Deque<HuaweiStatement> stack = new ArrayDeque<>();
    stack.push(root);
    String[] lines = parser.getInputLines();
    for (HuaweiParser.StatementContext ctx : tree.statement()) {
      int line = ctx.getStart().getLine();
      String raw = lines[line - 1];
      String text = raw.strip();
      int indent = raw.length() - raw.stripLeading().length();
      while (stack.peek().getIndent() >= indent) {
        stack.pop();
      }
      if (text.equals("#") || text.startsWith("#BATFISH") || text.startsWith("!BATFISH")) {
        continue;
      }
      HuaweiStatement statement = new HuaweiStatement(text, parser.originalLine(line), indent);
      stack.peek().getChildren().add(statement);
      stack.push(statement);
    }
    return root;
  }

  private HuaweiStatementTree() {}
}
