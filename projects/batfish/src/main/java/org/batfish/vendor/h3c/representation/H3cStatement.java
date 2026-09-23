package org.batfish.vendor.h3c.representation;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

/** A statement in a Comware view, retaining source location and all child statements. */
public final class H3cStatement implements Serializable {
  private final String _text;
  private final int _line;
  private final int _indent;
  private final List<H3cStatement> _children = new ArrayList<>();

  public H3cStatement(String text, int line, int indent) {
    _text = text;
    _line = line;
    _indent = indent;
  }

  public String getText() {
    return _text;
  }

  public int getLine() {
    return _line;
  }

  public int getIndent() {
    return _indent;
  }

  public List<H3cStatement> getChildren() {
    return _children;
  }

  public String[] words() {
    return _text.split("\\s+");
  }
}
