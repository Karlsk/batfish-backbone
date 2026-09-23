package org.batfish.vendor.h3c.grammar;

import org.antlr.v4.runtime.CharStream;
import org.batfish.grammar.BatfishLexer;

public abstract class H3cBaseLexer extends BatfishLexer {
  protected H3cBaseLexer(CharStream input) {
    super(input);
  }
}
