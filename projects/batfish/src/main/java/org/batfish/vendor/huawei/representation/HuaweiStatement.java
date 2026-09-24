package org.batfish.vendor.huawei.representation;

import java.io.Serializable;
import java.util.ArrayList;
import java.util.List;

/** A statement in a VRP view, retaining source location and all child statements. */
public final class HuaweiStatement implements Serializable {
  private final String _text;
  private final int _line;
  private final int _indent;
  private final List<HuaweiStatement> _children = new ArrayList<>();

  public HuaweiStatement(String text, int line, int indent) {
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

  public List<HuaweiStatement> getChildren() {
    return _children;
  }

  public String[] words() {
    return _text.split("\\s+");
  }
}
