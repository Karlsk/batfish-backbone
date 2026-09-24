package org.batfish.vendor.huawei.grammar;

import org.antlr.v4.runtime.CharStream;
import org.batfish.grammar.BatfishLexer;

public abstract class HuaweiBaseLexer extends BatfishLexer {
  protected HuaweiBaseLexer(CharStream input) {
    super(input);
  }
}
