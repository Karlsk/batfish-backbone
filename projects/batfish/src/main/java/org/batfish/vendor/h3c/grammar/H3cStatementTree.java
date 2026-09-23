package org.batfish.vendor.h3c.grammar;

import java.util.ArrayDeque;
import java.util.Deque;
import org.batfish.vendor.h3c.representation.H3cStatement;

/** View tree: a separator closes its own indentation level, never its enclosing view. */
public final class H3cStatementTree {
  public static H3cStatement build(
      H3cCombinedParser parser, H3cParser.H3c_configurationContext tree) {
    H3cStatement root = new H3cStatement("", 0, -1);
    Deque<H3cStatement> stack = new ArrayDeque<>();
    stack.push(root);
    String[] lines = parser.getInputLines();
    for (H3cParser.StatementContext ctx : tree.statement()) {
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
      H3cStatement statement = new H3cStatement(text, parser.originalLine(line), indent);
      stack.peek().getChildren().add(statement);
      stack.push(statement);
    }
    return root;
  }

  private H3cStatementTree() {}
}
